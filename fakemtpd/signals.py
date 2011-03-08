import types

# This module is a lot of magic. Like, a lot of magic. The general structure
# is this:
#
# Signalable is the simple interface that the user sees.
#
# _Signals is a metaclass which dynamically builds the on_* and _signal_*
# methods in things that implement it. It does this by calling into the next
# bit, getting back some functions, and then turning them into unbound
# methods.
#
# _handler_factory is where the magic really happens. It makes functions that
# implement the actual logic. It then sets the docstrings and __name__
# (which is important to get the help looking correct).

def _handler_factory(signal_name):
    def on_signal(self, callback, first=False):
        if first:
            self._signal_handlers.setdefault(signal_name, []).insert(0, callback)
        else:
            self._signal_handlers.setdefault(signal_name, []).append(callback)
        return signal_name
    def signal_signal(self, *args):
        for handler in self._signal_handlers.get(signal_name, []):
            handler(*args)
        return signal_name
    on_signal.__doc__ = """Add a callback for signal '%s'
    Arguments:
      callback: The callback function to execute. Should take no args.
""" % signal_name
    signal_signal.__doc__ = """Assert the signal '%s' and notify any registered callbacks"""
    on_signal.__name__ = "on_" + signal_name
    signal_signal.__name__ = "_signal_" + signal_name
    return (on_signal, signal_signal)

class _Signals(type):
    """Metaclass for implementing a basic observer pattern. Creates
    methods on_foo and _signal_foo for all values foo in the Iterable
    cls._signals."""
    def __new__(clsarg, *args, **kwargs):
        cls = super(_Signals, clsarg).__new__(clsarg, *args, **kwargs)
        for signal in cls._signals:
            (on, sig) = _handler_factory(signal)
            setattr(cls, on.__name__, types.UnboundMethodType(on, None, cls))
            setattr(cls, sig.__name__, types.UnboundMethodType(sig, None, cls))
        return cls

class Signalable(object):
    """Inherit from this mixin (and make sure to call super in your __init__
    function) to have basic support for signals (Observer pattern). For every
    string foo in the cls._signals iterable, there will be two methods created:

    * on_foo allows remote objects to subscribe to event foo
    * _signal_foo allows this object to notify on event foo
    """
    __metaclass__ = _Signals
    _signals = []

    def __init__(self):
        self._signal_handlers = {}
