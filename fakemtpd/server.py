import daemon
import errno
import functools
import logging
import grp
import optparse
import os
import pwd
import signal
import socket
import sys
import tornado.ioloop

from fakemtpd.better_lockfile import BetterLockfile
from fakemtpd.config import Config
from fakemtpd.connection import Connection
from fakemtpd.smtpsession import SMTPSession
from fakemtpd.signals import Signalable

class SMTPD(Signalable):
    _signals = ('stop',)

    def __init__(self):
        super(SMTPD, self).__init__()
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
        parser.add_option('--tls-cert', action='store', default=self.config.tls_cert,
                help='Certificate to use for TLS')
        parser.add_option('--tls-key', action='store', default=self.config.tls_key,
                help='Key to use for TLS')
        parser.add_option('--gen-config', action='store_true', default=False,
                help='Print out a config file with all parameters')
        parser.add_option('--smtp-ver', action='store', default=self.config.smtp_ver,
                help='SMTP or ESMTP')
        parser.add_option('-d', '--daemonize', action='store_true', default=self.config.daemonize,
                help='Damonize (must also specify a pid_file)')
        parser.add_option('--pid-file', action='store', default=self.config.pid_file,
                help='PID File')
        parser.add_option('--log-file', action='store', default=self.config.log_file,
                help='File to write logs to (defaults to stdout)')
        (opts, _) = parser.parse_args()
        if bool(opts.daemonize) and not bool(opts.pid_file):
            parser.error('Cannot specify --daemonize xor --pid-file')
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
        return sock

    def create_loop(self, sock):
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
            c = Connection(io_loop, self.config.timeout)
            s = SMTPSession(c)
            logging.debug("Connection from %s", address)
            c.connect(connection, address)
            self.connections.append(s)
            c.on_closed(lambda: self.connections.remove(s))

    def run(self):
        opts = self.handle_opts()
        errors = self.config.merge_opts(opts)
        if errors:
            if errors:
                self.die(errors)
        if opts.gen_config:
            self.config.write()
            sys.exit(0)
        if opts.config_path:
            errors = self.config.read_file(opts.config_path)
            if errors:
                self.die(errors)
        if self.config.log_file:
            try:
                self.log_file = open(self.config.log_file, 'a')
                self.on_stop(self.log_file.close)
            except:
                self.die("Could not access log file %s" % self.config.log_file)
        else:
            self.log_file = None
        if self.config.pid_file:
            pidfile = BetterLockfile(self.config.pid_file)
            pidfile.acquire()
            pidfile.release()
            self.on_stop(pidfile.destroy)
        else:
            pidfile = None
        if self.config.daemonize:
            d = daemon.DaemonContext(files_preserve=[pidfile.file, self.log_file], pidfile=pidfile, stdout=self.log_file, stderr=self.log_file)
            self.on_stop(d.close)
            d.open()
        elif self.config.log_file:
            sys.stdout = self.log_file
            sys.stderr = self.log_file
        signal.signal(signal.SIGINT, lambda signum, frame: self._signal_stop())
        signal.signal(signal.SIGTERM, lambda signum, frame: self._signal_stop())
        self._setup_logging()
        self._run(pidfile)

    def _setup_logging(self):
        fmt = '\t'.join((
            '%(asctime)s',
            socket.gethostname(),
            '%(process)s',
            '%(name)s',
            '%(levelname)s',
            '%(message)s'))
        if self.config.verbose:
            level = logging.DEBUG
        else:
            level = logging.WARNING
        if self.config.log_file:
            logging.basicConfig(stream=self.log_file, format=fmt, level=level)
        else:
            logging.basicConfig(stream=sys.stderr, format=fmt, level=level)

    def _run(self, lockfile=None):
        """Does the actual work of running"""
        if lockfile:
            print >>lockfile.file, os.getpid()
            lockfile.file.flush()
        logging.info("Binding!")
        sock = self.bind()
        logging.info("Bound on port %d", sock.getsockname()[1])
        io_loop = self.create_loop(sock)
        self.maybe_drop_privs()
        self.on_stop(io_loop.stop)
        io_loop.start()
