import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

import random
import unittest
from collections.abc import Iterable

from roleml.library.workload.datasets.bases import Dataset
from roleml.library.workload.datasets.samplers import SequentialOneOffIndexSampler
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.datasets.zoo.image.cifar_10.functions import combine, transform_torch
from gossip_learning.workload.cifar_10 import MyCiFar10SlicedDataset, MyCiFar10Dataset
from gossip_learning.workload.lenet_5 import MyLeNet5RGBModel


class GLTestCase(unittest.TestCase):

    CIFAR_10_ROOT = '/home/roleml/datasets/cifar-10'
    CIFAR_10_SLICED_ROOT = '/home/roleml/datasets/cifar-10/sliced'

    NUM_CLIENTS = 10
    NUM_STEPS = 100

    # noinspection DuplicatedCode
    def test_gl(self):
        models = [MyLeNet5RGBModel(optimizer='sgd', lr=0.01) for _ in range(10)]
        view_factory = DatasetViewFactory
        dataset_views = [
            view_factory(
                MyCiFar10SlicedDataset(root=GLTestCase.CIFAR_10_SLICED_ROOT, index=i),
                converters=[transform_torch],
                batch_size=32, drop_last=False, combiner=combine)
            for i in range(self.NUM_CLIENTS)
        ]
        dataset_test_view = view_factory(
            MyCiFar10Dataset(root=GLTestCase.CIFAR_10_ROOT, part='test'),
            converters=[transform_torch],
            sampler=SequentialOneOffIndexSampler, combiner=combine
        )
        self.assertIsInstance(dataset_test_view, Dataset)
        self.assertIsInstance(dataset_test_view, Iterable)

        index = random.sample(range(self.NUM_CLIENTS), k=1)[0]    # starting client

        # train
        for i in range(self.NUM_STEPS):
            model = models[index]
            dataset = dataset_views[index]
            model.train(dataset)
            params = model.get_params()
            print(f'test result of overall epoch {i}', model.test(dataset_test_view))
            index = random.sample(range(self.NUM_CLIENTS), k=1)[0]
            model = models[index]
            model.set_params(params)


if __name__ == '__main__':
    unittest.main()
