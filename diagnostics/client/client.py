"""
Client for laser diagnostic operations
"""
import asyncio
import numpy
import collections
import threading

import diagnostics.common as common

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Now initialised/called by superclass:
        #     self.loop = asyncio.get_event_loop()
        #     self.dsp = jsonrpc.Dispatcher()
        #     self.add_rpc_methods()

        self.channels = {}

    def startup(self):
        """Place all startup methods here"""
        for s in self.servers:
            self.loop.create_task(self.server_connect(s))

        self.loop.call_later(60, self.kbstop)

    def shutdown(self):
        """Place all shutdown methods here"""
        self.cancel_pending_tasks()
        self.close_connections()
        self.loop.close()

    # -------------------------------------------------------------------------
    # Network operations
    #
    async def server_connect(self, server):
        """Connect to the named server"""
        s = self.servers[server]
        try:
            reader, writer = await asyncio.open_connection(s['address'], s['port'], loop=self.loop)
        except ConnectionRefusedError as e:
            print("connection failed: TODO: try again later")
        else:
            conn = common.JSONRPCConnection(self.handle_rpc, reader, writer)
            self.loop.create_task(conn.listen())
            s['connection'] = conn
            print("Opened connections to {}".format(server))

    def close_connections(self):
        for s in self.servers.values():
            s['connection'].close()

    # -------------------------------------------------------------------------
    # temporary
    #
    def tmp_add_request(self):
        self.loop.create_task(self.request(self.writer, "get_name", cb=self.tmp_process))

    def echo(self, msg):
        print(msg)

    def kbstop(self):
        raise KeyboardInterrupt

    # -------------------------------------------------------------------------
    # RPC methods
    #
    # Prefix RPC methods with `rpc_`. This prefix is stripped before adding
    # to the dispatcher
    #
    def rpc_get_name(self):
        print("called get_name")
        return self.name

    def rpc_osa(self, channel, time, data):
        print("OSA notification: {}".format([channel, time, data]))

    def rpc_wavemeter(self, channel, time, data):
        print("Wavemeter notification: {}".format([channel, time, data]))

    # -------------------------------------------------------------------------
    # Server requests
    #
    def request_channels(self, server):
        """Request the configured channels from the server"""

    def configure_channel(self, channel, cfg):
        """Send a request to change channel config to the appropriate server"""
        method = "configure_channel"
        params = {"channel":channel, "cfg":cfg}
        conn = channel.server

        self.request(conn, method, params)


class ClientBackendThread(threading.Thread):
    def run(self):
        self.cl = ClientBackend(fname=CFG_FILE)
        self.cl.run()

