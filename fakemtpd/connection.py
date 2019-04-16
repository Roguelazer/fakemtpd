import functools
import logging
import ssl
import time

import tornado.iostream

from fakemtpd.signals import Signalable

CLOSED = "closed"
CONNECTED = "connected"

log = logging.getLogger("connection")


class Connection(Signalable):
    """Wrapper around tornado.iostream.IOStream"""
    _signals = ["connected", "closed", "timeout", "data"]

    def __init__(self, io_loop, timeout=-1):
        super(Connection, self).__init__()
        self.io_loop = io_loop
        self.state = CLOSED
        self.timeout = timeout
        self._timeout_handle = None

    @staticmethod
    def _format_address(address):
        if isinstance(address, tuple) and len(address) == 2:
            return "[%s]:%d" % (address[0], address[1])
        else:
            return "%s" % address

    def connect(self, sock, address):
        log.info("Starting connection from %s", self._format_address(address))
        self.sock = sock
        self.address = address
        self.sock.setblocking(0)
        self.state = CONNECTED
        self.stream = tornado.iostream.IOStream(self.sock, io_loop=self.io_loop)
        self.stream.set_close_callback(self.close)
        self.on_timeout(self._timeout, first=True)
        self._set_timeout()
        self._signal_connected()
        self._read()

    def starttls(self, **ssl_options):
        assert self.state == CONNECTED
        log.debug("starting TLS session")
        self.sock = ssl.wrap_socket(
            self.sock, server_side=True,
            do_handshake_on_connect=False,
            **ssl_options
        )
        self.io_loop.remove_handler(self.sock.fileno())
        self.stream = tornado.iostream.SSLIOStream(self.sock, io_loop=self.io_loop)
        self.stream.set_close_callback(self.close)
        self._read()

    def _timeout(self):
        self._timeout_handle = None

    def _set_timeout(self):
        if self.timeout > 0:
            if self._timeout_handle:
                self.io_loop.remove_timeout(self._timeout_handle)
            self._timeout_handle = self.io_loop.add_timeout(time.time() + self.timeout, self._signal_timeout)

    def close(self):
        if self.state == CLOSED:
            return
        self.state = CLOSED
        if not self.stream.closed():
            self.stream.close()
        if self._timeout_handle:
            self.io_loop.remove_timeout(self._timeout_handle)
            self._timeout_handle = None
        self._signal_closed()
        log.info("Connection from %s closed", self._format_address(self.address))

    def _handle_data(self, data):
        self._signal_data(data)
        self._read()

    def _read(self):
        # Add this callback in a roundabout way to work around a regression
        # in Tornado 1.2 that causes stack overflows if you do this the
        # naive way
        self.stream.io_loop.add_callback(functools.partial(self.stream.read_until, "\n", self._handle_data))
        self._set_timeout()

    def write(self, data, callback=None, st=True):
        """Write some data to the connection (asynchronously)"""
        self.stream.write(data, callback)
        if st:
            self._set_timeout()
