"""
Modified from: https://en.d2l.ai/chapter_convolutional-neural-networks/lenet.html

Reference:
Zhang, A., Lipton, Z. C., Li, M., & Smola, A. J. (2023). Dive into Deep Learning. Cambridge University Press.
"""

from typing import Literal

import torch.nn as nn
import torch.optim as optim

from roleml.library.workload.models.templates.torch.classification import SimpleTorchXYModel

__all__ = ['LeNet5Model', 'LeNet5RGBModel']


def lenet5() -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(1, 6, kernel_size=5, padding=2), nn.Sigmoid(),
        nn.AvgPool2d(kernel_size=2, stride=2),
        nn.Conv2d(6, 16, kernel_size=5), nn.Sigmoid(),
        nn.AvgPool2d(kernel_size=2, stride=2),
        nn.Flatten(),
        nn.Linear(16 * 5 * 5, 120), nn.Sigmoid(),
        nn.Linear(120, 84), nn.Sigmoid(),
        nn.Linear(84, 10)
    )


class LeNet5Model(SimpleTorchXYModel):

    def build_model(
            self, optimizer: Literal['sgd', 'adam'] = 'sgd', lr: float = 0.01, **options
            ) -> tuple[nn.Module, optim.Optimizer, nn.Module]:
        module = lenet5()
        if optimizer == 'sgd':
            optimizer_instance = optim.SGD(module.parameters(), lr=lr)
        else:
            optimizer_instance = optim.Adam(
                filter(lambda p: p.requires_grad, module.parameters()),
                lr=lr, weight_decay=options['weight_decay'], amsgrad=True
            )
        return module, optimizer_instance, nn.CrossEntropyLoss()


def lenet5_rgb() -> nn.Sequential:
    # TODO fine-tune model structure
    return nn.Sequential(
        nn.Conv2d(3, 6, kernel_size=5), nn.ReLU(),
        nn.MaxPool2d(kernel_size=2, stride=2),
        nn.Conv2d(6, 16, kernel_size=5),
        nn.MaxPool2d(kernel_size=2, stride=2),
        nn.Flatten(),
        nn.Linear(16 * 5 * 5, 120),
        nn.Linear(120, 84),
        nn.Linear(84, 10)
    )


class LeNet5RGBModel(SimpleTorchXYModel):

    def build_model(
            self, optimizer: Literal['sgd', 'adam'] = 'sgd', lr: float = 0.01, **options
            ) -> tuple[nn.Module, optim.Optimizer, nn.Module]:
        module = lenet5_rgb()
        if optimizer == 'sgd':
            optimizer_instance = optim.SGD(module.parameters(), lr=lr)
        else:
            optimizer_instance = optim.Adam(
                filter(lambda p: p.requires_grad, module.parameters()),
                lr=lr, weight_decay=options['weight_decay'], amsgrad=True
            )
        return module, optimizer_instance, nn.CrossEntropyLoss()
