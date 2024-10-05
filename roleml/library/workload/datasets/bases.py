from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import Generic, Protocol, TypeVar, runtime_checkable

__all__ = ['DataPoint', 'Dataset', 'DataStreams', 'IterableDataset', 'DatasetType',
           'IndexSampler', 'DatasetConverter', 'DataModifier', 'DataBatch', 'DataCombiner']


DataPoint = TypeVar('DataPoint')
DataPoint_co = TypeVar('DataPoint_co', covariant=True)
DataPoint_contra = TypeVar('DataPoint_contra', contravariant=True)


@runtime_checkable
class Dataset(Protocol[DataPoint_co]):

    def __getitem__(self, index: int, /) -> DataPoint_co: ...

    def __len__(self) -> int: ...


@runtime_checkable
class DataStreams(Protocol[DataPoint_co]):

    def __iter__(self) -> Iterator[DataPoint_co]: ...


@runtime_checkable
class IterableDataset(Dataset[DataPoint_co], DataStreams[DataPoint_co], Protocol[DataPoint_co]):
    pass


DatasetType = TypeVar('DatasetType', bound=Dataset)
DatasetType_co = TypeVar('DatasetType_co', bound=Dataset, covariant=True)
DatasetType_contra = TypeVar('DatasetType_contra', bound=Dataset, contravariant=True)


class IndexSampler(Generic[DatasetType], ABC):

    def __init__(self, source: DatasetType):
        """ More options can be defined by overriding `__init__` """
        self.source = source
    
    @abstractmethod
    def __iter__(self) -> Iterator[int]: ...


@runtime_checkable
class DatasetConverter(Protocol[DatasetType_contra, DatasetType_co]):

    def __call__(self, original: DatasetType_contra, /) -> DatasetType_co: ...


@runtime_checkable
class DataModifier(Protocol[DataPoint_contra, DataPoint_co]):

    def __call__(self, original: DataPoint_contra, /) -> DataPoint_co: ...


DataBatch = TypeVar('DataBatch')
DataBatch_co = TypeVar('DataBatch_co', covariant=True)


@runtime_checkable
class DataCombiner(Protocol[DataPoint_contra, DataBatch_co]):

    def __call__(self, original: Iterable[DataPoint_contra], /) -> DataBatch_co: ...
