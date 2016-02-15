"""
Server for laser diagnostics operation.
"""
import itertools
import asyncio
import json
import jsonrpc
import collections

from PyDAQmx.DAQmxFunctions import DAQError

import diagnostics.server.osa as osa
import diagnostics.server.wavemeter as wavemeter
import diagnostics.server.channel as channel
import diagnostics.common as common

# don't actually do anything with wavemeter/osa
TEST=True
if TEST:
    import random

# Normal switching interval in seconds
INTERVAL=1
# Lock duration in seconds
LOCK=300

# TODO: should read filename from command line args when starting
CFG_FILE = "./cfg/oldlab_server.json"



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
                ('channels', channel.ServerChannel),
            ])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Now initialised/called by superclass:
        #     self.loop = asyncio.get_event_loop()
        #     self.dsp = jsonrpc.Dispatcher()
        #     self.add_rpc_methods()

        # Generator for cycling through configured channels infinitely
        self.ch_gen = itertools.cycle(self.channels)

        self.clients = {}
        self.connections = {}

        # maxsize is temporary for the time being
        self.data_q = asyncio.Queue(maxsize=1000, loop=self.loop)

        self.tcp_server = None
        self.locked = False

        # Switching task is stored to allow cancellation
        self.next_switch = None

        # Measurement tasks
        self.otask = None
        self.wtask = None

    def startup(self):
        # TODO: Put this somewhere more sensible (main?)
        if not TEST:
            wavemeter.init()

        # Start the TCP server
        coro = asyncio.start_server(self.client_connected, self.address, self.port, loop=self.loop)
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
        self.loop.close()

    # -------------------------------------------------------------------------
    # Network operations
    #
    async def client_connected(self, reader, writer):
        # Store the client reader and writer objects under the address
        # and start the listening coroutine
        conn = common.JSONRPCConnection(self.handle_rpc, reader, writer)
        self.loop.create_task(conn.listen())

        def register_connection(result):
            print("Registered connection of {}".format(result))
            self.clients[result] = conn

        # Get the name of the client
        self.request(conn, 'get_name', cb=register_connection)

        addr = writer.get_extra_info('peername')
        print("Registered connection of {}".format(addr))
        self.connections[addr] = conn

    def close_connections(self):
        for conn in self.connections.values():
            conn.close()

    # -------------------------------------------------------------------------
    # Switching
    #
    def switch(self, ch_name=None):
        """Switch to the NAMED channel"""
        self.next_switch = None

        # Cancel the old Wavemeter and OSA Tasks
        if not TEST:
            self.cancel_tasks()

        # Get the next channel in sequence if none supplied
        if ch_name is None:
            ch_name = next(self.ch_gen)
        channel = self.channels[ch_name]
        print("!", end='', flush=True)

        # Switch the switcher, wherever it's located
        if self.switcher['name'] == "wavemeter":
            if not TEST:
                wavemeter.switch(channel.number)
        else:
            # do the switching
            pass

        if not TEST:
            self.new_tasks(channel)
            self.start_tasks()
        else:
            self.dummy_osa(ch_name)
            self.dummy_wavemeter(ch_name)

        # Schedule the next switch
        if not self.locked:
            delay = INTERVAL
        else:
            delay = LOCK
            self.locked = False
        self.next_switch = self.loop.call_later(delay, self.switch)

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
        Switches to named channel and delays the next switch.

        (so less of a lock and more of a hold, but never mind)
        """
        self.loop.call_soon_threadsafe(self.next_switch.cancel)
        self.locked = True
        self.loop.call_soon(self.switch, channel)

    def rpc_unlock(self):
        """Resume normal switching"""
        self.loop.call_soon_threadsafe(self.next_switch.cancel)
        self.locked = False
        self.loop.call_soon(self.switch)

    def rpc_get_name(self):
        return self.name

    def rpc_add_channels(self, client, channels):
        """
        Add the client to the send list for the list of channels
        """
        conn = self.clients.get(client)
        for ch in channels:
            self.channels[ch].add_client(client, conn)

    def rpc_remove_channels(self, client, channels):
        for ch in channels:
            self.channels[ch].remove_client(client)

    def rpc_echo(self, s):
        return s

    # -------------------------------------------------------------------------
    # Helper functions
    #
    def data2notification(self, data):
        """Convert data from sources into an rpc notification payload"""
        notification = {'jsonrpc':"2.0"}
        notification['method'] = data['source']
        notification['params'] = {k:v for k,v in data.items() if k != 'source'}

        return notification

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
            self.loop.call_soon(self.basic_send_data, data)

    def basic_send_data(self, data):
        """Sends data to all clients indiscriminately"""
        notification = self.data2notification(data)

        for conn in self.connections.values():
            self.loop.create_task(conn.send_object(notification))

    def send_data(self, data):
        """Send the data to the appropriate clients only"""
        channel = self.channels.get(data['channel'])
        notification = self.data2notification(data)

        for conn in channel.clients.values():
            self.loop.create_task(conn.send_object(notification))

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


    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! #
    # Dirty and nasty hacks
    #
    def state(self):
        """Return the running state as a string"""

    def dummy_osa(self, channel):
        data_length = 10
        data = [random.randint(0, 65535) for _ in range(data_length)]
        self.loop.create_task(self.data_q.put(
            {'source':'osa', 'channel':channel, 'time':self.loop.time(), 'data':data} ))

    def dummy_wavemeter(self, channel):
        frequency = random.randint(100, 200)
        self.loop.create_task(self.data_q.put(
            {'source':'wavemeter', 'channel':channel, 'time':self.loop.time(), 'data':frequency} ))
