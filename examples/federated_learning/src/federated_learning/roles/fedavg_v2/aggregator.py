from typing import Any, Mapping

from roleml.core.actor.group.makers import RoleInstances
from roleml.core.actor.group.util.collections import TaskResultCollector
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Task, Event
from roleml.core.role.elements import Factory
from roleml.core.role.types import Message
from roleml.library.workload.util.collections.merger.base import WeightedMerger, DefaultWeightedMerger
from roleml.shared.collections.merger import DictKeyValueMerger


class WeightedCollectiveAggregator(Role):

    def __init__(self, collect_channel: str = 'train', weight_source_channel: str = 'get-data-size'):
        super().__init__()
        self.collect_channel = collect_channel
        self.weight_source_channel = weight_source_channel

    merger = Factory(WeightedMerger, default_constructor=DefaultWeightedMerger)

    aggregation_completed = Event()

    @Task(expand=True)
    def aggregate(self, _, sources_and_options: Mapping[tuple[str, str], Mapping[str, Any]]):
        # serialization may lose RoleInstanceID namedtuple info, but we can reconstruct it
        group = RoleInstances(sources_and_options.keys()).targets
        # first collect data sample counts
        merger = DictKeyValueMerger()
        self.call_group(group, self.weight_source_channel, on_result=merger.push)
        weights = merger.merge()
        # then collect result and merge
        merger = TaskResultCollector(group, merger=self.merger(weights))
        self.call_task_group(
            group, self.collect_channel,
            message_map={RoleInstanceID(*source): Message(options) for source, options in sources_and_options.items()},
            on_result=merger.push)
        aggregated = merger.result()
        self.logger.info('aggregation completed')
        self.aggregation_completed.emit(args={'sources': group})
        return aggregated
