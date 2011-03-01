import errno
import select
import socket
import sys
import ssl
import time

import tornado.iostream

from fakemtpd.signals import Signalable

CLOSED = "closed"
CONNECTED = "connected"

class Connection(Signalable):
    """Wrapper around tornado.iostream.IOStream"""
    _signals = ["connected", "closed", "timeout", "data"]
    timeout = -1

    def __init__(self, io_loop):
        super(Connection, self).__init__()
        self.io_loop = io_loop
        self.state = CLOSED
        self._timeout_handle = None

    def connect(self, sock, address):
        self.sock = sock
        self.address = address
        self.sock.setblocking(0)
        self.state = CONNECTED
        self.stream = tornado.iostream.IOStream(self.sock, io_loop=self.io_loop)
        self.on_timeout(self._timeout)
        self._set_timeout()
        self._signal_connected()
        self._read()

    def starttls(self, **ssl_options):
        assert self.state == CONNECTED
        self.sock = ssl.wrap_socket(self.sock, server_side=True,
                do_handshake_on_connect=False, **ssl_options)
        self.io_loop.remove_handler(self.sock.fileno())
        self.stream = tornado.iostream.SSLIOStream(self.sock, io_loop = self.io_loop)
        print "Made SSLIOStream"
        self.stream._do_ssl_handshake()
        self._read()

    def _timeout(self):
        self._timeout_handle = None

    def _set_timeout(self):
        if self.timeout > 0:
            if self._timeout_handle:
                self.io_loop.remove_timeout(self._timeout_handle)
            self._timeout_handle = self.io_loop.add_timeout(time.time() + self.timeout, self._signal_timeout)

    def close(self):
        self.state = CLOSED
        self.stream.close()
        if self._timeout_handle:
            self.io_loop.remove_timeout(self._timeout_handle)
        self._signal_closed()

    def _handle_data(self, data):
        self._signal_data(data)
        self._read()

    def _read(self):
        self.stream.read_until("\n", self._handle_data)

    def write(self, data, callback=None):
        """Write some data to the connection (asynchronously)"""
        self.stream.write(data, callback)
        self._set_timeout()
