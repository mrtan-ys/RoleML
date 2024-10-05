from collections.abc import Sequence
from typing import TypeVar

from roleml.library.workload.datasets.bases import DataPoint, Dataset

__all__ = ['SimpleDataset', 'X', 'Y', 'XYDataset']


class SimpleDataset(Dataset[DataPoint]):

    def __init__(self, source: Sequence[DataPoint]):
        """ If `source` is a list or ndarray, this wrapper is not needed; you can instead use `type: ignore` """
        self.source = source
    
    def __len__(self) -> int:
        return len(self.source)
    
    def __getitem__(self, index: int) -> DataPoint:
        return self.source[index]


X = TypeVar('X')
Y = TypeVar('Y')


class XYDataset(Dataset[tuple[X, Y]]):

    def __init__(self, x: Dataset[X], y: Dataset[Y]):
        self.x = x
        self.y = y
    
    def __getitem__(self, index: int) -> tuple[X, Y]:
        return self.x[index], self.y[index]
    
    def __len__(self) -> int:
        return len(self.x)
