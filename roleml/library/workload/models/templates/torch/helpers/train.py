from collections.abc import Iterable
from typing import Any, Protocol

import torch


class XYTrainFunction(Protocol):

    def __call__(
            self,
            module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
            data: Iterable[tuple[torch.Tensor, torch.Tensor]], device: torch.device) -> dict[str, Any]: ...


def default_xy_train(
        module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
        data: Iterable[tuple[torch.Tensor, torch.Tensor]], device: torch.device) -> dict[str, Any]:
    module.train()
    batch_count = 0
    total_loss = 0.0
    for (x, y) in data:
        x = x.to(device)
        y = y.to(device)
        optimizer.zero_grad()
        logits = module(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()   # loss.item() returns a Python float
        batch_count += 1
    return {'loss': total_loss / batch_count}
