from collections.abc import Iterator
from typing import Any, Optional

from roleml.core.role.channels import Service, Task, Event
from roleml.core.role.elements import Element
from roleml.library.roles.trainer.base import BaseModelMaintainer
from roleml.library.workload.datasets.bases import IterableDataset
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.models.bases import GradientsOperableModel


class GradientsTrainer(BaseModelMaintainer):

    def __init__(self):
        super().__init__()
        # if duplicate data is acceptable in one gradient computation session, 
        # user may just use the random sampler
        self.dataset_iterator: Optional[Iterator[tuple[Any, Any]]] = None

    # element dataset_test inherited from base class

    model: Element[GradientsOperableModel] = Element(GradientsOperableModel)    # type: ignore
    dataset = Element(IterableDataset, default_constructor=DatasetViewFactory)

    gradient_computed = Event()

    @Task(expand=True)
    def compute_gradients(self, _):
        with self.lock:
            try:
                data_batch = next(self.dataset_iterator)    # type: ignore
            except (StopIteration, TypeError):
                self.dataset_iterator = iter(self.dataset())
                data_batch = next(self.dataset_iterator)
            # data_batch should contain x and y
            metrics, gradients = self.model().compute_gradients(data_batch)
            self.gradient_computed.emit(args=metrics)
            return gradients
    
    gradient_applied = Event()

    @Service(expand=True)
    def apply_gradients(self, _, update: Any):
        with self.lock:
            self.model().apply_gradients(update)
            self.gradient_applied.emit()
