from collections.abc import Iterable
from typing import Any

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision.models import mobilenet_v3_large, mobilenet_v3_small

from roleml.library.workload.models.templates.torch.base import SimpleTorchModel
from roleml.library.workload.models.templates.torch.helpers.test import default_xy_test
from roleml.library.workload.models.templates.torch.helpers.train import default_xy_train

__all__ = ['MobileNetV3LargeModel', 'MobileNetV3SmallModel']


class MobileNetV3LargeModel(SimpleTorchModel):

    def build_model(
            self, optimizer: str = 'sgd', lr: float = 0.01, num_classes: int = 100, **options
            ) -> tuple[nn.Module, optim.Optimizer, nn.Module]:
        module = mobilenet_v3_large(num_classes=num_classes)
        if optimizer == 'sgd':
            opt = optim.SGD(module.parameters(), lr=lr)
        else:
            opt = optim.Adam(
                filter(lambda p: p.requires_grad, module.parameters()),
                lr=lr, weight_decay=options['weight_decay'], amsgrad=True
            )
        return module, opt, nn.CrossEntropyLoss()

    def train(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]], **_) -> dict[str, Any]:
        return default_xy_train(self.module, self.optimizer, self.criterion, data, self.device)

    def test(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]]) -> dict[str, Any]:
        return default_xy_test(self.module, self.criterion, data, self.device)


class MobileNetV3SmallModel(SimpleTorchModel):

    def build_model(
            self, optimizer: str = 'sgd', lr: float = 0.01, num_classes: int = 100, **options
            ) -> tuple[nn.Module, optim.Optimizer, nn.Module]:
        module = mobilenet_v3_small(num_classes=num_classes)
        if optimizer == 'sgd':
            opt = optim.SGD(module.parameters(), lr=lr)
        else:
            opt = optim.Adam(
                filter(lambda p: p.requires_grad, module.parameters()),
                lr=lr, weight_decay=options['weight_decay'], amsgrad=True
            )
        return module, opt, nn.CrossEntropyLoss()

    def train(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]], **_) -> dict[str, Any]:
        return default_xy_train(self.module, self.optimizer, self.criterion, data, self.device)

    def test(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]]) -> dict[str, Any]:
        return default_xy_test(self.module, self.criterion, data, self.device)
