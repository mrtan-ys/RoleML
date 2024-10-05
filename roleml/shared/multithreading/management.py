import time
from concurrent.futures import ThreadPoolExecutor, Future, wait
from enum import Enum, auto
from threading import Thread
from typing import Any, Callable, Optional, Union

from roleml.shared.interfaces import Runnable


class ReturnStrategy(Enum):
    FIRST_COMPLETED = auto()
    FIRST_EXCEPTION = auto()
    ALL_COMPLETED = auto()


class ThreadManager:

    def __init__(self, max_pooled_workers: Optional[int] = None):
        self._components: dict[str, tuple[Thread, Runnable]] = {}
        self._executor = ThreadPoolExecutor(max_pooled_workers)

    def add_threaded_component(self, component: Runnable, *, name: Optional[str] = None, start: bool = True):
        thread = Thread(target=component.run, name=name)
        if thread.name in self._components:
            raise RuntimeError(f'thread named {thread.name} already exists')
        self._components[thread.name] = thread, component
        if start is True:
            thread.start()
        return thread

    def add_threaded_task(self, func: Callable, args: tuple = (), kwargs: Optional[dict] = None, *,
                          callback: Optional[Callable[[Future], Any]] = None) -> Future:
        if kwargs is None:
            kwargs = {}
        future = self._executor.submit(func, *args, **kwargs)
        if callback:
            future.add_done_callback(callback)
        return future

    @staticmethod
    def wait_for_threaded_tasks(futures, timeout: Optional[float] = None,
                                return_strategy: ReturnStrategy = ReturnStrategy.ALL_COMPLETED):
        return wait(futures, timeout, return_strategy.name)

    def start_all_components(self):
        for thread, _ in self._components.values():
            try:
                if thread.ident is None:
                    thread.start()
            except RuntimeError:    # ignore error if a thread is started twice
                pass

    def start_component(self, name: str):
        try:
            thread = self._components[name][0]
        except KeyError:
            raise RuntimeError(f'component named {name} does not exist')
        else:
            if thread.ident is None:
                thread.start()  # will raise RuntimeError if a thread is started twice

    def terminate_all_components(self, timeout: Union[int, float, None] = None):
        t0 = time.time()
        for thread, component in self._components.values():
            if thread.ident is not None and thread.is_alive():
                component.stop()
            remaining = max(timeout - (time.time() - t0), 0) if timeout is not None else None
            if thread.ident is not None and thread.is_alive():
                thread.join(remaining)

    def terminate_component(self, name: str, timeout: Union[int, float, None] = None):
        try:
            thread, component = self._components[name]
        except KeyError:
            raise RuntimeError(f'component named {name} does not exist')
        else:
            if thread.ident is not None and thread.is_alive():
                component.stop()
            thread.join(timeout)
