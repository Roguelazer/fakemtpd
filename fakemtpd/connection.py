import errno
import socket
import sys

CLOSED = "closed"
CONNECTED = "connected"

class Connection(object):
    def __init__(self, smtpd, io_loop):
        self.smtpd = smtpd
        self.io_loop = io_loop
        self._data = []
        self.state = CLOSED

    def connect(self, sock, address):
        self.sock = sock
        self.address = address
        self.sock.setblocking(0)
        self.state = CONNECTED
        self.io_loop.add_handler(self.sock.fileno(), self.handler, self.io_loop.READ)

    def close(self):
        self.state = CLOSED
        self.io_loop.remove_handler(self.sock.fileno())
        self.sock.close()
        self.smtpd.closed(self)

    def handler(self, fd, events):
        if events & self.io_loop.READ:
            self.read_data()
        elif events & self.io_loop.WRITE:
            self.write_data()

    def handle_data(self, data):
        sys.stdout.write(data)

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
        self.io_loop.update_handler(self.sock.fileno(), io_loop.READ)

