import inspect
from functools import wraps
from threading import RLock


def _wrap_synchronized(method):
    def synchronized_method(self, *args, **kwargs):
        with self._synch_lock_:
            return method(self, *args, **kwargs)
    return synchronized_method


class _SynchronizedPropertyMarker:

    __slots__ = ('prop', )

    def __init__(self, prop: property):
        self.prop: property = prop


def synchronized(method):
    method._synchronized_ = True
    return method


class Locked:
    """ Creates an object lock for every instance. Be careful with MRO when in a context of multiple inheritance. """

    def __init_subclass__(cls, synchronize_all: bool = False):
        """ If synchronize_all is True, all methods (actually including lambdas) and properties defined in the given
        class will be synchronized. This does not include methods defined in its parent class, unless overridden. It
        also excludes magic methods starting and ending with __. If you need a magic method to be synchronized, use the
        `@synchronized` decorator manually. """
        original_init = cls.__init__

        @wraps(original_init)
        def init_wrapped(self, *args, **kwargs):
            if not hasattr(self, '_synch_lock_'):
                # subclass can use this lock by getattr(self, '_synch_lock_')
                self._synch_lock_ = RLock()
            original_init(self, *args, **kwargs)    # noqa: the IDE is wrong
        cls.__init__ = init_wrapped

        def __enter__(self):
            self._synch_lock_.acquire()
        cls.__enter__ = __enter__

        def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: argument unused
            self._synch_lock_.release()
        cls.__exit__ = __exit__

        for name, attr in cls.__dict__.items():
            if inspect.isfunction(attr):
                if getattr(attr, '_synchronized_', False) or \
                        (synchronize_all and (not name.startswith('__')) and (not name.endswith('__'))):
                    setattr(cls, name, _wrap_synchronized(attr))
            elif inspect.isdatadescriptor(attr):
                # property not marked synchronized
                assert isinstance(attr, property)
                if synchronize_all and (not name.startswith('__')) and (not name.endswith('__')):
                    synchronized_property = property(
                        _wrap_synchronized(attr.fget) if attr.fget is not None else None,
                        _wrap_synchronized(attr.fset) if attr.fset is not None else None,
                        _wrap_synchronized(attr.fdel) if attr.fdel is not None else None,
                        attr.__doc__
                    )
                    setattr(cls, name, synchronized_property)
            elif isinstance(attr, _SynchronizedPropertyMarker):
                # property already marked synchronized
                original_property: property = attr.prop
                synchronized_property = property(
                    _wrap_synchronized(original_property.fget) if original_property.fget is not None else None,
                    _wrap_synchronized(original_property.fset) if original_property.fset is not None else None,
                    _wrap_synchronized(original_property.fdel) if original_property.fdel is not None else None,
                    original_property.__doc__
                )
                setattr(cls, name, synchronized_property)

    # for type check only; will be replaced by __init_subclass__

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
