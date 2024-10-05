from threading import RLock
from typing import Any

from roleml.core.role.base import Role
from roleml.core.role.channels import Service, Task, Event
from roleml.core.role.elements import Element
from roleml.library.workload.datasets.bases import IterableDataset
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.models.bases import Testable, TrainableModel


__all__ = ['BaseModelMaintainer']


class BaseModelMaintainer(Role):

    def __init__(self):
        super().__init__()
        self.lock = RLock()

    model = Element(TrainableModel)     # type: Element[TrainableModel]
    dataset_test = Element(IterableDataset, default_constructor=DatasetViewFactory, optional=True)   

    @Service(expand=True)
    def apply_update(self, _, update):
        with self.lock:
            self.model().set_params(update)

    @Service(expand=True)
    def get_model(self, _):
        with self.lock:
            return self.model().get_params()

    test_completed = Event()

    @Task(expand=True)
    def test(self, _) -> dict[str, Any]:
        with self.lock:
            model = self.model()
            if self.dataset_test.implemented and isinstance(model, Testable):
                metrics = model.test(self.dataset_test())
                self.test_completed.emit(args=metrics)
                return metrics
            else:
                raise TypeError('testing is not supported in this Trainer')
