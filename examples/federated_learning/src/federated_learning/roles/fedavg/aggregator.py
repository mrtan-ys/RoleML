from typing import Any, Mapping, Optional, Union

from roleml.core.actor.group.util.collections import TaskResultCollector
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Event, Task
from roleml.core.role.elements import Factory
from roleml.core.role.types import Message
from roleml.shared.collections.merger import ValueMerger, KeyValueMerger, DictKeyValueMerger


class CollectiveAggregator(Role):

    def __init__(self, collect_channel: str = 'train'):
        super().__init__()
        self.collect_channel = collect_channel

    merger = Factory(Union[ValueMerger, KeyValueMerger], default_constructor=DictKeyValueMerger)

    aggregation_completed = Event()

    @Task(expand=True)
    def aggregate(self, _, sources_and_options: Mapping[RoleInstanceID, dict[str, Any]],
                  collect_channel: Optional[str] = None):
        # serialization may lose RoleInstanceID namedtuple info, but we can reconstruct it
        # you can also require that any call to this channel must put `sources_and_options` in the payloads
        group = sources_and_options.keys()
        merger = TaskResultCollector(group, merger=self.merger())
        self.call_task_group(
            group, collect_channel or self.collect_channel,
            message_map={src: Message(args=options) for src, options in sources_and_options.items()},
            on_result=merger.push)
        aggregated = merger.result()
        self.aggregation_completed.emit(args={'sources': list(group)})
        return aggregated
