from __future__ import absolute_import

import functools
import os
import signal
import socket

import tornado.ioloop

from testify import TestCase, assert_equal, run

import fakemtpd.server


class PartialMockServer(fakemtpd.server.SMTPD):
    def create_loop(self, sock):
        self._saved_socket = sock
        return self

    def _start(self, *args):
        pass

    def stop(self):
        if hasattr(self, '_io_loop'):
            self._io_loop.stop()

    def _actually_start(self):
        io_loop = tornado.ioloop.IOLoop.instance()
        new_connection_handler = functools.partial(self.connection_ready, io_loop, self._saved_socket)
        io_loop.add_handler(self._saved_socket.fileno(), new_connection_handler, io_loop.READ)
        self._io_loop = io_loop
        io_loop.start()


class ServerManager(object):
    def __init__(self):
        self.server = PartialMockServer()
        self.server.config.read_file(os.path.join(os.path.dirname(__file__), 'data', 'mock_config.yaml'))
        self.server.run(handle_opts=False)

    def __enter__(self):
        self.pid = os.fork()
        if self.pid == 0:
            self.server._actually_start()
            os._exit(0)
        else:
            return self.server.config

    def __exit__(self, *args):
        os.kill(self.pid, signal.SIGTERM)


class IntegrationTest(TestCase):
    def test_construct(self):
        self.server = PartialMockServer()
        self.server.config.read_file(os.path.join(os.path.dirname(__file__), 'data', 'mock_config.yaml'))
        self.server.run(handle_opts=False)

    def test_listen(self):
        with ServerManager() as config:
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
            sock.connect((config.address, config.port))
            sock.close()

    def test_helo(self):
        with ServerManager() as config:
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
            sock.connect((config.address, config.port))
            data = sock.recv(1024)
            assert_equal(b"220 mock_hostname SMTP FakeMTPD\r\n", data)
            sock.send(b"HELO google.com\r\n")
            data = sock.recv(1024)
            assert_equal(b"250 mock_hostname\r\n", data)
            sock.send(b"QUIT")
            sock.close()

    def test_ehlo(self):
        with ServerManager() as config:
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
            sock.connect((config.address, config.port))
            data = sock.recv(1024)
            assert_equal(b"220 mock_hostname SMTP FakeMTPD\r\n", data)
            sock.send(b"EHLO google.com\r\n")
            data = sock.recv(1024)
            assert_equal(b"250-mock_hostname\r\n", data)
            sock.send(b"QUIT")
            sock.close()


if __name__ == "__main__":
    run()
