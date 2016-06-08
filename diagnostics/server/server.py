"""
Server for laser diagnostics operation.
"""
import itertools
import asyncio
import json
import jsonrpc
import collections
import weakref


# don't actually do anything with wavemeter/osa
TEST=False
if TEST:
    import random
    DAQError = Exception
else:
    from PyDAQmx.DAQmxFunctions import DAQError
    import diagnostics.server.osa as osa
    import diagnostics.server.wavemeter as wavemeter

import diagnostics.common as common
from diagnostics.server.channel import ServerChannel as Channel


# Normal switching interval in seconds
INTERVAL=1

DEFAULT_CFG_FILE = "./cfg/oldlab_server.json"

class Server(common.JSONRPCPeer):
    """
    """
    # List of configurable attributes (maintains order when dumping config)
    # These will all be initialised during __init__ in the call to 
    # super.__init__ because JSONRPCPeer is a JSONConfigurable
    _attrs = collections.OrderedDict([
                ('name', None),
                ('address', None),
                ('port', None),
                ('switcher', None),
                ('channels', Channel),
                ('fast', None),
                ('pause', None),
            ])

    @property
    def interval(self):
        if self.fast:
            return 0.5
        else:
            return 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Generator for cycling through configured channels infinitely
        self.ch_gen = itertools.cycle(self.channels)

        self.clients = weakref.WeakValueDictionary()
        self.connections = {}

        self.data_q = asyncio.Queue()

        self.tcp_server = None
        self.locked = False

        # Switching task is stored to allow cancellation
        self.next_switch = None

        # Measurement tasks
        self.otask = None
        self.wtask = None

    def startup(self):
        # Start the TCP server
        coro = asyncio.start_server(self.client_connected, self.address, self.port)
        self.tcp_server = self.loop.run_until_complete(coro)
        # Schedule switching and store the task
        self.next_switch = self.loop.call_soon(self.switch)
        # Make sure we're taking items off the queue
        self.loop.create_task(self.consume())

    def shutdown(self):
        self.cancel_pending_tasks()
        self.close_connections()
        self.tcp_server.close()
        self.loop.run_until_complete(self.tcp_server.wait_closed())

    # -------------------------------------------------------------------------
    # Network operations
    #
    async def client_connected(self, reader, writer):
        # Store the client reader and writer objects under the address
        # and start the listening coroutine
        conn = common.JSONRPCConnection(self.handle_rpc, reader, writer)
        future = self.loop.create_task(conn.listen())

        addr = writer.get_extra_info('peername')
        self.connections[addr] = conn

        def register_connection(result):
            print("Connection registered: {} ({})".format(addr, result))
            self.clients[result] = conn
        self.request(conn, 'get_name', cb=register_connection)

        def client_disconnected(future):
            # Just removing connection from connections should be enough -
            # all the other references are weak
            print("Connection unregistered: {}".format(addr))
            conn = self.connections.pop(addr)
            conn.close()
            del conn
        future.add_done_callback(client_disconnected)

    def close_connections(self):
        while self.connections:
            (_, conn) = self.connections.popitem()
            conn.close()

    # -------------------------------------------------------------------------
    # Switching
    #
    def switch(self, channel=None):
        """Switch to the NAMED channel"""
        self.next_switch = None

        # Cancel the old Wavemeter and OSA Tasks
        if not TEST:
            self.cancel_tasks()

        # Get the next channel in sequence if none supplied
        if channel is None:
            channel = next(self.ch_gen)
        c = self.channels[channel]
        #print("!", end='', flush=True)

        # Switch the switcher, wherever it's located
        if self.switcher['name'] == "wavemeter":
            if not TEST:
                wavemeter.switch(c.number)
        else:
            # do the switching
            pass

        if not TEST:
            self.new_tasks(c)
            self.start_tasks()
        else:
            self.dummy_osa(channel)
            self.dummy_wavemeter(channel)

        # Schedule the next switch
        if not self.locked:
            self.next_switch = self.loop.call_later(self.interval, self.switch)

    # -------------------------------------------------------------------------
    # RPC methods
    #
    # Prefix RPC methods with `rpc_`. This prefix is stripped before adding
    # to the dispatcher
    #
    # All state changes in the server should be accompanied by notifications
    # to ALL clients, not just the one causing the state change
    #
    def rpc_lock(self, channel):
        """
        Switches to named channel indefinitely
        """
        if self.next_switch:
            self.loop.call_soon(self.next_switch.cancel)
        self.locked = channel
        self.loop.call_soon(self.switch, channel)
        self.loop.call_soon(self.notify_locked, channel)

    def rpc_unlock(self):
        """Resume normal switching"""
        self.locked = False
        self.next_switch = self.loop.call_soon(self.switch)
        self.loop.call_soon(self.notify_unlocked)

    def rpc_pause(self, pause=True):
        if pause:
            if self.next_switch:
                self.loop.call_soon(self.next_switch.cancel)
            self.cancel_tasks()
        else:
            # Resume
            if self.locked:
                self.loop.call_soon(self.switch, self.locked)
            else:
                self.loop.call_soon(self.switch)
        self.pause = pause

    def rpc_get_name(self):
        return self.name

    def rpc_register_client(self, client, channels):
        """
        Add the client to the send list for the list of channels
        """
        conn = self.clients.get(client)
        result = {}
        for c in channels:
            self.channels[c].add_client(client, conn)
            result[c] = self.channels[c].to_json(separators=(',', ':'))
        return result

    def rpc_unregister_client(self, client):
        pass

    def rpc_configure_channel(self, channel, cfg):
        c = self.channels.get(channel)
        if c is not None:
            c.from_dict(cfg)
            self.loop.call_soon(self.notify_refresh_channel, channel)

    def rpc_echo_channel_config(self, channel):
        return self.channels[channel].to_json()

    def rpc_save_channel_settings(self, channel):
        """Save the currently stored channel config to file"""
        # Get channel settings
        cfg = self.channels[channel].to_dict()
        update = {'channels':{channel:cfg}}

        # Store running config so that not all channels are saved
        running = self.to_dict()

        # Load file into running (from_file defaults to the last used)
        self.from_file()

        # Update with channel to save and then save file
        self.from_dict(update)
        self.to_file()

        # Restore running config
        self.from_dict(running)

    def rpc_save_all(self):
        self.to_file()

    def rpc_configure_server(self, cfg):
        # Only allow updates to acquisition mode, update speed and pause
        cfg = {k:v for k,v in cfg.items if k in ['mode', 'fast', 'pause']}
        self.from_dict(cfg)

    def rpc_echo(self, s):
        return s

    # -------------------------------------------------------------------------
    # Notifications to clients
    def notify_locked(self, channel):
        method = "locked"
        params = {"server":self.name, "channel":channel}
        self._notify_all(method, params)

    def notify_unlocked(self):
        method = "unlocked"
        params = {"server":self.name}
        self._notify_all(method, params)

    def notify_refresh_channel(self, channel):
        c = self.channels.get(channel)
        method = "refresh_channel"
        params = {"channel":channel, "cfg":c.to_json()}
        self._notify_channel(channel, method, params)

    # -------------------------------------------------------------------------
    # Helper functions for channel/client requests
    #
    def _notify_client(self, client, *args, **kwargs):
        pass

    def _notify_channel(self, channel, *args, **kwargs):
        c = self.channels.get(channel)
        #print("\nNotify channel: {} args: {} kwargs: {}".format(channel, args, kwargs))
        for conn in c.clients.values(): 
            self.loop.create_task(conn.notify(*args, **kwargs))

    def _notify_all(self, *args, **kwargs):
        #print("\nNotify all: args: {} kwargs: {}".format(args, kwargs))
        for conn in self.connections.values():
            self.loop.create_task(conn.notify(*args, **kwargs))
        #for conn in self.clients.values()
        #    conn.notify(*args, **kwargs)

    # -------------------------------------------------------------------------
    # Data consumption
    #
    async def consume(self):
        """Handles data sending and logs frequency occasionally"""
        while True:
            data = await self.data_q.get()
            if data['source'] == 'wavemeter':
                # logic for logging
                pass
            self.loop.call_soon(self.send_data, data)
            #self.loop.call_soon(self.basic_send_data, data)

    def basic_send_data(self, data):
        """Sends data to all clients indiscriminately"""
        method = data['source']
        params = {k:v for k,v in data.items() if k != 'source'}
        self._notify_all(method, params)

    def send_data(self, data):
        """Send the data to the appropriate clients only"""
        channel = data['channel']
        method = data['source']
        params = {k:v for k,v in data.items() if k != 'source'}
        self._notify_channel(channel, method, params)

    # -------------------------------------------------------------------------
    # OSA and Wavemeter task operations
    #
    def new_tasks(self, channel):
        if self.otask is None:
            self.otask = osa.OSATask(self.loop, self.data_q, channel)
        if self.wtask is None:
            self.wtask = wavemeter.WavemeterTask(self.loop, self.data_q, channel)        
        # else error condition

    def start_tasks(self):
        if self.otask is not None:
            self.otask.StartTask()
        if self.wtask is not None:
            self.wtask.StartTask()

    def cancel_tasks(self):
        if self.otask is not None:
            try:
                self.otask.StopTask()
            except DAQError:
                # we expect an error due to stopping acquisition before
                # requested number of samples acquired
                pass
            self.otask.ClearTask()
            self.otask = None

        if self.wtask is not None:
            self.wtask.StopTask()
            self.wtask.ClearTask()
            self.wtask = None

