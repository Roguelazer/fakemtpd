from __future__ import absolute_import

import testify
from testify import TestCase, assert_equal, setup, teardown, run

from fakemtpd.signals import _Signals, Signalable

class SignalClass(Signalable):
    _signals = ["foo", "bar"]

    def send(self):
        self._signal_foo()
        self._signal_bar()

class FancySignalClass(SignalClass):
    def __init__(self):
        super(FancySignalClass, self).__init__()
        self.foo_signaled = Counter()

class Counter(object):
    def __init__(self, start=0):
        self.val = start
    
    def incr(self):
        self.val += 1

    def decr(self):
        self.val -= 1

    def __eq__(self, other):
        return self.val == other

    def __repr__(self):
        return "<Counter=%d>" % self.val

class SignalableTestCase(TestCase):
    def test_full(self):
        obj = SignalClass()
        foo_ran = Counter()
        bar_ran = Counter()
        foo_callback = lambda: foo_ran.incr()
        bar_callback = lambda: bar_ran.incr()
        assert_equal(obj.on_foo(foo_callback), "foo")
        assert_equal(obj.on_bar(bar_callback), "bar")
        obj.send()
        assert_equal(foo_ran, 1)
        assert_equal(bar_ran, 1)

    def test_distinct(self):
        obj = SignalClass()
        foo_ran = Counter()
        bar_ran = Counter()
        foo_callback = lambda: foo_ran.incr()
        assert_equal(obj.on_foo(foo_callback), "foo")
        obj.send()
        assert_equal(foo_ran, 1)
        assert_equal(bar_ran, 0)
    
    def test_per_object_not_per_class(self):
        obj1 = SignalClass()
        obj2 = SignalClass()
        foo_ran = Counter()
        bar_ran = Counter()
        bar_callback = lambda: bar_ran.incr()
        assert_equal(obj1.on_bar(bar_callback), "bar")
        obj1.send()
        obj2.send()
        assert_equal(foo_ran, 0)
        assert_equal(bar_ran, 1)

if __name__ == "__main__":
    run()
