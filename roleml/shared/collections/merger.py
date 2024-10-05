from abc import ABC, abstractmethod
from typing import Generic, Optional, Protocol, TypeVar

from roleml.shared.types import Key, Value

__all__ = ['ValueMerger', 'ListValueMerger', 'CumulativeValueMerger', 'CumulativeAddingValueMerger',
           'KeyValueMerger', 'DictKeyValueMerger', 'KeyAgnosticKeyValueMerger', 'make_kv_merger', 'MergedValue']


MergedValue = TypeVar('MergedValue')


class ValueMerger(Generic[Value, MergedValue], ABC):

    @abstractmethod
    def push(self, value: Value): ...

    @abstractmethod
    def merge(self) -> MergedValue: ...

    @property
    def disposable(self) -> bool:
        """ Whether the method `merge()` does not allow any duplicate call for the same instance. """
        return False


class ListValueMerger(ValueMerger[Value, list[Value]]):

    def __init__(self):
        self._data = list()

    def push(self, value: Value):
        self._data.append(value)

    def merge(self) -> list[Value]:
        return self._data

    @property
    def disposable(self) -> bool:
        return False    # as long as it is not modified elsewhere


class Addable(Protocol[Value]):

    def __add__(self: Value, other: Value, /) -> Value: ...


AnyAddable = TypeVar('AnyAddable', bound=Addable)


class CumulativeValueMerger(ValueMerger[Value, Optional[Value]], ABC):

    def __init__(self):
        self._data = None

    def push(self, value: Value):
        if self._data is None:
            self._data = value
        else:
            self._data = self.cumulate(self._data, value)

    @abstractmethod
    def cumulate(self, current_value: Value, new_value: Value) -> Value:
        """ The cumulation should be done in-place whenever possible (i.e. by directly operating `current_value`) """
        ...

    def merge(self) -> Optional[Value]:
        return self._data

    @property
    def disposable(self) -> bool:
        return False


class CumulativeAddingValueMerger(CumulativeValueMerger[AnyAddable]):

    def cumulate(self, current_value: AnyAddable, new_value: AnyAddable) -> AnyAddable:
        return current_value + new_value


class KeyValueMerger(Generic[Key, Value, MergedValue], ABC):

    @abstractmethod
    def push(self, key: Key, value: Value): ...

    @abstractmethod
    def merge(self) -> MergedValue: ...

    @property
    def allow_append(self) -> bool:
        """ Whether the method `push()` is allowed to be called multiple times on the same key for an instance. """
        return True

    @property
    def disposable(self) -> bool:
        """ Whether the method `merge()` does not allow any duplicate call for the same instance. """
        return False


class DictKeyValueMerger(KeyValueMerger[Key, Value, dict[Key, Value]]):

    def __init__(self):
        self._data = dict()

    def push(self, key: Key, value: Value):
        self._data[key] = value

    def merge(self) -> dict[Key, Value]:
        return self._data

    @property
    def allow_append(self) -> bool:
        return True

    @property
    def disposable(self) -> bool:
        return False


class KeyAgnosticKeyValueMerger(KeyValueMerger[Key, Value, MergedValue]):

    def __init__(self, merger: ValueMerger[Value, MergedValue]):
        self._merger = merger

    def push(self, key: Key, value: Value):
        self._merger.push(value)

    def merge(self) -> MergedValue:
        return self._merger.merge()

    @property
    def allow_append(self) -> bool:
        return True

    @property
    def disposable(self) -> bool:
        return False


def make_kv_merger(merger: ValueMerger[Value, MergedValue]) -> KeyValueMerger:
    return KeyAgnosticKeyValueMerger(merger)
