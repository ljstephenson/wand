"""
Client peer method
"""
import collections
import ctypes
import json
import jsonrpc
import logging
import queue
import threading
import socket
from . import QtCore, QtNetwork

from wand.common import JSONConfigurable, with_log, get_log_name

__all__ = [
    "RPCPeer",
    "RPCClient",
    "RPCConnection",
]

class RPCPeer(JSONConfigurable):
    """
    Base class that acts as both RPC server and client.
    """
    def __init__(self, *args, **kwargs):
        # JSON configuration initialisation
        super().__init__(*args, **kwargs)
        self.set_up_logger()

        self.connections = {}

        self.dsp = jsonrpc.Dispatcher()
        self.add_rpc_methods()

        self.next_id = 0
        self.results = {}

    def set_up_logger(self):
        """Set up the top level logger"""
        log = logging.getLogger('wand')
        log_name = get_log_name(self.name)
        fmt = logging.Formatter("{asctime}:{levelname}:{name}:{message}", style='{')
        # Use 10kib log files, with 5 backups
        fh = logging.handlers.RotatingFileHandler(log_name, maxBytes=100*1024, backupCount=5)
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

    def handle_rpc(self, conn, obj):
        """
        Triage an RPC packet according to whether it is a request or response.
        """
        if isinstance(obj, dict) and 'method' in obj:
            self._request_handler(conn, obj)
        else:
            self._response_handler(obj)

    def close_connections(self):
        while self.connections:
            (_, conn) = self.connections.popitem()
            conn.close()

    # -------------------------------------------------------------------------
    # Internal functions
    #
    def request(self, conn, method, params=None, cb=None):
        """Make a request over the connection"""
        id = self.next_id
        self.next_id = id + 1

        if callable(cb):
            self.results[id] = cb

        conn.request(method, id, params)

    def notify(self, conn, method, params=None):
        """Send a notification over the connection"""
        conn.notify(method, params)

    def _request_handler(self, conn, obj):
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
            conn.send(reply)

    def _response_handler(self, obj):
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
        #self._log.debug("RPC returned:{}".format(result))
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


@with_log
class RPCClient(RPCPeer):
    """Handles making the connections as well"""
    def startup(self):
        self.running = True
        for s in self.servers:
            self.server_connect(s)
        self._log.info("Ready")

    def shutdown(self):
        self.running = False
        self.close_connections()
        self._log.info("Shutdown finished")

    def server_connect(self, server):
        s = self.servers.get(server)
        sock = QtNetwork.QTcpSocket()

        def connected():
            s.connected = True
            self._log.info("Connected to {}".format(server))

        def disconnected():
            s.connected = False
            self._log.info("Disconnected from {}".format(server))

        sock.connected.connect(connected)
        sock.disconnected.connect(disconnected)
        conn = RPCConnection(self.handle_rpc, sock)

        sock.connectToHost(*s.addr)

        self.connections[s.addr] = conn
        self.conns_by_s[server] = conn
        for c in s.channels:
            self.conns_by_c[c] = conn


class RPCConnection(QtCore.QObject):
    """Represents a connection between one RPC peer and another"""
    msgReady = QtCore.pyqtSignal(str)
    def __init__(self, handler, sock):
        super().__init__()
        self.handler = handler
        self.sock = sock
        self.buf = ""
        self.decoder = json.JSONDecoder()
        self.sock.readyRead.connect(self.get_listen())

        self.worker_t = QtCore.QThread()
        self.worker = Decoder()
        self.worker.moveToThread(self.worker_t)
        self.msgReady.connect(self.worker.decode)
        self.worker.jsonReady.connect(self.handle)

        self.worker_t.start()

    def close(self):
        if self.sock:
            self.sock.close()
        self.sock = None
        self.handler = None

    def request(self, method, id, params=None):
        """Make an RPC request"""
        request = {'jsonrpc':'2.0', 'id':id, 'method':method, 'params':params}
        self.send_object(request)

    def notify(self, method, params=None):
        """Send a notification"""
        notification = {'jsonrpc':'2.0', 'method':method, 'params':params}
        self.send_object(notification)

    def send_object(self, obj):
        """Send an object"""
        msg = json.dumps(obj, separators=(',', ':'))
        self.send(msg)

    def send(self, msg):
        """Send a string without checking if it's valid JSON"""
        if self.sock is not None:
            self.sock.write(msg.encode())

    def get_listen(self):
        def listen():
            """Called when data is available"""
            #print("hello from thread {}".format(QtCore.QThread.currentThreadId()))
            obj = None
            data = self.sock.read(self.sock.bytesAvailable())
            self.msgReady.emit(data.decode())
            #if data:
            #    message = self.buf + data.decode()
            #    try:
            #        obj, end = self.decoder.raw_decode(message)
            #    except ValueError:
            #        # Not enough data, continue reading
            #        end = 0
            #    finally:
            #        # Store whatever is left in the buffer
            #        self.buf = message[end:]

            #if obj:
            #    self.handler(self, obj)
        return listen

    def handle(self, obj):
        self.handler(self, obj)


class Decoder(QtCore.QObject):
    """Worker to decode data into meaningful JSON objects"""
    jsonReady = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self.buf = ""
        self.decoder = json.JSONDecoder()

    def decode(self, msg):
        #print("hello from thread {}".format(QtCore.QThread.currentThreadId()))
        if msg:
            message = self.buf + msg
            try:
                obj, end = self.decoder.raw_decode(message)
            except ValueError:
                # Not enough data, continue reading
                end = 0
            finally:
                # Store whatever is left in the buffer
                self.buf = message[end:]

        if obj:
            self.jsonReady.emit(obj)


# class ThreadClient(RPCPeer):


# class ThreadConnection(threading.Thread):
#     def __init__(self, cmd_q=None, reply_q=None):
#         super().__init__()
#         self.cmd_q = cmd_q or Queue.Queue()
#         self.reply_q = reply_q or Queue.Queue()
#         self.alive = threading.Event()
#         self.alive.set()
#         self.sock = None

#     def run(self):
#         while self.alive.isSet():
#             try:
#                 cmd = self.cmd_q.get(True, 0.1)
