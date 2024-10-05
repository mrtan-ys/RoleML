import logging
from threading import Event, RLock
from typing import Any, Callable, Iterable, Optional, Union

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.context import RoleInstanceID
from roleml.core.role.types import TaskInvocation
from roleml.shared.collections.merger import KeyValueMerger, MergedValue, ValueMerger, make_kv_merger
from roleml.shared.types import Key, Value

__all__ = ['MergerTimeoutError', 'MergingFailedError', 'FilteredOut', 'DataFilter',
           'AsynchronousKeyValueMerger', 'TaskResultFilter', 'TaskResultCollector']


class MergerTimeoutError(Exception):
    pass


class MergingFailedError(Exception):
    pass


class FilteredOut(Exception):

    def __init__(self, still_count: bool = False):
        self.still_count = still_count


DataFilter = Callable[[Any, Any], tuple[Key, Value]]


class AsynchronousKeyValueMerger(KeyValueMerger[Key, Value, MergedValue]):

    def __init__(self, targets: Optional[Iterable[Key]], *,
                 merger: Union[KeyValueMerger[Key, Value, MergedValue], ValueMerger[Value, MergedValue]],
                 data_filter: DataFilter = lambda key, value: (key, value),
                 allow_append: bool = False):
        self._targets = set(targets) if targets else set()
        self._merger = merger if isinstance(merger, KeyValueMerger) else make_kv_merger(merger)
        self._data_filter = data_filter
        self._exception_occurred: Optional[Exception] = None
        if allow_append and not self._merger.allow_append:
            raise TypeError('merger does not allow appending')
        self._allow_append = allow_append   # if False, will raise exception occurred in pushing when fetching result

        self._lock = RLock()
        self._accepted = set()
        self._ready = Event()

    def push(self, key: Key, value: Value):
        with self._lock:
            try:
                self._push(key, value)
            except Exception as e:
                self._exception_occurred = e
                raise

    def push_bulk(self, data: Iterable[tuple[Key, Value]]):
        # synchronous, returns after data iteration finished
        with self._lock:
            for key, value in data:
                self.push(key, value)

    def _push(self, key: Key, value: Value):
        self._before_push(key)
        if not (key in self._accepted) or self.allow_append:
            try:
                f_key, f_value = self._data_filter(key, value)  # the filter may raise exception here
            except FilteredOut as fo:
                if fo.still_count:
                    self._after_push(key)
                elif fo.__cause__:
                    raise fo.__cause__
                return
            self._merger.push(f_key, f_value)
            self._after_push(key)
        else:
            if key not in self._accepted:
                raise KeyError(f'{key!s} does not belong to merger')
            else:
                raise TypeError('merger does not support value appending')

    def _before_push(self, key: Key):
        if self._targets and (key not in self._targets):
            raise KeyError(f'key {key} is not accepted by merger')

    def _after_push(self, key: Key):
        """ If you need to override this, make sure it does not raise any exception. """
        self._accepted.add(key)
        if len(self._accepted) == len(self._targets):
            self._ready.set()

    def merge(self) -> MergedValue:
        return self.result(None, True)

    def result(self, timeout: Optional[Union[int, float]] = None, ready_required: bool = True):
        if not self._targets:
            with self._lock:
                return self._merger.merge()
        with self._lock:
            if not self._allow_append and self._exception_occurred:
                raise MergingFailedError('see above for cause') from self._exception_occurred
        all_ready = self._ready.wait(timeout)
        if ready_required and not all_ready:
            raise MergerTimeoutError(f'merger timed out waiting for {self._targets.difference(self._accepted)}')
        with self._lock:
            return self._merger.merge()

    @property
    def allow_append(self) -> bool:
        return self._allow_append

    @property
    def disposable(self) -> bool:
        return self._merger.disposable


class TaskResultFilter:
    
    def __init__(self, on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE):
        self.on_error = on_error
        self.logger = logging.getLogger('roleml.managers.task.result-filter')

    def __call__(self, source: RoleInstanceID, task: TaskInvocation):
        try:
            result = task.result()
        except Exception as e:
            if self.on_error == ErrorHandlingStrategy.KEEP:
                return self.transform_source(source), e
            elif self.on_error == ErrorHandlingStrategy.IGNORE:
                self.logger.warning(f'failed to call task on {source}: {e!s}')
                raise FilteredOut(True)
            elif self.on_error == ErrorHandlingStrategy.RAISE_FIRST:
                self.logger.error(f'failed to call task on {source}: {e!s}')
                raise e
            else:
                raise RuntimeError('Retry on task failure is not supported in group messaging')
        else:
            return self.transform_source(source), result

    # noinspection PyMethodMayBeStatic
    def transform_source(self, source: RoleInstanceID):
        return source


class TaskResultCollector(AsynchronousKeyValueMerger[Key, Value, MergedValue]):

    def __init__(self, targets: Optional[Iterable[Key]], *,
                 merger: Union[KeyValueMerger[Key, Value, MergedValue], ValueMerger[Value, MergedValue]],
                 on_error: ErrorHandlingStrategy = ErrorHandlingStrategy.IGNORE):
        super().__init__(
            targets, merger=merger, data_filter=TaskResultFilter(on_error), allow_append=False)
