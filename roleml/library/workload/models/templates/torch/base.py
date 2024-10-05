from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping
from typing import Any, Optional

import torch

from roleml.library.workload.models.bases import ParametersAccessible


class SimpleTorchModel(ParametersAccessible[MutableMapping[str, Any], Mapping[str, Any]], ABC):

    def __init__(self, device: str = 'cpu', num_threads: Optional[int] = None, copy_on_get_params: bool = False,
                 **options):
        if num_threads:
            torch.set_num_threads(num_threads)
        self.module, self.optimizer, self.criterion = self.build_model(**options)
        self.device = self.get_device(device)
        self.module.to(self.device)
        self.criterion.to(self.device)
        # torch.autograd.set_detect_anomaly(True)
        self.copy_on_get_params = copy_on_get_params    # True means get_params() will return a deep copy

    def get_device(self, device_name: str) -> torch.device:     # noqa: non-static method
        if device_name.lower() == 'cuda' and torch.cuda.is_available():
            return torch.device('cuda')
        else:
            return torch.device('cpu')
    
    @abstractmethod
    def build_model(self, **options) -> tuple[torch.nn.Module, torch.optim.Optimizer, torch.nn.Module]:
        """ Return values are (model, optimizer, loss). "to device" operation is not needed. """
        ...

    def get_params(self) -> dict[str, Any]:
        if self.copy_on_get_params:
            import copy
            return copy.deepcopy(self.module.state_dict())
        else:
            return self.module.state_dict()

    def set_params(self, params: Mapping[str, Any]):
        self.module.load_state_dict(params)
