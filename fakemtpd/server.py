import errno
import functools
import grp
import optparse
import os
import pwd
import signal
import socket
import sys
import tornado.ioloop

from fakemtpd.config import Config
from fakemtpd.connection import Connection
from fakemtpd.smtpsession import SMTPSession

class SMTPD(object):
    def __init__(self):
        self.connections = []
        self.config = Config.instance()

    def handle_opts(self):
        parser = optparse.OptionParser()
        parser.add_option('-c', '--config-path', action='store', default=None,
                help='Path to a YAML configuration file (overridden by any conflicting args)')
        parser.add_option('-p', '--port', dest='port', action='store', type=int, default=self.config.port,
                help='Port to listen on (default %default)')
        parser.add_option('-H', '--hostname', dest='hostname', action='store', default=self.config.hostname,
                help='Hostname to report as (default %default)')
        parser.add_option('-B', '--bind', dest='address', action='store', default=self.config.address,
                help='Address to bind to (default "%default"')
        parser.add_option('-v', '--verbose', action='store_true', default=self.config.verbose,
                help='Be more verbose')
        parser.add_option('--cert', action='store', default=self.config.cert,
                help='Certificate to use for TLS')
        parser.add_option('--gen-config', action='store_true', default=False,
                help='Print out a config file with all parameters')
        parser.add_option('--smtp-ver', action='store', default=self.config.smtp_ver,
                help='SMTP or ESMTP')
        (opts, _) = parser.parse_args()
        return opts

    def die(self, message):
        print >>sys.stderr, message
        sys.exit(1)
    
    def maybe_drop_privs(self):
        if self.config.group:
            try:
                data = grp.getgrnam(self.config.group)
                os.setegid(data.gr_gid)
            except KeyError:
                self.die('Group %s not found, unable to drop privs, aborting' % self.config.group)
        if self.config.user:
            try:
                data = pwd.getpwnam(self.config.user)
                os.seteuid(data.pw_uid)
            except KeyError:
                self.die('User %s not found, unable to drop privs, aborting' % self.config.user)

    def bind(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(0)
        sock.bind((self.config.address, self.config.port))
        sock.listen(128)

        io_loop = tornado.ioloop.IOLoop.instance()
        new_connection_handler = functools.partial(self.connection_ready, io_loop, sock)
        io_loop.add_handler(sock.fileno(), new_connection_handler, io_loop.READ)
        return io_loop

    def connection_ready(self, io_loop, sock, fd, events):
        while True:
            try:
                connection, address = sock.accept()
            except socket.error, e:
                if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                return
            c = Connection(io_loop)
            s = SMTPSession(c)
            c.connect(connection, address)
            self.connections.append(s)
            c.on_closed(lambda: self.connections.remove(c))

    def run(self):
        opts = self.handle_opts()
        errors = self.config.merge_opts(opts)
        if errors:
            print errors
            sys.exit(1)
        if opts.gen_config:
            self.config.write()
            sys.exit(0)
        if opts.config_path:
            errors = self.config.read_file(opts.config_path)
            if errors:
                print errors
                sys.exit(1)
        io_loop = self.bind()
        self.maybe_drop_privs()
        signal.signal(signal.SIGINT, lambda signum, frame: io_loop.stop())
        io_loop.start()
