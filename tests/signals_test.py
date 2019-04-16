from __future__ import absolute_import

from testify import TestCase, assert_equal, run

from fakemtpd.signals import Signalable


class SignalClass(Signalable):
    _signals = ("foo", "bar")

    def send(self):
        self._signal_foo()
        self._signal_bar()


class FancySignalClass(SignalClass):
    def __init__(self):
        super(FancySignalClass, self).__init__()
        self.foo_signaled = Counter()


class SignalWithDataClass(Signalable):
    _signals = ("food",)

    def send_d(self, arg):
        self._signal_food(arg)


class Counter(object):
    def __init__(self, start=0):
        self.val = start

    def incr(self):
        self.val += 1

    def set_to(self, val):
        self.val = val

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

    def test_multiple(self):
        obj = SignalClass()
        foo_ran = Counter()
        foo_3_ran = Counter()
        foo_callback_1 = lambda: foo_ran.incr()
        foo_callback_2 = lambda: foo_ran.incr()
        foo_callback_3 = lambda: foo_3_ran.incr()
        assert_equal(obj.on_foo(foo_callback_1), "foo")
        assert_equal(obj.on_foo(foo_callback_2), "foo")
        assert_equal(obj.on_foo(foo_callback_3), "foo")
        obj.send()
        assert_equal(foo_ran, 2)
        assert_equal(foo_3_ran, 1)

    def test_data(self):
        obj = SignalWithDataClass()
        food_data = Counter()
        food_callback = lambda d: food_data.set_to(d)
        assert_equal(obj.on_food(food_callback), "food")
        obj.send_d(10)
        assert_equal(food_data, 10)


if __name__ == "__main__":
    run()
