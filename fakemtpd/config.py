from __future__ import with_statement

import yaml

class Config(object):
    parameters = ['port', 'address', 'user', 'group', 'hostname']

    def __init__(self):
        self._config = {}

    @classmethod
    def instance(cls, opts=None):
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        if opts:
            cls._instance.merge_opts(opts)
        return cls._instance

    def merge_opts(self, opts):
        self.opts = opts
        for opt in self.parameters:
            if getattr(opts, opt, None) is not None:
                self._config[opt] = getattr(opts, opt)

    def read_config(self, path):
        with open(path) as f:
            data = yaml.safe_load(f)
            for key in parameters:
                if key in data:
                    self._config[key] = data[key]

    @property
    def port(self):
        return int(self._config['port'])

    def __getattr__(self, attr):
        if attr not in self.parameters:
            raise AttributeError
        return self._config[attr]

    def __contains__(self, attr):
        return attr in self._config

    def __repr__(self):
        return repr(self._config)
