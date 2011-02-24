from __future__ import with_statement

import copy
import new
import socket
import yaml

class Config(object):
    """Singleton class for implementing configuration. Use the instance
    method to get handles to it. Supports loading options from both objects
    and YAML files."""

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
    }

    def __new__(cls, *args, **kwargs):
        # MAGIC
        # Creates properties corresponding to everything in self.parameter
        # which doesn't already have a property
        obj = super(Config, cls).__new__(cls, *args, **kwargs)
        for parameter in cls._parameters.iterkeys():
            if parameter not in obj.__dict__:
                setattr(cls, parameter, property(lambda self: self._config[parameter]))
        return obj

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

    def read_file(self, path):
        """Merge in options from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
            for key in data:
                if key in self._parameters:
                    self._config[key] = data[key]

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
