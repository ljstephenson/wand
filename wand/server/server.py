"""
Server for laser diagnostics operation.
"""
import itertools
import asyncio
import collections
import weakref
from influxdb import InfluxDBClient

import wand.server.osa as osa
import wand.server.wavemeter as wavemeter
import wand.server.switcher as switcher
import wand.server.fake as fake
import wand.common as common
from wand.server.channel import Channel


@common.with_log
class Server(common.JSONRPCPeer):
    """
    Main class for laser diagnostics.

    Implements a TCP server for clients to connect to, handles gathering
    data from OSA and wavemeter, switching channels, and distributing data
    to clients.
    """
    # List of configurable attributes (maintains order when dumping config)
    # These will all be initialised during __init__ in the call to 
    # super.__init__ because JSONRPCPeer is a JSONConfigurable
    _attrs = collections.OrderedDict([
                ('name', None),
                ('host', None),
                ('port', None),
                ('influxdb', None),
                ('switcher', None),
                ('osa', None),
                ('mode', None),
                ('channels', Channel),
            ])
    switch_interval = 10
    data_frequency = {'fast':10, 'slow':1}
    log_interval = {'wavemeter':5, 'osa':600}

    def __init__(self, simulate=False, **kwargs):
        super().__init__(**kwargs)
        self.simulate = simulate
        self.get_switcher()
        self.configure_osa()
        self.configure_wavemeter()

        # Initialise influxdb client
        if not self.simulate:
            self.influx_cl = InfluxDBClient(**self.influxdb)

        # Generator for cycling through configured channels infinitely
        self.ch_gen = itertools.cycle(self.channels)

        self.clients = weakref.WeakValueDictionary()

        self.data_q = asyncio.Queue()

        self.tcp_server = None
        self.locked = None
        self.pause = False
        self.fast = False
        self.setup_data_rate()

        # Switching task is stored to allow cancellation
        self._next = None

        # Measurement tasks
        self.tasks = []

        # Store last logging time of wavelength and osa trace
        self.last_log = collections.OrderedDict()
        for c in self.channels:
            self.last_log[c] = {"wavemeter":None, "osa":None}

    def get_switcher(self):
        """Factory to set the 'switch' method to do the right thing"""
        if self.simulate:
            # lambda function must have an argument
            self.switch = lambda channel: None
        elif self.switcher['name'] == "wavemeter":
            self.switch = wavemeter.switch
        elif self.switcher['name'] == "leoni":
            self._switcher = switcher.LeoniSwitcher(**self.switcher['kwargs'])
            self.switch = self._switcher.setChannel

    def configure_osa(self):
        """Set the input and trigger channels to be used on the osa"""
        if not self.simulate:
            osa.channel_setup(self.osa)
            self._log.debug("Set osa configuration")

    def configure_wavemeter(self):
        """Initialise wavemeter"""
        if not self.simulate:
            wavemeter.init()
            self._log.debug("Wavemeter ready")

    def startup(self):
        # Start the TCP server
        coro = asyncio.start_server(self.client_connected, self.host, self.port)
        self.tcp_server = self.loop.run_until_complete(coro)
        # Schedule switching and store the task
        self._next = self.loop.call_soon(self.select)
        # Make sure we're taking items off the queue
        self.loop.create_task(self.consume())
        self.do_nothing()
        if self.simulate:
            self._log.info("Running as simulation, will not access hardware")
        self._log.info("Ready")

    def shutdown(self):
        self.cancel_pending_tasks()
        self.close_connections()
        self.tcp_server.close()
        self.loop.run_until_complete(self.tcp_server.wait_closed())
        self._log.info("Shutdown finished")

    def do_nothing(self):
        async def pinger():
            await asyncio.sleep(1)
            self.loop.call_soon(self.ping)
            self.loop.create_task(pinger())
        self.loop.create_task(pinger())

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
        self._log.info("Incoming connection from {}".format(addr))

        def register_connection(result):
            if result not in self.clients:
                self._log.info("Connection from {} registered: {}".format(addr, result))
                self.clients[result] = conn
                self.notify_server_state(result)
            else:
                self._log.info("Connection from {} rejected: name '{}' is already registered".format(addr, result))
                self.notify(conn, 'connection_rejected',
                            params={"server":self.name, "reason":"Client with same name already connected"})
        self.request(conn, 'get_name', cb=register_connection)

        def client_disconnected(future):
            # Just removing connection from connections should be enough -
            # all the other references are weak
            self._log.info("Connection unregistered: {}".format(addr))
            conn = self.connections.pop(addr)
            conn.close()
            del conn
            # If all clients have been removed, assume we can return to
            # switching mode
            if not self.connections:
                self._log.info("No more clients connected, force switching mode")
                self.locked = False
                self.pause = False
                self.fast = False
                self.setup_data_rate()
                self.loop.call_soon(self.select)
        future.add_done_callback(client_disconnected)

    # -------------------------------------------------------------------------
    # Switching
    #
    def select(self, channel=None):
        """Switch to named channel and begin collections"""
        self._next = None

        # Cancel the old Wavemeter and OSA Tasks
        self.cancel_tasks()

        # Get the next channel in sequence if none supplied
        if channel is None:
            channel = next(self.ch_gen)
        c = self.channels[channel]

        self._log.info("Selecting channel: {}".format(channel))
        self.switch(c.number)
        self.new_tasks(c)
        self.start_tasks()

        # Schedule the next switch
        if not self.locked:
            self._next = self.loop.call_later(self.switch_interval, self.select)

    def setup_data_rate(self):
        speed = 'fast' if self.fast else 'slow'

        self._log.info("Setting to {} mode".format(speed))
        f = self.data_frequency[speed]
        if self.simulate:
            fake.set_frequency(f)
        else:
            osa.set_frequency(f)
            wavemeter.set_frequency(f)

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
        self._log.info("Locking switcher to {}".format(channel))
        self.locked = channel
        self.loop.call_soon(self.notify_locked, channel)
        if not self.pause:
            if self._next:
                self.loop.call_soon(self._next.cancel)
            self.loop.call_soon(self.select, channel)


    def rpc_unlock(self):
        """Resume normal switching"""
        self._log.info("Unlocking switcher")
        self.locked = False
        self.loop.call_soon(self.notify_unlocked)
        if not self.pause:
            self._next = self.loop.call_soon(self.select)

    def rpc_pause(self, pause=True):
        if self._next:
            self.loop.call_soon(self._next.cancel)

        # Do nothing unless new value is different from old
        if pause ^ self.pause:
            if pause:
                self._log.info("Pausing")
                self.cancel_tasks()
            else:
                # Resume
                self._log.info("Unpausing")
                if self.locked:
                    self.loop.call_soon(self.select, self.locked)
                else:
                    self.loop.call_soon(self.select)
            self.pause = pause
            self.loop.call_soon(self.notify_paused)

    def rpc_fast(self, fast):
        # Do nothing unless new value is different from old
        if fast ^ self.fast:
            self.fast = fast
            self.setup_data_rate()
            self.loop.call_soon(self.notify_fast)

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
        self._log.debug("Saving {} settings".format(channel))
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
        self._log.debug("ECHO '{}'".format(s))
        return s

    # -------------------------------------------------------------------------
    # Notifications to clients
    #
    def notify_locked(self, channel):
        method = "locked"
        params = {"server":self.name, "channel":channel}
        self._notify_all(method, params)

    def notify_unlocked(self):
        method = "unlocked"
        params = {"server":self.name}
        self._notify_all(method, params)

    def notify_paused(self):
        method = "paused"
        params = {"server":self.name, "pause":self.pause}
        self._notify_all(method, params)

    def notify_fast(self):
        method = "fast"
        params = {"server":self.name, "fast":self.fast}
        self._notify_all(method, params)

    def notify_update_speed(self):
        method = "update_speed"
        params = {"server":self.name, "speed":self.update_speed}
        self._notify_all(method, params)

    def notify_refresh_channel(self, channel):
        c = self.channels.get(channel)
        method = "refresh_channel"
        params = {"channel":channel, "cfg":c.to_json()}
        self._notify_channel(channel, method, params)

    def notify_server_state(self, client=None):
        method = "server_state"
        params = {
            'server':self.name,
            'pause':self.pause,
            'lock':self.locked,
            'fast':self.fast
        }
        if client is not None:
            self._notify_client(client, method, params)
        else:
            self._notify_all(method, params)

    def ping(self):
        method = "ping"
        params = {"server":self.name}
        self._notify_all(method, params)

    # -------------------------------------------------------------------------
    # Helper functions for channel/client requests
    #
    def _notify_client(self, client, *args, **kwargs):
        conn = self.clients.get(client)
        if conn is not None:
            self.loop.create_task(conn.notify(*args, **kwargs))

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
            self.loop.call_soon(self.log_data, data)
            self.loop.call_soon(self.send_data, data)

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
        if self.simulate:
            tasks = [fake.OSATask, fake.WavemeterTask]
        else:
            if self.mode == 'osa_only':
                tasks = [osa.OSATask]
            elif self.mode == 'wavemeter_only':
                tasks = [wavemeter.WavemeterTask]
            else:
                tasks = [osa.OSATask, wavemeter.WavemeterTask]

        for t in tasks:
            self.tasks.append(t(self.loop, self.data_q, channel))

    def start_tasks(self):
        for t in self.tasks:
            t.StartTask()

    def cancel_tasks(self):
        while self.tasks:
            t = self.tasks.pop()
            t.StopTask()
            t.ClearTask()

    # -------------------------------------------------------------------------
    # Data logging
    #
    def log_data(self, data):
        """Choose whether or not to log a data point based on last log"""
        channel = data['channel']
        source = data['source']
        now = self.loop.time()
        last = self.last_log[channel][source]
        if last is None or now - last > self.log_interval[source]:
            self.last_log[channel][source] = now
            self._log.debug("Logging data for {} from {}".format(channel, source))
            if not self.simulate:
                if source == 'osa':
                    self.osa_log(data, now)
                else:
                    self.send_influx(data)

    def osa_log(self, data, time):
        """Save the osa data"""
        pass

    # -------------------------------------------------------------------------
    # InfluxDB
    #
    def send_influx(self, data):
        """Send reformatted wavemeter data object to influxDB server"""
        self.influx_cl.write_points(self.data2influx(data))

    def data2influx(self, data):
        """Convert wavemeter data object to influxDB point"""
        channel = data['channel']
        d = data['data']
        if d > 0:
            # Give all data in Hz, let influxdb handle any conversion
            frequency = d * 1e12
            detuning = (d - self.channels[channel].reference)*1e12
            error = None
        else:
            frequency = None
            detuning = None
            error = int(d)
        return self.populate_influx(channel, frequency, detuning, error)

    def populate_influx(self, channel, frequency, detuning, error):
        """Populate wavemeter influxDB point with relevant tags and fields"""
        return [
            {
                "measurement": "wavemeter",
                "tags": {
                    "channel": channel,
                },
                "fields": {
                    "frequency": frequency,
                    "detuning": detuning,
                    "error": error,
                }
            }
        ]
