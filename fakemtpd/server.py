import daemon
import errno
import functools
import lockfile
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
    _signals = ('stop', 'hup')

    def __init__(self):
        super(SMTPD, self).__init__()
        self.connections = []
        self.config = Config.instance()
        self._log_fmt = '\t'.join((
            '%(asctime)s',
            socket.gethostname(),
            '%(process)s',
            '%(name)s',
            '%(levelname)s',
            '%(message)s'))

    def handle_opts(self):
        parser = optparse.OptionParser()
        parser.add_option('-c', '--config-path', action='store', default=None,
                help='Path to a YAML configuration file (overridden by any conflicting args)')
        parser.add_option('-p', '--port', dest='port', action='store', type=int, default=self.config.port,
                help='Port to listen on (default %default)')
        parser.add_option('-H', '--hostname', dest='hostname', action='store', default=self.config.hostname,
                help='Hostname to report as (default %default)')
        parser.add_option('-B', '--bind', dest='address', action='store', default=self.config.address,
                help='Address to bind to (default "%default")')
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
        return opts

    def die(self, message):
        print >>sys.stderr, message
        sys.exit(1)

    def get_uid_gid(self):
        uid = None
        gid = None
        if self.config.group:
            try:
                data = grp.getgrnam(self.config.group)
                gid = data.gr_gid
            except KeyError:
                self.die('Group %s not found, unable to drop privs, aborting' % self.config.group)
        if self.config.user:
            try:
                data = pwd.getpwnam(self.config.user)
                uid = data.pw_uid
            except KeyError:
                self.die('User %s not found, unable to drop privs, aborting' % self.config.user)
        return (uid, gid)

    def maybe_drop_privs(self, uid, gid):
        if self.config.group and gid:
            os.setgid(gid)
        if self.config.user and uid:
            os.setuid(uid)

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

    def run(self, handle_opts=True):
        if handle_opts:
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
        (uid, gid) = self.get_uid_gid()
        if self.config.log_file:
            self._check_create_log_file(uid, gid)
            try:
                self.log_file = open(self.config.log_file, 'a')
                self.on_stop(lambda: self.log_file.flush())
                self.on_stop(lambda: self.log_file.close())
                self.on_hup(lambda: self._reopen_log_files())
            except IOError, e:
                self.die("Could not access log file %s" % self.config.log_file)
        else:
            self.log_file = None
        if self.config.pid_file:
            pidfile = BetterLockfile(os.path.realpath(self.config.pid_file))
            try:
                pidfile.acquire()
            except lockfile.AlreadyLocked:
                self.die("%s is already locked; another instance running?" % self.config.pid_file)
            pidfile.release()
        else:
            pidfile = None
        # Do this before daemonizing so that the user can see any errors
        # that may occur
        sock = self.bind()
        self.config.merge_sock(sock)
        if self.config.daemonize:
            d = daemon.DaemonContext(files_preserve=[pidfile.file, self.log_file, sock], pidfile=pidfile, stdout=self.log_file, stderr=self.log_file)
            self.on_stop(d.close)
            d.open()
        elif self.config.log_file:
            os.dup2(self.log_file.fileno(), sys.stdout.fileno())
            os.dup2(self.log_file.fileno(), sys.stderr.fileno())
        if self.config.pid_file:
            self.on_stop(pidfile.destroy)
        signal.signal(signal.SIGINT, lambda signum, frame: self._signal_stop())
        signal.signal(signal.SIGTERM, lambda signum, frame: self._signal_stop())
        signal.signal(signal.SIGHUP, lambda signum, frame: self._signal_hup())
        # This needs to happen after daemonization
        self._setup_logging()
        logging.info("Bound on port %d", self.config.port)
        if pidfile:
            print >>pidfile.file, os.getpid()
            pidfile.file.flush()
        io_loop = self.create_loop(sock)
        self.maybe_drop_privs(uid, gid)
        self.on_stop(io_loop.stop)
        logging.getLogger().handlers[0].flush()
        self._start(io_loop)

    def _check_create_log_file(self, uid, gid):
        """Create the log file if necessary, and give it the right owner"""
        if not os.path.exists(self.config.log_file):
            if not os.path.exists(os.path.realpath(os.path.dirname(self.config.log_file))):
                self.die("[setting up logging] No such directory '%s'" % os.path.realpath(os.path.dirname(self.config.log_file)))
            try:
                f = open(self.config.log_file, "w")
                if uid:
                    os.fchown(f.fileno(), uid, -1)
                if gid:
                    os.fchown(f.fileno(), -1, gid)
                f.close()
            except IOError:
                self.die("Cannot create file %s" % self.config.log_file)

    def _setup_logging(self):
        if self.config.verbose:
            level = logging.DEBUG
        else:
            level = logging.INFO
        if self.config.log_file:
            logging.getLogger().handlers = []
            logging.basicConfig(filename=self.config.log_file, format=self._log_fmt, level=level)
        else:
            logging.basicConfig(stream=sys.stderr, format=self._log_fmt, level=level)

    def _reopen_log_files(self):
        """Handle a HUP to reload logging"""
        if self.config.log_file:
            logging.info("re-opening log files")
            if self.config.verbose:
                level = logging.DEBUG
            else:
                level = logging.INFO
            logging.getLogger().handlers = []
            logging.basicConfig(filename=self.config.log_file, format=self._log_fmt, level=level)
            self.log_file.close()
            self.log_file = open(self.config.log_file, 'a')

    def _start(self, io_loop):
        """Broken out so I can mock this in the tests better"""
        io_loop.start()
        logging.info("Shutting down")
        logging.shutdown()
