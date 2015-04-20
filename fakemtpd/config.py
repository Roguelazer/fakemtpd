from __future__ import with_statement

import copy
import itertools
import os.path
import socket
import ssl
import yaml


def _param_getter_factory(parameter):
    def f(self):
        return self._config[parameter]
    f.__name__ = parameter
    return f


class _ParamsAsProps(type):
    """Create properties on the classes that apply this for everything
    in cls._parameters which read out of self._config.

    Cool fact: you can override any of these properties by just defining
    your own with the same name. Just like if they were statically defined!"""
    def __new__(clsarg, name, bases, d):
        cls = super(_ParamsAsProps, clsarg).__new__(clsarg, name, bases, d)
        for parameter in cls._parameters.iterkeys():
            if parameter not in d:
                f = _param_getter_factory(parameter)
                setattr(cls, parameter, property(f))
        return cls


class Config(object):
    """Singleton class for implementing configuration. Use the instance
    method to get handles to it. Supports loading options from both objects
    and YAML files."""

    __metaclass__ = _ParamsAsProps

    """Allowable logging methods"""
    logging_methods = ('stderr', 'file', 'syslog')

    """Allowable SMTP versions"""
    smtp_versions = ('SMTP', 'ESMTP')

    """Known SSL versions"""
    ssl_versions = ('ssl2', 'ssl3', 'ssl23', 'tls1')

    # Parameters and their defaults. All of these can be overridden
    # via the YAML configuration. Some can also be overridden via
    # command-line options
    _parameters = {
        'port': 25,
        'address': '0.0.0.0',
        'user': None,
        'group': None,
        'hostname': socket.gethostname(),
        'verbose': 0,
        'mtd': 'FakeMTPD',
        'smtp_ver': 'SMTP',
        'tls_cert': None,
        'tls_key': None,
        'timeout': 30,
        'daemonize': False,
        'pid_file': None,
        'log_file': None,
        'logging_method': 'stderr',
        'ssl_version': 'ssl23',
        'syslog_host': 'localhost',
        'syslog_port': 514,
        'syslog_domain_socket': None,
    }

    def __init__(self):
        """Initialize the object. You should always use instance()"""
        self._config = copy.copy(self._parameters)

    @classmethod
    def instance(cls):
        """Get a handle to the Config singleton"""
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def merge_opts(self, opts):
        """Merge in options from an object like the one returned by an
        optparse OptionParser (i.e., an object with attributes named after the
        options."""
        self.opts = opts
        for opt in self._parameters:
            if getattr(opts, opt, None) is not None:
                self._config[opt] = getattr(opts, opt)
        return self._validate()

    def read_file(self, path):
        """Merge in options from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
            for key in data:
                if key in self._parameters:
                    self._config[key] = data[key]
        return self._validate()

    def write(self):
        """Writes the current config to stdout, as YAML"""
        print yaml.dump(self._config, default_flow_style=False),

    def _validate(self):
        if self._config['pid_file'] and not os.path.isabs(self._config['pid_file']):
            return "PID file path must be absolute"
        if self._config['log_file'] and not os.path.isabs(self._config['log_file']):
            return "Log file path must be absolute"
        if self._config['smtp_ver'] not in ('SMTP', 'ESMTP'):
            return "smtp_ver must be in ('SMTP', 'ESMTP')"
        if self._config['logging_method'] not in self.logging_methods:
            return "logging_method must be in (%s)" % ",".join(self.logging_methods)
        if bool(self._config['tls_cert']) ^ bool(self._config['tls_key']):
            return "Cannot specify a certificate without a key, or vice versa"
        if self._config['ssl_version'] not in self.ssl_versions:
            return "Allowed values for ssl_version are (%s), got '%s'" % (','.join(("'" + s + "'") for s in self.ssl_versions), self._config['ssl_version'])
        if self._config['tls_cert']:
            self._config['smtp_ver'] = 'ESMTP'
        if bool(self._config['daemonize']) and not bool(self._config['pid_file']):
            return 'Cannot specify to daemonize without a pid-file, or vice versa'
        if self._config['logging_method'] == 'file':
            if not self._config['log_file']:
                return "cannot specify logging method 'file' without a log file"
        if self._config['logging_method'] == 'syslog':
            if not self._config['syslog_domain_socket']:
                if bool(self._config['syslog_host']) ^ bool(self._config['syslog_port']):
                    return "must specify both a syslog host and a port"
        return None

    def merge_sock(self, sock):
        self._config['port'] = int(sock.getsockname()[1])
        self._config['address'] = sock.getsockname()[0]

    @property
    def port(self):
        return int(self._config['port'])

    @property
    def ssl_version(self):
        parts = ["".join(b) for _, b in itertools.groupby(
            self._config['ssl_version'], str.isdigit
        )]
        attr = 'PROTOCOL_%sV%s' % (parts[0], parts[1])
        return getattr(ssl, attr)

    @property
    def syslog_connection(self):
        if self._config.get('logging_method', '') != 'syslog':
            return None
        elif self._config.get('syslog_domain_socket'):
            return self._config['syslog_domain_socket']
        else:
            return (self._config['syslog_host'], self._config['syslog_port'])

    def __contains__(self, attr):
        """x.__contains__(foo) <==> foo in x"""
        return attr in self._config

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return '<Config %r>' % self._config

    def __str__(self):
        """x.__str__() <==> str(x)"""
        return '<Config %s>' % self._config
