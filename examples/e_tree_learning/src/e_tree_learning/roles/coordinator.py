from roleml.core.role.base import Role
from roleml.core.role.channels import Task, Event
from roleml.core.role.elements import Element
from roleml.library.workload.datasets.bases import DataStreams
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.models.bases import TestableModel


class ELCoordinator(Role):

    ROOT_RELATIONSHIP_NAME = 'root'

    model = Element(TestableModel)
    dataset = Element(DataStreams, default_constructor=DatasetViewFactory)

    round_completed = Event()
    el_completed = Event()

    @Task(expand=True)
    def run(self, _, num_rounds: int = 10):
        self.logger.info(f'start EL run, num of rounds is {num_rounds}')
        model = self.model()        # type: TestableModel
        dataset = self.dataset()    # type: DataStreams     # test dataset
        for i in range(num_rounds):
            # 1. dispatch, propagate to leaf nodes (trainers)
            self.call(ELCoordinator.ROOT_RELATIONSHIP_NAME, 'dispatch', payloads={'update': model.get_params()})
            self.logger.info(f'round {i} updates applied')
            # 2. train, wait for aggregated model to propagate to the root
            future = self.call_task(ELCoordinator.ROOT_RELATIONSHIP_NAME, 'aggregate')
            aggregated_model = future.result()
            self.logger.info(f'round {i} aggregation done')
            # 3. update global model and test
            model.set_params(aggregated_model)
            test_result = model.test(dataset)
            self.logger.info(f'round {i} test result is: {test_result}')
            self.round_completed.emit(args={'round': i, 'result': test_result})
        self.el_completed.emit()
        self.logger.info('EL is done!!!!')
