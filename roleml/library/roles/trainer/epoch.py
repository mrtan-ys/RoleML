from abc import ABC, abstractmethod
from collections.abc import Sized
from itertools import repeat
from typing import Any, Iterable

from roleml.core.role.channels import Service, Task, Event
from roleml.core.role.elements import Element
from roleml.library.roles.trainer.base import BaseModelMaintainer
from roleml.library.workload.datasets.bases import IterableDataset
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.models.bases import TrainableModel


__all__ = ['EpochTrainer', 'TrainingPlanner', 'FixedTrainingPlanner']


class TrainingPlanner(ABC):

    @abstractmethod
    def make_plan(self, *_, **options) -> Iterable[dict[str, Any]]: ...

    def report(self, result):
        pass


class FixedTrainingPlanner(TrainingPlanner):

    def make_plan(self, num_steps: int, **hyperparams):
        return repeat(hyperparams, num_steps)


class EpochTrainer(BaseModelMaintainer):

    def __init__(self):
        super().__init__()
        self.current_epoch = -1

    # elements model and dataset_test inherited from base class

    dataset = Element(IterableDataset, default_constructor=DatasetViewFactory)

    planner = Element(TrainingPlanner, default_constructor=FixedTrainingPlanner)

    @Service(expand=True)
    def get_data_size(self, _):
        with self.lock:
            dataset = self.dataset()
            if isinstance(dataset, Sized):  # including the default DatasetView
                return len(dataset)
            raise TypeError('cannot obtain dataset size from this Trainer')

    @Task(expand=True)
    def train(self, _, num_epochs: int = 1, **options):
        with self.lock:
            self.train_impl(num_epochs, **options)
            return self.model().get_params()
    
    @Task(expand=True)
    def train2(self, _, num_epochs: int = 1, **options) -> dict[str, Any]:
        with self.lock:
            metrics = self.train_impl(num_epochs, **options)
            dataset = self.dataset()
            data_size = len(dataset) if isinstance(dataset, Sized) else 0
            return {
                'update': self.model().get_params(),
                'data_size': data_size,
                'metrics': metrics
            }

    epoch_completed = Event()

    def train_impl(self, num_epochs: int, **options) -> dict[str, Any]:
        with self.lock:
            plan = iter(self.planner().make_plan(num_epochs, **options))
            model = self.model()    # type: TrainableModel
            dataset = self.dataset()
            metrics = {}
            for _ in range(num_epochs):
                hyperparams = next(plan)
                self.current_epoch += 1
                metrics = model.train(dataset, **hyperparams)
                self.logger.info(f'local epoch {self.current_epoch} done, result is: {metrics}')
                self.epoch_completed.emit(args={**metrics, 'epoch': self.current_epoch})
            return metrics
