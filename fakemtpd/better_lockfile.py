import fcntl
import lockfile

class BetterLockfile(object):
    """
    A lockfile (matching the specification of the builtin lockfile class)
    based off of lockf. Only uses a single lock file rather than one per process/thread.
    """
    def __init__(self, path):
        self.path = path
        self.lock_file = None
        self.lock_file = open(self.path, 'w')
        self._is_locked = False

    def file(self):
        """Get a handle to the underlying lock file (to write out data to)"""
        return self.lock_file

    def acquire(self):
        try:
            fcntl.lockf(self.lock_file, fcntl.LOCK_EX|fcntl.LOCK_NB)
            self._is_locked = True
        except IOError:
            raise lockfile.AlreadyLocked()

    def break_lock(self):
        """Can't break posix locks, sorry man"""
        raise lockfile.LockError()

    def i_am_locking(self):
        return False

    @property
    def is_locked(self):
        return self._is_locked

    def release(self):
        if self.is_locked:
            fcntl.lockf(self.lock_file, fcntl.LOCK_UN)
            self._is_locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self):
        self.release()
