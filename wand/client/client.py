"""
Client for laser diagnostic operations
"""
import asyncio
import collections
import weakref
import numpy as np
import sys
import random

import wand.common as common
from wand.client.server import Server
from wand.client.peer import RPCClient
from wand import __version__


@common.with_log
class ClientBackend(RPCClient):
    _attrs = collections.OrderedDict([
                ('name', None),
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

    def rpc_list_server_channels(self, server):
        """Return the configured list of channels under a server"""
        return list(self.servers.get(server).channels)

    def rpc_log(self, server, lvl, msg):
        """Servers can call this to use the client log"""
        self._log.log(lvl, "{} says: {}".format(server, msg))

    def rpc_version(self):
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
            server = version.split('.')
            client = __version__.split('.')
            msg = "{} version mismatch: server {}, client {}".format("{}", version, __version__)
            if server[0] != client[0]:
                self.fatal(msg.format("Major"))
            elif server[1] != client[1]:
                self._log.warning("{}. Some features may not work".format(msg.format("Minor")))
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
        self._log.critical(reason)

    def get_channel_by_short_name(self, short_name):
        """Fetch the channel object using its short name"""
        name = self.short_names[short_name]
        return self.channels[name]

    # -------------------------------------------------------------------------
    # Config sanitiser
    #
    def check_config(self):
        """Check the current config for errors and flag them"""
        try:
            flat_layout = [shortname for row in self.layout for shortname in row]
            for shortname in flat_layout:
                all_names = [ch.short_name for sv in self.servers.values() for ch in sv.channels.values()]
                assert shortname in all_names, "{} not found in any server list".format(name)
        except AssertionError as e:
            self._log.error("Error in config file: {}".format(e))
            raise
