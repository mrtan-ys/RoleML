from typing_extensions import Any, Union, override

import torch

from roleml.library.workload.util.collections.merger.base import WeightedMerger
from roleml.shared.collections.merger import ValueMerger, CumulativeValueMerger
from roleml.shared.types import Key, Value

__all__ = ['TorchStateDictAverager', 'WeightedTorchStateDictAverager', 'TorchStateDictCumulator']


class TorchStateDictAverager(ValueMerger[dict[str, Any], dict[str, Any]]):

    def __init__(self):
        self._data = {}
        self._num = 0

    @override
    def push(self, value):
        if not self._data:
            self._data = value
        else:
            for k in self._data:
                self._data[k] += value[k]
        self._num += 1

    @override
    def merge(self):
        averaged = {k: torch.div(v, self._num) for k, v in self._data.items()}
        return averaged


class WeightedTorchStateDictAverager(WeightedMerger[Key, dict[str, Any], dict[str, Any]]):

    def __init__(self, weights: dict[Key, Union[int, float]]):
        super().__init__(weights)
        self._data = {}
        self._accepted_weights = 0

    @override
    def _push(self, key: Key, value: dict[str, Any]):
        weight = self._weights[key]
        if not self._data:
            for k in value:
                self._data[k] = value[k] * weight
        else:
            for k in self._data:
                self._data[k] += value[k] * weight
        self._accepted_weights += weight

    @override
    def merge(self) -> dict[str, Any]:
        for k in self._data:
            self._data[k] /= self._accepted_weights
        return self._data


class TorchStateDictCumulator(CumulativeValueMerger[dict[str, Any]]):

    def __init__(self):
        super().__init__()

    @override
    def cumulate(self, current_value: dict[str, Any], new_value: dict[str, Any]) -> dict[str, Any]:
        for k in current_value:
            current_value[k] += new_value[k]
        return current_value
