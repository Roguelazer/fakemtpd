import errno
import socket
import sys

class Connection(object):
    def __init__(self, io_loop, sock, address):
        self.io_loop = io_loop
        self.sock = sock
        self.address = address
        self._data = []

    def add_handler(self, io_loop):
        io_loop.add_handler(self.sock.fileno(), self.handler, io_loop.READ)

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

