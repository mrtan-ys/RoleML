from typing import Any, Callable

from roleml.core.role.base import Role
from roleml.core.role.channels import Task
from roleml.core.role.elements import Element
from roleml.library.workload.datasets.bases import DataStreams
from roleml.library.workload.models.bases import TestableModel


class AllReduceGlobalCoordinator(Role):

    def __init__(self, num_clients: int = 0):
        super().__init__()
        self.num_clients = num_clients

    model = Element(TestableModel)
    dataset_test = Element(DataStreams, optional=True)

    init_op = Element(Callable[[Any], Any])     # type: Element[Callable[[Any], Any]]

    @Task(expand=True)
    def start(self, _, num_rounds: int):
        model = self.model.get()
        trainers = list(self.ctx.relationships.get_relationship('trainer'))
        initial_model = self.call(trainers[0], 'get-model')
        self.init_op.get()(initial_model)
        self.call_group(trainers, 'apply-update', payloads={'update': initial_model})

        for i in range(num_rounds):
            targets = self.ctx.relationships.get_relationship_view('aggregator')

            # start scatter reduce
            self.call_group(targets, 'scatter-reduce-initialize')
            for _ in range(self.num_clients - 1):
                self.call_group(targets, 'scatter-reduce-step')

            # start all gather
            self.call_group(targets, 'all-gather-initialize')
            for _ in range(self.num_clients - 1):
                self.call_group(targets, 'all-gather-step')
            self.call_group(targets, 'all-reduce-finished')

            # test global model in the global node
            current_model = self.call(trainers[0], 'get-model')
            model.set_params(current_model)
            self.logger.info(f'round {i + 1} completed')
            if self.dataset_test.implemented:
                test_result = model.test(self.dataset_test.get())
                self.logger.info(f'round {i + 1} test result is: {test_result}')
