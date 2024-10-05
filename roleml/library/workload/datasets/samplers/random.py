import random
from collections.abc import Iterator

from roleml.library.workload.datasets.bases import DatasetType, IndexSampler

__all__ = ['RandomOneOffIndexSampler', 'RandomReplaceIndexSampler']


class RandomOneOffIndexSampler(IndexSampler[DatasetType]):

    def __init__(self, source: DatasetType, limit: int = -1):
        super().__init__(source)
        self.limit = limit
    
    def __iter__(self) -> Iterator[int]:
        limit = len(self.source) if (self.limit <= 0 or self.limit >= len(self.source)) else self.limit
        return iter(random.sample(range(len(self.source)), k=limit))


class RandomReplaceIndexSampler(IndexSampler[DatasetType]):
    """ Subclass this if a custom weight allocation is desired. """

    def __init__(self, source: DatasetType, limit: int = -1):
        super().__init__(source)
        self.limit = limit
    
    def __iter__(self) -> Iterator[int]:
        dataset_size = len(self.source)
        limit = dataset_size if self.limit <= 0 else self.limit
        return (random.randrange(0, dataset_size) for _ in range(limit)) 
