from math import ceil
from typing import Any, Protocol
from typing_extensions import override, TypedDict

from roleml.core.role.channels import Task
from roleml.core.role.elements import Element
from roleml.library.roles.trainer.epoch import EpochTrainer, FullTrainingOutput
from roleml.library.workload.models.bases import TrainableModel


class TrainingMetrics(TypedDict, closed=False):

    batches: int    # may contain other items (open TypedDict)


class StepAwareTrainableModel(TrainableModel, Protocol):

    def train(self, data, **options) -> TrainingMetrics: ...    # type: ignore


class StepsAwareTrainer(EpochTrainer):

    # NOTE: due to related typing mechanisms, type checking will not be strictly enforced here
    # therefore this element redeclaration (including the type definitions above)
    # does not contribute much in terms of runtime behavior
    # but it helps to clarify what is needed from the workload implementations
    model = Element(StepAwareTrainableModel)

    @override
    @Task(expand=True)
    def train2(self, _, num_epochs: int = 1, **options) -> dict[str, Any]:
        # TODO better way to override
        result = super().train2.__wrapped__(self, _, num_epochs, **options)     # type: FullTrainingOutput
        # assert 'batches' in result['metrics']
        total_steps = result['num_epochs'] * result['metrics'].get('batches', 1)
        return {
            'update': result['update'],
            'steps': total_steps,
            'data_size': result['data_size']
        }
