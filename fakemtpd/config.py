from __future__ import with_statement

import copy
import new
import socket
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

    # Parameters and their defaults. All of these can be overridden
    # via the YAML configuration. Some can also be overridden via
    # command-line options
    _parameters = {
            'port': 25,
            'address': '',
            'user': None,
            'group': None,
            'hostname': socket.gethostname(),
            'verbose': False,
            'mtd': 'FakeMTPD',
            'smtp_ver': 'SMTP',
            'tls_cert': None,
            'tls_key': None,
            'timeout': 30,
            'daemonize': False,
            'pid_file': None,
            'log_file': None,
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
        if self._config['smtp_ver'] not in ('SMTP', 'ESMTP'):
            return "smtp_ver must be in ('SMTP', 'ESMTP')"
        if bool(self._config['tls_cert']) ^ bool(self._config['tls_key']):
            return "Cannot specify a certificate without a key, or vice versa"
        if self._config['tls_cert']:
            self._config['smtp_ver'] = 'ESMTP'
        if bool(self._config['daemonize']) and not bool(self._config['pid_file']):
            return 'Cannot specify to daemonize without a pid-file, or vice versa'
        return None

    @property
    def port(self):
        return int(self._config['port'])

    def __contains__(self, attr):
        """x.__contains__(foo) <==> foo in x"""
        return attr in self._config

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return '<Config %r>' % self._config

    def __str__(self):
        """x.__str__() <==> str(x)"""
        return '<Config %s>' % self._config
