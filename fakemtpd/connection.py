import errno
import re
import socket
import sys
import time

from fakemtpd.config import Config
from fakemtpd.signals import Signalable

CLOSED = "closed"
CONNECTED = "connected"

MAIL_FROM_COMMAND=re.compile(r'')
HELO_COMMAND=re.compile(r'^HELO\s+(.*)')

class Connection(Signalable):
    _signals = ["connected", "closed", "timeout"]
    timeout = -1

    def __init__(self, io_loop):
        super(Connection, self).__init__()
        self.io_loop = io_loop
        self._data = []
        self.state = CLOSED

    def connect(self, sock, address):
        self.sock = sock
        self.address = address
        self.sock.setblocking(0)
        self.state = CONNECTED
        self.io_loop.add_handler(self.sock.fileno(), self.handler, self.io_loop.READ)
        self._timeout_handle = None
        self._set_timeout()
        self._signal_connected()
        self._closing = False

    def _signal_timeout(self):
        self._timeout_handle = None
        super(Connection, self)._signal_timeout()

    def _set_timeout(self):
        if self.timeout > 0:
            if self._timeout_handle:
                self.io_loop.remove_timeout(self._timeout_handle)
            self._timeout_handle = self.io_loop.add_timeout(time.time() + self.timeout, self._signal_timeout)

    def close(self):
        self.state = CLOSED
        self.io_loop.remove_handler(self.sock.fileno())
        self.sock.close()
        self._signal_closed()

    def handler(self, fd, events):
        if events & self.io_loop.READ:
            self.read_data()
        elif events & self.io_loop.WRITE:
            self.write_data()

    def handle_data(self, data):
        self._set_timeout()

    def write(self, data):
        self._data.append(data)
        self.io_loop.update_handler(self.sock.fileno(), self.io_loop.READ|self.io_loop.WRITE)
        self._set_timeout()

    def write_and_close(self, data):
        self._data.append(data)
        self.io_loop.update_handler(self.sock.fileno(), self.io_loop.READ|self.io_loop.WRITE)
        self._closing = True

    def read_data(self):
        data = []
        while True:
            try:
                this_data = self.sock.recv(4096)
                if len(this_data) == 0:
                    self.close()
                    return
                data.append(this_data)
            except socket.error, e:
                if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                break
        self.handle_data(''.join(data))
    
    def write_data(self):
        while self._data:
            try:
                sent = self.sock.send(self._data[0])
                if sent == len(self._data[0]):
                    self._data.pop(0)
                else:
                    self._data = self._data[sent:]
            except socket.error, e:
                if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                return
        self.io_loop.update_handler(self.sock.fileno(), self.io_loop.READ)
        if self._closing:
            self.close()

# SMTP States
SMTP_CONNECTED = 1
SMTP_HELO = 2

class SMTPSession(Connection):
    # Timeout before disconecting (in s)
    timeout = 30

    def __init__(self, *args):
        super(SMTPSession, self).__init__(*args)
        self.on_connected(self.print_banner)
        self.on_timeout(self.print_timeout)
        self.config = Config.instance()
        self.remote = ''
        self._state = SMTP_CONNECTED

    def print_banner(self):
        self.write("220 %s ESMTP FakeMTPD\r\n" % self.config.hostname)

    def handle_data(self, data):
        helo_match = HELO_COMMAND.match(data)
        if helo_match:
            self.remote = helo_match.group(1)
            self.write("250 %s\r\n" % self.config.hostname)
            self.state = SMTP_HELO

    def print_timeout(self):
        self.write_and_close("421 4.4.2 %s Error: timeout exceeded\r\n" % self.config.hostname)
