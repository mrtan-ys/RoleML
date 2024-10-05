from collections.abc import Iterator
from itertools import cycle

from roleml.library.workload.datasets.bases import DatasetType, IndexSampler


class SequentialOneOffIndexSampler(IndexSampler[DatasetType]):

    def __iter__(self) -> Iterator[int]:
        return iter(range(len(self.source)))


class SequentialCycleIndexSampler(IndexSampler[DatasetType]):

    def __iter__(self) -> Iterator[int]:
        return cycle(range(len(self.source)))
