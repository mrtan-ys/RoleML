from collections.abc import MutableMapping
from typing import Optional
import unittest

from roleml.library.workload.models.zoo.torch.cnn.vgg import VGGLiteModel
from tests.fixtures.workload.datasets.cifar_10 import load_data, load_data_using_view_factory
from tests.unittests.library.workload.combination.helpers import train


class VGGOnCiFar10TestCase(unittest.TestCase):

    NUM_EPOCHS = 3
    NUM_THREADS: Optional[int] = 32

    def test_training(self):
        model = VGGLiteModel(type='VGG11', in_channels=3, lr=0.001, num_threads=self.NUM_THREADS)
        dataset_view, dataset_test_view = load_data()
        train(model, dataset_view, dataset_test_view, num_epochs=VGGOnCiFar10TestCase.NUM_EPOCHS)
        params = model.get_params()
        self.assertIsInstance(params, MutableMapping)   # key: layer name | value: torch.Tensor
        model.set_params(params)

    def test_training_v2(self):
        model = VGGLiteModel(type='VGG11', in_channels=3, lr=0.001, num_threads=self.NUM_THREADS)
        dataset_view, dataset_test_view = load_data_using_view_factory()
        train(model, dataset_view, dataset_test_view, num_epochs=VGGOnCiFar10TestCase.NUM_EPOCHS)
        params = model.get_params()
        self.assertIsInstance(params, MutableMapping)   # key: layer name | value: torch.Tensor
        model.set_params(params)


if __name__ == '__main__':
    unittest.main()
