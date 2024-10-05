import pathlib
import sys
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

import random
import unittest
from collections.abc import Iterable

import torch

from roleml.library.workload.datasets.bases import Dataset
from roleml.library.workload.datasets.samplers import SequentialOneOffIndexSampler
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.datasets.zoo.image.cifar_10.functions import combine, transform_torch
from federated_learning.workload.cifar_10 import MyCiFar10SlicedDataset, MyCiFar10Dataset
from federated_learning.workload.lenet_5 import MyLeNet5RGBModel


class FLTestCase(unittest.TestCase):
    """ Locally-simulated Federated Learning. """

    CIFAR_10_ROOT = '/home/roleml/datasets/cifar-10'
    CIFAR_10_SLICED_ROOT = '/home/roleml/datasets/cifar-10/sliced'

    NUM_EPOCHS = 75
    NUM_CLIENTS = 10
    NUM_CLIENTS_PER_ROUND = 3

    # noinspection DuplicatedCode
    def test_fl(self):
        models = [MyLeNet5RGBModel(optimizer='sgd', lr=0.01) for _ in range(self.NUM_CLIENTS)]
        view_factory = DatasetViewFactory
        dataset_views = [
            view_factory(
                MyCiFar10SlicedDataset(root=FLTestCase.CIFAR_10_SLICED_ROOT, index=i),
                converters=[transform_torch],
                batch_size=32, drop_last=False, combiner=combine)
            for i in range(self.NUM_CLIENTS)
        ]
        global_model = MyLeNet5RGBModel()
        dataset_test_view = view_factory(
            MyCiFar10Dataset(root=FLTestCase.CIFAR_10_ROOT, part='test'),
            converters=[transform_torch],
            sampler=SequentialOneOffIndexSampler, combiner=combine
        )
        self.assertIsInstance(dataset_test_view, Dataset)
        self.assertIsInstance(dataset_test_view, Iterable)

        # train
        for i in range(self.NUM_EPOCHS):
            indices = random.sample(range(self.NUM_CLIENTS), k=self.NUM_CLIENTS_PER_ROUND)
            aggregated = {}
            for index in indices:
                model = models[index]
                model.set_params(global_model.get_params())
                model.train(dataset_views[index])
                # print(f'model {index} epoch stats', f'{model.train((dataset_views[index]))}')
                if not aggregated:
                    aggregated = model.get_params()
                else:
                    params = model.get_params()
                    for key in aggregated:
                        aggregated[key] += params[key]
            aggregated = {k: torch.div(v, self.NUM_CLIENTS_PER_ROUND) for k, v in aggregated.items()}
            global_model.set_params(aggregated)
            test_result = global_model.test(dataset_test_view)
            print(f'test result of epoch {i}', test_result)


if __name__ == '__main__':
    unittest.main()
