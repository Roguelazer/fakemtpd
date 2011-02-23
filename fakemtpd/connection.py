import errno
import re
import socket
import sys
import time

from fakemtpd.config import Config
from fakemtpd.signals import Signalable

CLOSED = "closed"
CONNECTED = "connected"

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
        if self._timeout_handle:
            self.io_loop.remove_timeout(self._timeout_handle)
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
SMTP_DISCONNECTED = 0
SMTP_CONNECTED = 1
SMTP_HELO = 2
SMTP_MAIL_FROM = 3
SMTP_DATA = 4

# Command REs
MAIL_FROM_COMMAND=re.compile(r'MAIL\s+FROM:\s*<(.+)>', re.I)
HELO_COMMAND=re.compile(r'^(?:EHLO|HELO)\s+(.*)', re.I)
RCPT_TO_COMMAND=re.compile(r'^RCPT\s+TO:\s*<(.+)>', re.I)
VRFY_COMMAND=re.compile(r'^VRFY (<?.+>?)', re.I)
QUIT_COMMAND=re.compile(r'^QUIT', re.I)
NOOP_COMMAND=re.compile(r'^NOOP', re.I)
RSET_COMMAND=re.compile(r'^RSET', re.I)
DATA_COMMAND=re.compile(r'^DATA', re.I)
HELP_COMMAND=re.compile(r'^HELP', re.I)
EXPN_COMMAND=re.compile(r'^EXPN', re.I)

class SMTPSession(Connection):
    # Timeout before disconecting (in s)
    timeout = 30

    def __init__(self, *args):
        super(SMTPSession, self).__init__(*args)
        self.on_connected(self.print_banner)
        self.on_timeout(self.print_timeout)
        self.config = Config.instance()
        self.remote = ''
        self._state = SMTP_DISCONNECTED
        self._message_state = {}

    def connect(self, *args):
        super(SMTPSession, self).connect(*args)
        self._state = SMTP_CONNECTED

    def print_banner(self):
        self.write("220 %s ESMTP FakeMTPD\r\n" % self.config.hostname)

    def handle_data(self, data):
        rv = False
        if self._state_all(data):
            return
        if self._state == SMTP_CONNECTED:
            rv = self._state_connected(data)
            # Some people don't HELO before sending commands; lame
            if not rv:
                rv = self._state_helo(data)
        elif self._state == SMTP_HELO:
            rv = self._state_helo(data)
        elif self._state == SMTP_MAIL_FROM:
            rv = self._state_mail_from(data)
        elif self._state == SMTP_DATA:
            rv = self._state_data(data)
        if rv == False:
            self.write("503 Commands out of sync\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED

    def _state_all(self, data):
        quit_match = QUIT_COMMAND.match(data)
        rset_match = RSET_COMMAND.match(data)
        noop_match = NOOP_COMMAND.match(data)
        help_match = HELP_COMMAND.match(data)
        if quit_match:
            self.write_and_close("221 2.0.0 Bye\r\n")
            return True
        elif rset_match:
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            self._message_state = {}
            self.write("250 2.0.0 Ok\r\n")
            return True
        elif noop_match:
            self.write("250 2.0.0 Ok\r\n")
            return True
        elif help_match:
            self.write_help()
            return True

    def _state_connected(self, data):
        helo_match = HELO_COMMAND.match(data)
        if helo_match:
            self.remote = helo_match.group(1)
            self.write("250 %s\r\n" % self.config.hostname)
            self._state = SMTP_HELO
            return True
        return False

    def _state_helo(self, data):
        mail_from_match = MAIL_FROM_COMMAND.match(data)
        vrfy_match = VRFY_COMMAND.match(data)
        expn_match = EXPN_COMMAND.match(data)
        if mail_from_match:
            self._message_state = {}
            self._message_state['mail_from'] = mail_from_match.group(1)
            self.write("250 2.1.0 Ok\r\n")
            self._state = SMTP_MAIL_FROM
            return True
        elif vrfy_match:
            self.write("502 5.5.1 VRFY command is disabled\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            return True
        elif expn_match:
            self.write("502 5.5.1 EXPN command is disabled\r\n")
            self._state = SMTP_HELO if self._state >= SMTP_HELO else SMTP_CONNECTED
            return True
        return False

    def _state_mail_from(self, data):
        rcpt_to_match = RCPT_TO_COMMAND.match(data)
        data_match = DATA_COMMAND.match(data)
        mail_from_match = MAIL_FROM_COMMAND.match(data)
        if rcpt_to_match:
            self._message_state.setdefault('rcpt_to', []).append(rcpt_to_match.group(1))
            self.write("554 5.7.1 <%s>: Relay access denied\r\n" % self._message_state['mail_from'])
            self._state = SMTP_HELO
            return True
        elif data_match:
            self._state = SMTP_DATA
            return True
        elif mail_from_match:
            self.write("503 5.5.1 Error: nested MAIL command\r\n")
            self._state = SMTP_HELO
            return True
        return False

    def _state_data(self, data):
        return False

    def print_timeout(self):
        self._timeout_handle = None
        self.write_and_close("421 4.4.2 %s Error: timeout exceeded\r\n" % self.config.hostname)

    def write_help(self):
        self.write("250 Ok\r\n")
        message = [
                "HELO",
                "EHLO",
                "HELP",
                "NOOP",
                "QUIT",
                "MAIL FROM:<address>",
                "RCPT TO:<address>",
                "DATA",
                "VRFY",
                "EXPN",
                "RSET",
        ]
        for msg in message:
            self.write("250 HELP - " + msg + "\r\n")
