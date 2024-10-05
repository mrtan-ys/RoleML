from typing import Optional
from roleml.core.role.base import Role

from roleml.core.role.channels import Event, Task
from roleml.core.role.elements import Element
from roleml.library.workload.datasets.bases import IterableDataset
from roleml.library.workload.datasets.views import DatasetViewFactory
from roleml.library.workload.models.bases import TestableModel


class FLCoordinator(Role):

    model = Element(TestableModel)  # type: Element[TestableModel]
    dataset = Element(IterableDataset, default_constructor=DatasetViewFactory, optional=True)
    # Note: dataset type can be relaxed to DataStreams (only requires __iter__)

    fl_completed = Event()
    round_completed = Event()

    @Task(expand=True)
    def run(self, _, num_rounds: int, select_ratio: Optional[float] = None, count: Optional[int] = None):
        model = self.model()        # type: TestableModel
        for i in range(num_rounds):
            self.logger.info(f'round {i} started')
            group = self.call('client-selector', 'select-client', args={'ratio': select_ratio, 'count': count})
            self.logger.debug(f'round {i} selected clients are: {[ins.actor_name for ins in group]}')
            configurations = self.call('configurator', 'configure', payloads={'clients': group})
            self.call_group(group, 'apply-update', payloads={'update': model.get_params()})
            # using payloads allows us to deploy the aggregator somewhere else
            future = self.call_task('aggregator', 'aggregate', payloads={'sources_and_options': configurations})
            aggregated_model = future.result()
            model.set_params(aggregated_model)
            try:
                dataset = self.dataset()    # type: IterableDataset
            except Exception:   # noqa: dataset impl not provided (default view factory will not work)
                self.round_completed.emit(args={'round': i})
            else:
                test_result = model.test(dataset)
                self.logger.info(f'round {i} test result is: {test_result}')
                self.round_completed.emit(args={'round': i, 'result': test_result})
        self.fl_completed.emit()
        self.logger.info('FL is done!!!!')
