from collections.abc import Iterable
from typing import Any, Protocol

import torch


class XYTestFunction(Protocol):

    def __call__(
            self,
            module: torch.nn.Module, criterion: torch.nn.Module,
            data: Iterable[tuple[torch.Tensor, torch.Tensor]], device: torch.device) -> dict[str, Any]: ...


def default_xy_test(
        module: torch.nn.Module, criterion: torch.nn.Module,
        data: Iterable[tuple[torch.Tensor, torch.Tensor]], device: torch.device) -> dict[str, Any]:
    module.eval()
    total_correct = 0
    total_samples = 0
    total_loss = 0.0
    with torch.no_grad():
        for (x, y) in data:
            x = x.to(device)
            y = y.to(device)
            logits = module(x)
            loss = criterion(logits, y)
            _, predicted = torch.max(logits, dim=1)
            num_correct = predicted.eq(y).sum()
            total_correct += num_correct.item()
            total_samples += y.size(0)
            total_loss += loss.item() * y.size(0)
    return {'accuracy': total_correct / total_samples, 'loss': total_loss / total_samples}
