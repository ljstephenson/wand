"""
Common classes and methods
"""
import asyncio
import collections
import ctypes
import json
import jsonrpc
import logging
import logging.handlers
import os

__all__ = [
    'with_log',
    'get_log_name',
    'add_verbosity_args',
    'get_verbosity_level',
    'JSONRPCPeer',
    'JSONRPCConnection',
    'JSONStreamIterator',
    'JSONConfigurable',
]


def with_log(cls):
    """Decorator to add a logger to a class."""
    setattr(cls, '_log', logging.getLogger(
        cls.__module__ + '.' + cls.__qualname__))
    return cls


def add_verbosity_args(parser):
    """Add args for verbose/quiet to an argparser"""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v", "--verbose", help="Increase output verbosity", action="count")
    group.add_argument(
        "-q", "--quiet", help="Decrease output verbosity", action="count")


def get_verbosity_level(args):
    """Set logging level given parsed args"""
    # Default log level is warning
    level = logging.WARNING
    if args.verbose:
        new_level = (logging.WARNING - 10*args.verbose)
        level = max(new_level, logging.DEBUG)
    elif args.quiet:
        new_level = (logging.WARNING + 10*args.quiet)
        level = min(new_level, logging.CRITICAL)
    return level


def get_log_name(name):
    """Platform independent way of getting appropriate log name"""
    if os.name == "nt":
        # Windows machine, shared area at Z:\
        shared = 'Z:\\'
    else:
        shared = os.path.expanduser('~/steaneShared')

    dirname = 'wavemeters'
    subdir = 'logs'
    filename = name + '.log'
    prefix = os.path.join(shared, dirname, subdir)
    return os.path.join(prefix, filename)


@with_log
class JSONConfigurable(object):
    """
    Base class for objects which can be configured with JSON

    Subclasses must implement their own _attrs OrderedDict
        * _attrs can map to other classes, which must themselves be a
           JSONConfigurable or to None
        * if a JSONConfigurable is mapped then the config must be a
          dictionary, allowing the key to be used as an identifier and the
          value as a JSON object used to initialise the JSONConfigurable
        * otherwise if the attribute maps to 'None' then the value is stored
          as is
        * OrderedDict for consistent dumping to files

    This schema allows nested JSONConfigurables.
    """

    def __init__(self, cfg=None, cfg_str=None, fname=None):
        """Initialise a JSONConfigurable with the given config option. """
        # Check that only one of the initialising options was used
        options = [cfg, cfg_str, fname]
        it = iter(options)
        if any(it) and any(it):
            # This looks a bit funny at first glance, but works:
            # We create an iterator from 'options', then consume from it until
            # we find a truthy value - the first 'any'
            # 'it' now consists of the values left over, so if another truthy
            # one is found we've supplied too many options
            raise ValueError(
                "Only one of 'cfg', 'cfg_str' and 'fname' may be supplied")

        if not hasattr(self, '_attrs'):
            raise NotImplementedError(
                "JSONConfigurable must have an `_attrs` OrderedDict")

        # Set all attrs so that they exist
        self.set_blank()
        self.filename = None

        if cfg:
            self.from_dict(cfg)
        elif cfg_str:
            self.from_json(cfg_str)
        elif fname:
            self.from_file(fname)

    def set_blank(self):
        """Initialise and clear all configuration"""
        for attr, cls in self._attrs.items():
            if cls:
                setattr(self, attr, collections.OrderedDict())
            else:
                setattr(self, attr, None)

    def cfg_from_file(self, fname=None):
        """Return the configuration dict from a file"""
        if fname is not None:
            self.filename = fname

        with open(self.filename, 'r') as f:
            cfg = json.load(f, object_pairs_hook=collections.OrderedDict)
        return cfg

    def from_file(self, fname=None):
        """Set configuration from a file"""
        cfg = self.cfg_from_file(fname)
        self.from_dict(cfg)

    def cfg_to_file(self, cfg, fname=None, **kwargs):
        """Save a configuration dict to a file"""
        # Default to pretty printing with indent
        if kwargs == {}:
            kwargs = {'indent': 4, 'separators': (',', ':')}

        if fname is not None:
            self.filename = fname

        with open(self.filename, 'w') as f:
            json.dump(cfg, f, **kwargs)

    def to_file(self, fname=None, **kwargs):
        """Print configuration to a file"""
        cfg = self.to_dict()
        self.cfg_to_file(cfg, fname, **kwargs)

    def from_json(self, cfg_str):
        """Set attributes with JSON string"""
        cfg = json.loads(cfg_str, object_pairs_hook=collections.OrderedDict)
        self.from_dict(cfg)

    def to_json(self, **kwargs):
        """Return the JSON string for this item's configuration"""
        cfg = self.to_dict()
        return json.dumps(cfg, **kwargs)

    def from_dict(self, cfg):
        """
        Set config from a dictionary.

        Will update rather than overwrite, so call set_blank to clear config.
        """
        for attr, cls in self._attrs.items():
            # Get the raw object from config
            # Note that object not supplied (KeyError, do nothing) is not the
            # same as a None object supplied (clear that section)
            try:
                val = cfg[attr]
            except KeyError:
                # Not supplied, don't change
                pass
            else:
                if cls and val is not None:
                    # Form the dictionary of new sub items
                    _dict = collections.OrderedDict()
                    for name, sub_cfg in val.items():
                        # key is used as name field as well
                        sub_cfg['name'] = name
                        _dict[name] = cls(cfg=sub_cfg)

                    # Update the current dictionary with the new one
                    getattr(self, attr).update(_dict)
                elif cls:
                    # We expected a dict but got nothing, set to blank dict
                    setattr(self, attr, collections.OrderedDict())
                else:
                    # Just store the raw value
                    setattr(self, attr, val)

    def to_dict(self):
        """Return the dict representing this item's configuration"""
        _dict = collections.OrderedDict()
        for attr, cls in self._attrs.items():
            if cls:
                sub_dict = collections.OrderedDict(
                    [(k, obj.to_dict())
                     for k, obj in getattr(self, attr).items()])
                _dict[attr] = sub_dict
            else:
                _dict[attr] = getattr(self, attr)

        return _dict

    def from_dict_lenient(self, cfg):
        """
        Mostly wrong, but works if the configuration is complete and correct
        """
        for attr, val in cfg.items():
            if attr in self._attrs:
                cls = self._attrs[attr]

                if cls:
                    _dict = collections.OrderedDict()
                    for name, sub_cfg in val.items():
                        _dict[name] = cls(cfg=sub_cfg)
                    setattr(self, attr, _dict)
                else:
                    setattr(self, attr, val)


