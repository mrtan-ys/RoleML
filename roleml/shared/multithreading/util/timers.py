from threading import Lock, RLock, Condition
from typing import Any, Callable, Optional, Union


class TimerLocal:

    __slots__ = ('condition', '_interrupted', '_running')

    def __init__(self, lock: Optional[Union[Lock, RLock]] = None):
        self.condition = Condition(lock)
        self._interrupted = False
        self._running = False

    def interrupt(self):
        with self.condition:
            self._interrupted = True
            self.condition.notify_all()

    def wait(self, timeout: Optional[Union[int, float]] = None,
             *, on_interrupt: Callable[[], Any] = (lambda: None), on_timeout: Callable[[], Any] = (lambda: None)):
        with self.condition:
            if self._running:
                raise RuntimeError('cannot run two waits simultaneously')
            self._running = True
            self.condition.wait(timeout)
            if self._interrupted:
                on_interrupt()
                self._interrupted = False
            else:
                on_timeout()
            self._running = False
