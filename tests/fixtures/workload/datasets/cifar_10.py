import unittest

from roleml.library.workload.datasets.samplers import SequentialOneOffIndexSampler
from roleml.library.workload.datasets.views import DatasetBatchView, DatasetViewFactory
from roleml.library.workload.datasets.zoo.image.cifar_10.functions import transform_torch, combine
from roleml.library.workload.datasets.zoo.image.cifar_10.impl import CiFar10SlicedDataset, CiFar10Dataset


CIFAR_10_ROOT = '/home/roleml/datasets/cifar-10'
CIFAR_10_SLICED_ROOT = '/home/roleml/datasets/cifar-10/sliced'


def load_data(training_set_slices: int = 5) -> tuple[DatasetBatchView, DatasetBatchView]:
    dataset = CiFar10SlicedDataset(root=CIFAR_10_SLICED_ROOT, index=range(training_set_slices))
    dataset = transform_torch(dataset)
    dataset_view = DatasetBatchView(dataset, index_sampler=SequentialOneOffIndexSampler, combiner=combine)
    dataset_test = CiFar10Dataset(root=CIFAR_10_ROOT, part='test')
    dataset_test = transform_torch(dataset_test)
    dataset_test_view = DatasetBatchView(dataset_test, index_sampler=SequentialOneOffIndexSampler, combiner=combine)
    return dataset_view, dataset_test_view


def load_data_using_view_factory(training_set_slices: int = 5) -> tuple[DatasetBatchView, DatasetBatchView]:
    view_factory = DatasetViewFactory
    dataset = CiFar10SlicedDataset(root=CIFAR_10_SLICED_ROOT, index=range(training_set_slices))
    dataset_view = view_factory(
        dataset,    # batch size is by default 32
        converters=[transform_torch], sampler=SequentialOneOffIndexSampler, combiner=combine)
    dataset_test = CiFar10Dataset(root=CIFAR_10_ROOT, part='test')
    dataset_test_view = view_factory(
        dataset_test,   # batch size is by default 32
        converters=[transform_torch], sampler=SequentialOneOffIndexSampler, combiner=combine)
    return dataset_view, dataset_test_view  # type: ignore


if __name__ == '__main__':
    unittest.main()