class JSONRPCPeer(JSONConfigurable):
    """
    Base class that acts as both RPC server and client.
    """

    def __init__(self, *args, **kwargs):
        # JSON configuration initialisation
        super().__init__(*args, **kwargs)
        self.set_up_logger()

        self.loop = asyncio.get_event_loop()
        self.connections = {}

        self.result_q = asyncio.Queue()
        self.dsp = jsonrpc.Dispatcher()
        self.add_rpc_methods()

        self.next_id = 0
        self.results = {}

    def set_up_logger(self):
        """Set up the top level logger"""
        log = logging.getLogger('wand')
        log_name = get_log_name(self.name)
        fmt = logging.Formatter(
            "{asctime}:{levelname}:{name}:{message}", style='{')
        # Use 10kib log files, with 5 backups
        fh = logging.handlers.RotatingFileHandler(
            log_name, maxBytes=100*1024, backupCount=5)
        ch = logging.StreamHandler()
        for handler in [fh, ch]:
            handler.setFormatter(fmt)
            log.addHandler(handler)

    def add_rpc_methods(self):
        """Add the rpc methods to the dispatcher (call only during init)"""
        rpc_methods = [s for s in dir(self) if s.startswith('rpc_')
                       and callable(getattr(self, s))]
        for method in rpc_methods:
            fn = getattr(self, method)
            # Remove the prefix
            name = method[4:]
            self.dsp.add_method(fn, name=name)

    def startup(self):
        """
        To be run before entering infinite event loop.

        Subclasses must define functionality
        """
        raise NotImplementedError

    def shutdown(self):
        """
        To be run after exiting infinite loop.

        Subclasses must define functionality
        """
        raise NotImplementedError

    def cancel_pending_tasks(self):
        """Cancel pending loop tasks explicitly"""
        pending = asyncio.Task.all_tasks()
        if pending:
            for p in pending:
                p.cancel()
            self.loop.run_until_complete(asyncio.wait(pending, timeout=0.1))

    def request(self, *args, **kwargs):
        self.loop.create_task(self._request(*args, **kwargs))

    def notify(self, *args, **kwargs):
        self.loop.create_task(self._notify(*args, **kwargs))

    def handle_rpc(self, conn, obj):
        """
        Triage an RPC packet according to whether it is a request or response.
        """
        if isinstance(obj, dict) and 'method' in obj:
            self.loop.create_task(self._request_handler(conn, obj))
        else:
            self.loop.create_task(self._response_handler(obj))

    def do_nothing(self):
        """Keeps the loop occupied and responsive to CTRL+C"""
        async def sleep():
            await asyncio.sleep(1)
            self.loop.create_task(sleep())
        self.loop.create_task(sleep())

    def close_connections(self):
        while self.connections:
            (_, conn) = self.connections.popitem()
            conn.close()

    # -------------------------------------------------------------------------
    # Internal functions
    #
    async def _request(self, conn, method, params=None, cb=None):
        """Make a request over the connection"""
        id = self.next_id
        self.next_id = id + 1

        if callable(cb):
            self.results[id] = cb

        await conn.request(method, id, params)

    async def _notify(self, conn, method, params=None):
        """Send a notification over the connection"""
        await conn.notify(method, params)

    async def _request_handler(self, conn, obj):
        """
        Acts on an incoming RPC request.

        This is compatible with batch requests. Note that although we are
        passed in a JSON *object* we must convert it back to a string for the
        JSON RPC response manager. Ths is because we had to parse the incoming
        stream to find delimiters correctly.
        """
        request_str = json.dumps(obj)
        response = jsonrpc.JSONRPCResponseManager.handle(request_str, self.dsp)
        if response and response._id is not None:
            reply = response.json
            await conn.send(reply)

    async def _response_handler(self, obj):
        """Default handler for response objects"""
        if 'id' in obj:
            # Retrieve and remove the reference to the result callback.
            # Note that this is done before checking for errors in the response
            # as we don't want stale callbacks floating around
            cb = self.results.pop(obj['id'], self._result_handler)

        if 'error' in obj:
            self._error_handler(obj['error'])
        elif 'result' in obj:
            cb(obj['result'])
        else:
            self._log.error("Malformed RPC response")

    def _error_handler(self, error):
        """Log errors"""
        self._log.error("RPC error:{}".format(error))

    def _result_handler(self, result):
        """Default to logging successes"""
        # self._log.debug("RPC returned:{}".format(result))
        pass

    @property
    def next_id(self):
        """The next number to use in the 'id' field of a request"""
        return self._next_id.value

    @next_id.setter
    def next_id(self, value):
        """
        Internal representation is a short so that it will overflow.

        Hopefully we shouldn't ever have 65535 pending responses...
        """
        self._next_id = ctypes.c_ushort(value)


