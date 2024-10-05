from typing import Any, Protocol

import torch


class XYApplyGradientsFunction(Protocol):

    def __call__(
            self,
            module: torch.nn.Module, optimizer: torch.optim.Optimizer, gradients: Any) -> None: ...


def default_xy_apply_gradients(
        module: torch.nn.Module, optimizer: torch.optim.Optimizer, gradients: Any):
    for param, grad in zip(module.parameters(), gradients):
        param.grad.copy_(grad)
    optimizer.step()
