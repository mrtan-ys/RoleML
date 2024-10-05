from threading import Lock, RLock
from typing import Any, Callable, Generic, Optional, Union

from roleml.shared.types import T

__all__ = ['CallAtMostOnceLimiter', 'at_most_once']


class CallAtMostOnceLimiter(Generic[T]):
    """ For lightweight use, see also ``functools.cache``. This helper makes sure that a second call cannot be made even
    with different args or kwargs. """

    __slots__ = ('lock', 'func', 'args', 'kwargs', 'called', 'cache', 'result')

    def __init__(self, func: Callable[..., T], *, args: tuple = (), kwargs: Optional[dict[str, Any]] = None,
                 lock: Optional[Union[Lock, RLock]] = None, cache: bool = True):
        self.lock = lock or RLock()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.called = False
        self.cache = cache
        self.result: Optional[T] = None

    def __call__(self, *args, **kwargs) -> Optional[T]:
        with self.lock:
            if not self.called:
                result = self.func(*(args or self.args), **(kwargs or self.kwargs or {}))
                self.called = True
                if self.cache:
                    self.result = result
                return result
            else:
                return self.result


def at_most_once(func: Callable):
    """ This decorator cannot be used if ``func`` is a method. In that case, use ``CallAtMostOnceLimiter`` instead. """
    return CallAtMostOnceLimiter(func)