class JSONRPCConnection(object):
    """Represents a connection between one RPC peer and another"""

    def __init__(self, handler, reader, writer):
        # Handler is the callback used to handle RPC objects
        self.handler = handler
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')

    def close(self):
        if self.writer:
            self.writer.close()
        self.writer = None
        self.reader = None
        self.handler = None
        self.addr = None

    async def request(self, method, id, params=None):
        """Make an RPC request"""
        request = {'jsonrpc': '2.0', 'id': id,
                   'method': method, 'params': params}
        await self.send_object(request)

    async def notify(self, method, params=None):
        """Send a notification"""
        notification = {'jsonrpc': '2.0', 'method': method, 'params': params}
        await self.send_object(notification)

    async def send_object(self, obj):
        """Send an object"""
        msg = json.dumps(obj, separators=(',', ':'))
        await self.send(msg)

    async def send(self, msg):
        """Send a string without checking if it's valid JSON"""
        # print("{}--> {}".format(self.addr, msg))
        # print("--> Message size: {}".format(len(msg)))
        # Need to protect against connection being closed before the send
        if self.writer is not None:
            self.writer.write(msg.encode())
            # await self.writer.drain()

    async def listen(self):
        """Listens for JSON and calls the handler"""
        async for obj in JSONStreamIterator(self.reader):
            # print("{}<-- {}".format(self.addr, json.dumps(obj)))
            self.handler(self, obj)


class JSONStreamIterator(object):
    """
    Yields JSON objects asynchronously as they are read from a stream.

    Use with e.g. 'async for' loops. May return a list in the case of batch
    requests/responses, so the user must check for this possibility.
    """

    def __init__(self, reader, **kwargs):
        self.reader = reader
        self.buffer = ""
        self.decoder = json.JSONDecoder(**kwargs)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        obj = await self._fetch_object()
        if obj:
            return obj
        else:
            raise StopAsyncIteration

    async def _fetch_object(self):
        obj = None
        while not obj:
            try:
                data = await self.reader.read(2**12)
                # print("*", end='', flush=True)
            except (ConnectionResetError,
                    ConnectionAbortedError, BrokenPipeError) as e:
                # print("got a connection error")
                data = None
            except AttributeError:
                # Reader destroyed before finished
                data = None

            if data:
                msg = data.decode()
                message = self.buffer + msg
                try:
                    obj, end = self.decoder.raw_decode(message)
                except ValueError:
                    # Not enough data, continue reading
                    end = 0
                finally:
                    # Store whatever is left in the buffer
                    self.buffer = message[end:]
            else:
                # EOF or error
                if self.reader is not None:
                    self.reader.feed_eof()
                return None
        # print("!", end='', flush=True)
        return obj
