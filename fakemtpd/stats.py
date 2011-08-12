"""Statistics keeping, using the Singleton Module pattern"""

import itertools
import time

incrementable_stats = ('lifetime_sessions', 'lifetime_control_sessions', 'lifetime_tls_sessions')
settable_stats = ('active_sessions', )
static_stats = ('uptime',)
tracked_stats = tuple(itertools.chain(incrementable_stats, static_stats, settable_stats))

def _verify_settable(function):
    def inner(stat_name, *args, **kwargs):
        if stat_name not in incrementable_stats:
            return NameError("stat name must be in (%s)" % ",".join(settable_stats))
        return function(stat_name, *args, **kwargs)
    return inner

def _verify_incrementable(function):
    def inner(stat_name, *args, **kwargs):
        if stat_name not in incrementable_stats:
            return NameError("stat name must be in (%s)" % ",".join(tracked_stats))
        return function(stat_name, *args, **kwargs)
    return inner

def _verify_tracked(function):
    def inner(stat_name, *args, **kwargs):
        if stat_name not in tracked_stats:
            return NameError("stat name must be in (%s)" % ",".join(tracked_stats))
        return function(stat_name, *args, **kwargs)
    return inner

_stats = dict((k, 0) for k in tracked_stats)
_stats['start_time'] = time.time()

@_verify_incrementable
def increment(stat_name):
    _stats[stat_name] += 1

@_verify_tracked
def get(stat_name):
    if stat_name in _overrides:
        return _overrides[stat_name]()
    else:
        return _stats[stat_name]

@_verify_settable
def set_value(stat_name, value):
    self._stats[stat_name] = value

_overrides = {'uptime': lambda: time.time() - _stats['start_time']}
