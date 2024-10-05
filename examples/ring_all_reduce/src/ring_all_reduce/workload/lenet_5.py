from typing import Any

import torch

from roleml.library.workload.models.templates.torch.helpers.compute_gradients import default_xy_compute_gradients_impl
from roleml.library.workload.models.zoo.torch.cnn.lenet_5 import LeNet5RGBModel


class MyLeNet5RGBModel(LeNet5RGBModel):

    def compute_gradients(self, data: tuple[torch.Tensor, torch.Tensor], **options) -> tuple[dict[str, Any], Any]:
        x, y = data
        metrics = default_xy_compute_gradients_impl(self.module, self.optimizer, self.criterion, x, y, self.device)
        # get all gradients and flatten into one-dimensional
        gradients_flattened = torch.cat([param.grad.view(-1) for param in self.module.parameters()])
        return metrics, gradients_flattened

    def apply_gradients(self, gradients):
        # the received gradients is one-dimensional tensor
        index = 0
        for param in self.module.parameters():
            grad_size = param.grad.numel()
            param.grad.copy_(gradients[index:index + grad_size].view_as(param.grad))
            index += grad_size
        self.optimizer.step()
