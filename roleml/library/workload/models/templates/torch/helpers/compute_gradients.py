from typing import Any, Protocol

import torch


class XYComputeGradientsFunction(Protocol):

    def __call__(
            self,
            module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
            x: torch.Tensor, y: torch.Tensor, device: torch.device) -> tuple[dict[str, Any], Any]: ...


class XYComputeGradientsImplFunction(Protocol):

    def __call__(
        self,
        module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
        x: torch.Tensor, y: torch.Tensor, device: torch.device) -> dict[str, Any]: ...


class RetrieveGradientsFunction(Protocol):

    def __call__(self, module: torch.nn.Module) -> Any: ...


def default_xy_compute_gradients(
        module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
        x: torch.Tensor, y: torch.Tensor, device: torch.device) -> tuple[dict[str, Any], Any]:
    metrics = default_xy_compute_gradients_impl(module, optimizer, criterion, x, y, device)
    gradients = retrieve_gradients(module)
    return metrics, gradients


def default_xy_compute_gradients_impl(
        module: torch.nn.Module, optimizer: torch.optim.Optimizer, criterion: torch.nn.Module,
        x: torch.Tensor, y: torch.Tensor, device: torch.device) -> dict[str, Any]:
    module.train()
    x = x.to(device)
    y = y.to(device)
    optimizer.zero_grad()
    logits = module(x)
    loss = criterion(logits, y)
    loss.backward()
    loss_value = loss.item()    # a Python float
    return {'loss': loss_value}


def retrieve_gradients(module: torch.nn.Module):
    return list(param.grad.view(-1) for param in module.parameters())
