from collections.abc import MutableMapping
from typing import Optional
import unittest

from roleml.library.workload.models.zoo.torch.cnn.lenet_5 import LeNet5RGBModel
from tests.fixtures.workload.datasets.cifar_10 import load_data, load_data_using_view_factory
from tests.unittests.library.workload.combination.helpers import train


class LeNet5OnCiFar10TestCase(unittest.TestCase):

    NUM_EPOCHS = 100
    NUM_THREADS: Optional[int] = 16

    def test_training(self):
        model = LeNet5RGBModel(optimizer='sgd', lr=0.01, num_threads=self.NUM_THREADS)
        dataset_view, dataset_test_view = load_data(training_set_slices=10)
        train(model, dataset_view, dataset_test_view, num_epochs=LeNet5OnCiFar10TestCase.NUM_EPOCHS)
        params = model.get_params()
        self.assertIsInstance(params, MutableMapping)   # key: layer name | value: torch.Tensor
        model.set_params(params)

    def test_training_v2(self):
        model = LeNet5RGBModel(optimizer='sgd', lr=0.01, num_threads=self.NUM_THREADS)
        dataset_view, dataset_test_view = load_data_using_view_factory(training_set_slices=10)
        train(model, dataset_view, dataset_test_view, num_epochs=LeNet5OnCiFar10TestCase.NUM_EPOCHS)
        params = model.get_params()
        self.assertIsInstance(params, MutableMapping)   # key: layer name | value: torch.Tensor
        model.set_params(params)


if __name__ == '__main__':
    unittest.main()
