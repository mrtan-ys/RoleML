from typing import Any, Optional, Union

from roleml.core.actor.group.makers import Relationship
from roleml.core.actor.group.util.collections import TaskResultCollector
from roleml.core.role.base import Role
from roleml.core.role.channels import Service, Task, Event
from roleml.core.role.elements import Factory
from roleml.shared.collections.merger import ValueMerger, KeyValueMerger, DictKeyValueMerger


class LayeredCollectiveAggregator(Role):

    L0_DEFAULT_COLLECT_CHANNEL = 'train'
    L0_DEFAULT_DISPATCH_CHANNEL = 'apply-update'
    Ln_DEFAULT_COLLECT_CHANNEL = 'aggregate'
    Ln_DEFAULT_DISPATCH_CHANNEL = 'dispatch'

    # default relationship name: source-<layer>

    def __init__(self, layer: int = 0, collect_channel: Optional[str] = None, dispatch_channel: Optional[str] = None,
                 num_steps: int = 1):
        super().__init__()
        # missing argument exception should be handled by the actor (and report to the user)

        self.layer = layer
        self.collect_channel = \
            collect_channel or (self.L0_DEFAULT_COLLECT_CHANNEL if layer == 0 else self.Ln_DEFAULT_COLLECT_CHANNEL)
        self.dispatch_channel = \
            dispatch_channel or (self.L0_DEFAULT_DISPATCH_CHANNEL if layer == 0 else self.Ln_DEFAULT_DISPATCH_CHANNEL)

        self.num_steps = num_steps

    step_completed = Event()
    aggregation_completed = Event()

    merger = Factory(Union[ValueMerger, KeyValueMerger], default_constructor=DictKeyValueMerger)

    @Task(expand=True)
    def aggregate(self, _, num_steps: Optional[int] = None):
        if num_steps is None:
            num_steps = self.num_steps
        group = Relationship(f'source-{self.layer}').targets
        aggregated = None   # for linting only
        for i in range(num_steps):
            merger = TaskResultCollector(group, merger=self.merger())
            self.call_task_group(group, self.collect_channel, on_result=merger.push)
            aggregated = merger.result()
            self.logger.info(f'step {i} aggregation done')
            if i != num_steps - 1:
                # returns after all received
                self.call_group(group, self.dispatch_channel, payloads={'update': aggregated})
            self.step_completed.emit()
        self.logger.info(f'aggregation completed')
        self.aggregation_completed.emit(args={'sources': group})
        return aggregated

    @Service(expand=True)
    def dispatch(self, _, update: Any):
        group = Relationship(f'source-{self.layer}').targets     # add lock if dynamic topology needed
        self.call_group(group, self.dispatch_channel, payloads={'update': update})
