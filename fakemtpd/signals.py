class Signals(type):
    """Metaclass for implementing a basic observer pattern. Creates
    methods on_foo and _signal_foo for all values foo in the Iterable
    cls._signals."""
    def __init__(cls, name, bases, d):
        super(Signals, cls).__init__(name, bases, d)
        cls.__signal_handlers = {}
        for signal in cls._signals:
            setattr(cls, "on_" + signal, lambda self, callback: self.__signal_handlers.setdefault(signal, []).append(callback))
            setattr(cls, "_signal_" + signal, lambda self: map(lambda x: x(), self.__signal_handlers.get(signal, [])))
