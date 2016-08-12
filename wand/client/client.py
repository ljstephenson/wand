"""
Client for laser diagnostic operations
"""
import collections
import numpy as np
import time
import weakref

from . import QtGui

import wand.common as common
from wand.client.server import Server
from wand.client.peer import ThreadClient
from wand import __version__


@common.with_log
class ClientBackend(ThreadClient):
    _attrs = collections.OrderedDict([
        ('name', None),
        ('version', None),
        ('servers', Server),
        ('layout', None),
    ])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_config()

        self.running = False

        self.conns_by_s = weakref.WeakValueDictionary()
        self.conns_by_c = weakref.WeakValueDictionary()
        self.channels = collections.OrderedDict()
        self.name_map = collections.OrderedDict()
        self.short_names = collections.OrderedDict()

        for s in self.servers.values():
            s.client = self
            for c in s.channels.values():
                c.client = self
                self.channels[c.name] = c
                self.name_map[c.name] = c.short_name
                self.short_names[c.short_name] = c.name

    def startup(self):
        self.running = True
        for s in self.servers:
            self.server_connect(s)
            self.request_version(s)
        self._log.info("Ready")

    def shutdown(self):
        self.running = False
        self.close_connections()
        self._log.info("Shutdown finished")

    # -------------------------------------------------------------------------
    # RPC methods implemented by this class
    #
    # Prefix RPC methods with `rpc_`. This prefix is stripped before adding
    # to the dispatcher
    #
    def rpc_get_name(self):
        # print("called get_name")+
        return self.name

    def rpc_osa(self, channel, data, scale):
        c = self.channels.get(channel)
        if c is not None:
            c.osa = np.divide(np.asarray(data), scale)

    def rpc_wavemeter(self, channel, data):
        c = self.channels.get(channel)
        if c is not None:
            c.frequency = data

    def rpc_refresh_channel(self, channel, cfg):
        """Called by the server when another client updates config"""
        c = self.channels.get(channel)
        if c is not None:
            c.from_json(cfg)

    def rpc_locked(self, server, channel):
        # Show locking of stated channel and clear all others associated with
        # this server
        locked = self.channels.get(channel)
        if locked is not None:
            # Locked channel may not be shown on this client at all
            locked.set_locked(True)

        s = self.servers.get(server)
        s.locked = channel
        unlocked = [self.channels.get(c) for c in s.channels if c != channel]
        for c in unlocked:
            c.set_locked(False)

    def rpc_unlocked(self, server):
        s = self.servers.get(server)
        s.locked = False
        unlocked = [self.channels.get(c) for c in s.channels]
        for c in unlocked:
            c.set_locked(False)

    def rpc_paused(self, server, pause):
        self.servers.get(server).pause = pause

    def rpc_fast(self, server, fast):
        self.servers.get(server).fast = fast

    def rpc_server_state(self, server, pause, lock, fast):
        if lock:
            self.rpc_locked(server, lock)
        else:
            self.rpc_unlocked(server)
        self.rpc_paused(server, pause)
        self.rpc_fast(server, fast)

    def rpc_uptime(self, server, uptime):
        self.servers.get(server).uptime = uptime

    def rpc_ping(self, server):
        # self._log.debug("Ping from {}".format(server))
        pass

    def rpc_timestamp(self, server, timestamp):
        self._log.debug("{} timestamp:{}".format(server,
                                                 time.ctime(timestamp)))

    def rpc_list_server_channels(self, server):
        """Return the configured list of channels under a server"""
        return list(self.servers.get(server).channels)

    def rpc_log(self, server, lvl, msg):
        """Servers can call this to use the client log"""
        self._log.log(lvl, "{} says: {}".format(server, msg))

    def rpc_version(self):
        # Note that this is the running version, not the config version.
        # The patch number in config is assumed not to matter.
        return __version__

    # -------------------------------------------------------------------------
    # Requests for RPC
    #
    # Could do fancy things like overriding getattr to make proxies and so on,
    # but it's clearer to make each request explicitly a request and have the
    # the slight awkwardness of typing out the method name and expected
    # parameter lists here
    #
    # This also provides a convenient place to define a callback on the result
    # of the RPC
    #
    def request_echo_channel_config(self, channel):
        method = "echo_channel_config"
        params = {"channel":channel}
        self._channel_request(channel, method, params)

    def request_lock(self, channel):
        method = "lock"
        params = {"channel":channel}
        self._channel_request(channel, method, params)

    def request_unlock(self, channel):
        method = "unlock"
        params = {}
        self._channel_request(channel, method, params)

    def request_configure_channel(self, channel, cfg):
        method = "configure_channel"
        params = {"channel":channel, "cfg":cfg}
        self._channel_request(channel, method, params)

    def request_save_channel_settings(self, channel):
        method = "save_channel_settings"
        params = {"channel":channel}
        self._channel_request(channel, method, params)

    def request_register_client(self, server):
        """Request the configured channels from the server"""
        def update_channels(result):
            for c, cfg in result.items():
                self.channels[c].from_json(cfg)
        s = self.servers.get(server)
        method = "register_client"
        params = {"client":self.name, "channels":list(s.channels)}
        self._server_request(server, method, params, cb=update_channels)

    def request_echo(self, server, string):
        method = "echo"
        params = {"s":string}
        self._server_request(server, method, params)

    def request_pause(self, server, pause):
        method = "pause"
        params = {"pause":pause}
        self._server_request(server, method, params)

    def request_fast(self, server, fast):
        method = "fast"
        params = {"fast":fast}
        self._server_request(server, method, params)

    def request_version(self, server):
        def checker(version):
            try:
                self.check_version(version, "server")
            except AssertionError as e:
                self.fatal(str(e))
        method = "version"
        self._server_request(server, method, cb=checker)

    # -------------------------------------------------------------------------
    # Helpers for channel/server requests
    #
    def _channel_request(self, channel, *args, **kwargs):
        conn = self.conns_by_c[channel]
        self.request(conn, *args, **kwargs)

    def _channel_notify(self, channel, *args, **kwargs):
        conn = self.conns_by_c[channel]
        self.notify(conn, *args, **kwargs)

    def _server_request(self, server, *args, **kwargs):
        conn = self.conns_by_s[server]
        self.request(conn, *args, **kwargs)

    # -------------------------------------------------------------------------
    # Misc
    #
    def fatal(self, reason):
        """Force quits the application, logging the error message"""
        self._log.critical(reason)
        QtGui.QApplication.instance().quit()

    def get_channel_by_short_name(self, short_name):
        """Fetch the channel object using its short name"""
        name = self.short_names[short_name]
        return self.channels[name]

    def check_version(self, version, owner):
        """
        Checks a version string against the internal running version.

        Raise an assertion error on major mismatch, return False on a
        minor mismatch and True otherwise.
        """
        # Versions consist of 3 numbers separated by dots, so split on
        # the dots for Major/Minor/Patch number
        vtuple = version.split('.')
        internal = __version__.split('.')
        msg = "{{}} version mismatch: client {}, {} {}".format(__version__,
                                                               owner, version)

        assert vtuple[0] == internal[0], msg.format("Major")

        if vtuple[1] != internal[1]:
            self._log.warning(msg.format("Minor"))
            return False
        else:
            self._log.debug("Client and {} versions match".format(owner))
            return True

    # -------------------------------------------------------------------------
    # Config sanitiser
    #
    def check_config(self):
        """Check the current config for errors and flag them"""
        try:
            # Raises AssertionError on major mismatch
            self.check_version(self.version, "config")

            # flatten the layout, which is a list of lists, to have all the
            # short names we expect to see configured
            flattened = [shortname for row in self.layout for shortname in row]

            # Each short name is configured on the channel itself
            all_names = [ch.short_name for sv in self.servers.values()
                         for ch in sv.channels.values()]
            count_names = collections.Counter(all_names)
            for name in count_names:
                err = "Short name '{}' is not unique".format(name)
                assert count_names[name] == 1, err

            # Check that all names in layout map to actual channels
            for name in flattened:
                err = "Can't map short name '{}' to a full name".format(name)
                assert name in all_names, err

        except AssertionError as e:
            self._log.error("Error in config file: {}".format(e))
            raise
