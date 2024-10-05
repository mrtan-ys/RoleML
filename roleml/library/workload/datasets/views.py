from collections.abc import Iterator
from typing import Any, Optional, TypeVar, Union

from roleml.library.workload.datasets.bases import \
    DataBatch, DataCombiner, DataModifier, DataPoint, DataStreams, Dataset, DatasetConverter, IndexSampler
from roleml.library.workload.datasets.samplers import BUILTIN_SAMPLERS
from roleml.shared.importing import LoadCompatible, Loadable, load


__all__ = ['DatasetView', 'DatasetPointView', 'DatasetBatchView', 'DatasetViewFactory']


DataPointOriginal = TypeVar('DataPointOriginal')


class DatasetView(Dataset[DataPoint]):

    def __init__(self, dataset: Dataset[DataPointOriginal],
                 *, modifier: DataModifier[DataPointOriginal, DataPoint] = lambda original: original,
                 index_sampler: Loadable[IndexSampler], index_sampler_options: Optional[dict[str, Any]] = None):
        self.dataset = dataset
        self.modifier = modifier
        self.index_sampler = load(
            index_sampler, IndexSampler,
            args=(dataset, ), kwargs=index_sampler_options, builtin_sources=BUILTIN_SAMPLERS)

    def set_index_sampler(self, index_sampler_cls: type[IndexSampler], **options):
        self.index_sampler = index_sampler_cls(self.dataset, **options)
    
    def __len__(self) -> int:
        return len(self.dataset)
    
    def __getitem__(self, index) -> DataPoint:
        return self.modifier(self.dataset[index])
    
    def get_original_item(self, index: int) -> Any:
        return self.dataset[index]


class DatasetPointView(DatasetView[DataPoint], DataStreams[DataPoint]):
    # also implements IterableDataset

    class DataIterator:

        def __init__(self, dataset: Dataset, indices: Iterator[int], *, modifier: DataModifier):
            self.dataset = dataset
            self.indices = indices
            self.modifier = modifier
        
        def __iter__(self):
            return self
        
        def __next__(self):
            index = next(self.indices)
            sample = self.dataset[index]
            return self.modifier(sample)
    
    def __iter__(self) -> Iterator[DataPoint]:
        return DatasetPointView.DataIterator(self.dataset, iter(self.index_sampler), modifier=self.modifier)


class DatasetBatchView(DatasetView[DataPoint], DataStreams[DataBatch]):
    # also implements IterableDataset

    class DataIterator:

        def __init__(self, dataset: Dataset[DataPointOriginal], indices: Iterator[int],
                     *, modifier: DataModifier, batch_size: int, drop_last: bool, combiner: DataCombiner):
            self.dataset = dataset
            self.indices = indices
            self.modifier = modifier
            self.combiner = combiner
            self.batch_size = batch_size
            self.drop_last = drop_last
            self._iter_done = False
        
        def __iter__(self):
            return self
        
        def __next__(self):
            if self._iter_done:
                raise StopIteration
            indices = []
            try:
                for _ in range(self.batch_size):
                    indices.append(next(self.indices))
            except StopIteration:
                last_size = len(indices)
                if last_size == 0 or (self.drop_last is True and last_size < self.batch_size):
                    self._iter_done = True
                    raise
            samples = (self.modifier(self.dataset[index]) for index in indices)
            return self.combiner(samples)

    def __init__(self, dataset: Dataset[DataPointOriginal],
                 *, modifier: DataModifier[DataPointOriginal, DataPoint] = lambda original: original,
                 index_sampler: Loadable[IndexSampler], index_sampler_options: Optional[dict[str, Any]] = None,
                 batch_size: int = 32, drop_last: bool = False,
                 combiner: DataCombiner[DataPoint, DataBatch] = lambda original: original):
        super().__init__(
            dataset, modifier=modifier, index_sampler=index_sampler, index_sampler_options=index_sampler_options)
        self.combiner = combiner
        self.batch_size = batch_size
        self.drop_last = drop_last
    
    def __iter__(self) -> Iterator[DataBatch]:
        return DatasetBatchView.DataIterator(
            self.dataset, iter(self.index_sampler), modifier=self.modifier,
            batch_size=self.batch_size, drop_last=self.drop_last, combiner=self.combiner)


# noinspection PyPep8Naming
def DatasetViewFactory(
    dataset: LoadCompatible[Dataset],
    *,
    converters: Optional[list[LoadCompatible[DatasetConverter]]] = None,
    sampler: Loadable[IndexSampler] = 'sequential',
    batch_size: int = 32,
    drop_last: bool = False,
    always_combine: bool = False,   # even when batch_size == 1
    modifier: LoadCompatible[DataModifier] = lambda original: original,
    combiner: LoadCompatible[DataCombiner] = lambda original: list(original),
) -> Union[DatasetPointView, DatasetBatchView]:
    dataset = load(dataset, Dataset)
    if converters:
        for arg in converters:
            converter = load(arg, DatasetConverter)
            dataset = converter(dataset)
    assert isinstance(dataset, Dataset)
    if batch_size > 1 or always_combine:
        return DatasetBatchView(
            dataset, index_sampler=sampler, batch_size=batch_size, drop_last=drop_last,
            modifier=load(modifier, DataModifier), combiner=load(combiner, DataCombiner))
    else:
        return DatasetPointView(
            dataset, index_sampler=sampler, modifier=load(modifier, DataModifier))
