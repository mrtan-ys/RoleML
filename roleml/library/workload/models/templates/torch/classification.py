from abc import ABC
from collections.abc import Iterable
from typing import Any

import torch

from roleml.library.workload.models.bases import GradientsOperableModel, Testable
from roleml.library.workload.models.templates.torch.base import SimpleTorchModel
from roleml.library.workload.models.templates.torch.helpers.apply_gradients import default_xy_apply_gradients
from roleml.library.workload.models.templates.torch.helpers.compute_gradients import default_xy_compute_gradients
from roleml.library.workload.models.templates.torch.helpers.test import default_xy_test
from roleml.library.workload.models.templates.torch.helpers.train import default_xy_train


class SimpleTorchXYTestableModel(SimpleTorchModel, Testable[Iterable[tuple[torch.Tensor, torch.Tensor]]], ABC):

    def test(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]]) -> dict[str, Any]:
        return default_xy_test(self.module, self.criterion, data, self.device)


class SimpleTorchXYTrainableModel(SimpleTorchXYTestableModel, ABC):

    def train(self, data: Iterable[tuple[torch.Tensor, torch.Tensor]], **_) -> dict[str, Any]:
        return default_xy_train(self.module, self.optimizer, self.criterion, data, self.device)


class SimpleTorchGradientsOperableModel(
        SimpleTorchXYTestableModel, GradientsOperableModel[tuple[torch.Tensor, torch.Tensor], Any], ABC):

    def compute_gradients(self, data: tuple[torch.Tensor, torch.Tensor], **options) -> tuple[dict[str, Any], Any]:
        x, y = data
        return default_xy_compute_gradients(self.module, self.optimizer, self.criterion, x, y, self.device)

    def apply_gradients(self, gradients: Any):
        return default_xy_apply_gradients(self.module, self.optimizer, gradients)


class SimpleTorchXYModel(SimpleTorchXYTrainableModel, SimpleTorchGradientsOperableModel, ABC):
    pass
