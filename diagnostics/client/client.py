"""
Client for laser diagnostic operations
"""
import asyncio
import collections
import weakref
import numpy as np
import sys
import random

import diagnostics.common as common
from diagnostics.client.channel import ClientChannel

# TODO: should read filename from command line args
CFG_FILE = "./cfg/oldlab_client.json"

class ClientBackend(common.JSONRPCPeer):
    # List of configurable attributes (maintains order when dumping config)
    # These will all be initialised during __init__ in the call to 
    # super.__init__ because JSONRPCPeer is a JSONConfigurable
    _attrs = collections.OrderedDict([
                ('name', None),
                ('servers', None),
            ])

    def __init__(self, cls, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.running = False

        self.conns_by_s = {}
        self.conns_by_c = weakref.WeakValueDictionary()
        self.channels = collections.OrderedDict()

        if cls is None:
            cls = ClientChannel

        for s in self.servers.values():
            channels = s.get('channels', [])
            for c in channels:
                self.channels[c] = cls(self, cfg={'name':c})

    def startup(self):
        """Place all startup methods here"""
        self.running = True
        for s in self.servers:
            self.loop.run_until_complete(self.server_connect(s))


    def shutdown(self):
        """Place all shutdown methods here"""
        self.running = False
        self.cancel_pending_tasks()
        self.close_connections()

    # -------------------------------------------------------------------------
    # Network operations
    #
    async def server_connect(self, server, attempt=1):
        """Connect to the named server"""
        def disconnected(future):
            """Simple closure so that we can tell which server disconnected"""
            self.server_disconnected(server)

        s = self.servers[server]
        try:
            reader, writer = await asyncio.open_connection(s['address'], s['port'])
        except (ConnectionRefusedError, WindowsError) as e:
            print("Connection failed")
            self.loop.create_task(self.server_reconnect(server, attempt))
        else:
            conn = common.JSONRPCConnection(self.handle_rpc, reader, writer)

            self.conns_by_s[server] = conn

            channels = s.get('channels', [])
            for c in channels:
                self.conns_by_c[c] = conn
                
            future = self.loop.create_task(conn.listen())
            future.add_done_callback(disconnected)

            # Wait to make sure client has replied with name before
            # requesting channels
            self.loop.call_later(1.0, self.request_register_client, server)

    def server_disconnected(self, server):
        """Called when server disconnects"""
        print("Server {} disconnected".format(server))
        conn = self.conns_by_s.pop(server, None)
        if conn:
            conn.close()
            del conn
        if self.running:
            self.loop.create_task(self.server_reconnect(server))

    async def server_reconnect(self, server, attempt=0):
        backoff = 10 * attempt * random.random()
        attempt = attempt + 1
        if attempt < 5:
            print("Attempting reconnect after {:.1f}s".format(backoff))
            await asyncio.sleep(backoff)
            await self.server_connect(server, attempt)
        else:
            print("Aborting reconnect, too many failures")

    def close_connections(self):
        while self.conns_by_s:
            (_, conn) = self.conns_by_s.popitem()
            conn.close()
            del conn

    # -------------------------------------------------------------------------
    # RPC methods implemented by this class
    #
    # Prefix RPC methods with `rpc_`. This prefix is stripped before adding
    # to the dispatcher
    #
    def rpc_get_name(self):
        # print("called get_name")
        return self.name

    def rpc_osa(self, channel, time, data):
        # print("OSA notification: {}".format([channel, time, data]))
        c = self.channels.get(channel)
        if c is not None:
            c.osa = np.asarray(data)

    def rpc_wavemeter(self, channel, time, data):
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
            locked.lock()

        channels = self.servers.get(server).get('channels')
        unlocked = [self.channels.get(c) for c in channels if c != channel]
        for c in unlocked:
            c.unlock()

    def rpc_unlocked(self, server):
        channels = self.servers.get(server).get('channels')
        unlocked = [self.channels.get(c) for c in channels]
        for c in unlocked:
            c.unlock()

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
        s = self.servers.get(server, {})
        method = "register_client"
        params = {"client":self.name, "channels":s.get('channels', [])}
        self._server_request(server, method, params, cb=update_channels)

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
