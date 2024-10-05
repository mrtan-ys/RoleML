import inspect
from functools import wraps

from fasteners import ReaderWriterLock

__all__ = ['synchronized_read', 'synchronized_write', 'RWLocked', 'read_lock', 'write_lock']


READ = 0
WRITE = 1


def _wrap_synchronized(method):
    if getattr(method, '_synchronized_') == READ:
        def synchronized_read_method(self, *args, **kwargs):
            with self._synch_lock_.read_lock():
                return method(self, *args, **kwargs)
        return synchronized_read_method
    elif getattr(method, '_synchronized_') == WRITE:
        def synchronized_write_method(self, *args, **kwargs):
            with self._synch_lock_.write_lock():
                return method(self, *args, **kwargs)
        return synchronized_write_method
    else:
        assert False


def synchronized_read(method):
    method._synchronized_ = READ
    return method


def synchronized_write(method):
    method._synchronized_ = WRITE
    return method


class RWLocked:
    """ Creates an object lock (which is a reader-writer lock) for every instance. Be careful with MRO when in a context
    of multiple inheritance. """

    def __init_subclass__(cls):
        original_init = cls.__init__

        @wraps(original_init)
        def init_wrapped(self, *args, **kwargs):
            if not hasattr(self, '_synch_lock_'):
                # subclass can use this lock by getattr(self, '_synch_lock_')
                self._synch_lock_ = ReaderWriterLock()
            original_init(self, *args, **kwargs)    # noqa: the IDE is wrong
        cls.__init__ = init_wrapped

        for name, attr in cls.__dict__.items():
            if inspect.isfunction(attr):
                if hasattr(attr, '_synchronized_') and (not name.startswith('__')) and (not name.endswith('__')):
                    setattr(cls, name, _wrap_synchronized(attr))


def read_lock(obj: RWLocked):
    """ Utility function to create a read lock context for given RWLocked object. Should be used inside an
    instance method."""
    lock: ReaderWriterLock = getattr(obj, '_synch_lock_')
    return lock.read_lock()


def write_lock(obj: RWLocked):
    """ Utility function to create a write lock context for given RWLocked object. Should be used inside an
    instance method."""
    lock: ReaderWriterLock = getattr(obj, '_synch_lock_')
    return lock.write_lock()


if __name__ == '__main__':
    class Foo(RWLocked):
        """ a simple test """

        def __init__(self):
            self.val = 0

        def add(self, val):
            with write_lock(self):
                self.val += val

        def get(self):
            with read_lock(self):
                return self.val

    foo = Foo()

    from threading import Thread
    t1 = Thread(target=foo.add, args=(10, ))
    t2 = Thread(target=foo.add, args=(20, ))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert foo.get() == 30
