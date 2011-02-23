def _handler_factory(signal_name):
    def on_signal(self, callback):
        self._signal_handlers.setdefault(signal_name, []).append(callback)
        return signal_name
    def signal_signal(self, *args):
        for handler in self._signal_handlers.get(signal_name, []):
            handler(*args)
        return signal_name
    return (on_signal, signal_signal)

class _Signals(type):
    """Metaclass for implementing a basic observer pattern. Creates
    methods on_foo and _signal_foo for all values foo in the Iterable
    cls._signals."""
    def __new__(clsarg, *args, **kwargs):
        cls = super(_Signals, clsarg).__new__(clsarg, *args, **kwargs)
        for signal in cls._signals:
            (on, sig) = _handler_factory(signal)
            setattr(cls, "on_" + signal, on)
            setattr(cls, "_signal_" + signal, sig)
        return cls

class Signalable(object):
    __metaclass__ = _Signals
    _signals = []

    def __init__(self):
        self._signal_handlers = {}
