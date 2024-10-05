from abc import ABC, abstractmethod
from typing_extensions import Union, override

from roleml.shared.collections.merger import KeyValueMerger, MergedValue
from roleml.shared.types import Key, Value

__all__ = ['WeightedMerger', 'DefaultWeightedMerger']


class WeightedMerger(KeyValueMerger[Key, Value, MergedValue], ABC):

    def __init__(self, weights: dict[Key, Union[int, float]]):
        self._weights: dict[Key, Union[int, float]] = weights

    def push(self, key: Key, value: Value):
        if key not in self._weights:
            raise KeyError(f'key {key} not accepted by merger')
        self._push(key, value)

    @abstractmethod
    def _push(self, key: Key, value: Value): ...

    @property
    def allow_append(self) -> bool:
        return False

    @property
    def disposable(self) -> bool:
        return False


class DefaultWeightedMerger(WeightedMerger[Key, Value, dict[Key, Value]]):

    def __init__(self, weights: dict[Key, Union[int, float]]):
        super().__init__(weights)
        self._data = {}

    @override
    def _push(self, key: Key, value: Value):
        self._data[key] = value

    def merge(self) -> dict[Key, Value]:
        return self._data
