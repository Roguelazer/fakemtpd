import fcntl
import lockfile
import logging
import os


class BetterLockfile(object):
    """
    A lockfile (matching the specification of the builtin lockfile class)
    based off of flock. Only uses a single lock file rather than one per process/thread.
    """
    def __init__(self, path):
        self.path = path
        self.lock_file = None
        try:
            self.lock_file = open(self.path, 'a')
        except Exception:
            raise lockfile.LockError()
        self._has_lock = False

    @property
    def file(self):
        """Get a handle to the underlying lock file (to write out data to)"""
        return self.lock_file

    def acquire(self):
        logging.debug("Locking %s", self.path)
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._has_lock = True
        except IOError:
            raise lockfile.AlreadyLocked()
        logging.debug("Locked %s", self.path)

    def break_lock(self):
        """Can't break posix locks, sorry man"""
        raise lockfile.LockError()

    @property
    def i_am_locking(self):
        return self._has_lock

    @property
    def is_locked(self):
        if self._has_lock:
            return True
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            return False
        except IOError:
            return True

    def release(self):
        logging.debug("Releasing lock on %s", self.path)
        if self.i_am_locking:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self._has_lock = False
        else:
            raise lockfile.NotLocked()
        logging.debug("Unlocked %s", self.path)

    def destroy(self):
        try:
            if self.i_am_locking:
                self.release()
            self.lock_file.close()
        finally:
            if os.path.exists(self.path):
                os.unlink(self.path)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
