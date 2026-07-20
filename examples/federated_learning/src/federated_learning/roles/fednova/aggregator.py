from collections.abc import Mapping
from typing import Any, Generic
from typing_extensions import TypedDict

from roleml.core.actor.group.util.collections import TaskResultCollector
from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Event, Task
from roleml.core.role.elements import Element
from roleml.core.role.types import Message
from roleml.library.workload.util.arithmetic.base import BasicArithmeticOps
from roleml.library.workload.util.arithmetic.default import DefaultBasicArithmeticOps
from roleml.shared.collections.merger import KeyAgnosticKeyValueMerger, ValueMerger
from roleml.shared.types import Value


class TrainingOutput(TypedDict, Generic[Value], closed=False):
    data_size: int
    steps: int
    update: Value


class StepNormalizingMerger(ValueMerger[TrainingOutput[Value], Value]):

    def __init__(self, ops: BasicArithmeticOps, base: Value):
        self.ops = ops
        self.base = base

        self.total_data_size = 0
        self.total_weighted_steps = 0
        self.all_contribution = None

    def push(self, value: TrainingOutput[Value]):
        self.total_data_size += value['data_size']
        self.total_weighted_steps += value['data_size'] * value['steps']
        # contribution weighted by data size only
        contribution = self.ops.multiply(self.ops.minus(value['update'], self.base), value['data_size'] / value['steps'])
        self.all_contribution = \
            contribution if self.all_contribution is None else self.ops.add(self.all_contribution, contribution)

    def merge(self) -> Value:
        assert self.total_data_size > 0 and self.total_weighted_steps > 0 and self.all_contribution is not None
        effective_steps = self.total_weighted_steps / self.total_data_size
        increment = self.ops.divide(self.all_contribution, self.total_data_size / effective_steps)
        return self.ops.add(self.base, increment)


class StepNormalizingCollectiveAggregator(Role):

    def __init__(self, collect_channel: str = 'train2'):
        super().__init__()
        self.collect_channel = collect_channel

    ops = Element(BasicArithmeticOps, default=DefaultBasicArithmeticOps())

    aggregation_completed = Event()

    @Task(expand=True)
    def aggregate(self, _, base: Any, sources_and_options: Mapping[RoleInstanceID, dict[str, Any]]):
        # serialization may lose RoleInstanceID namedtuple info, but we can reconstruct it
        # you can also require that any call to this channel must put `sources_and_options` in the payloads
        group = sources_and_options.keys()
        merger = TaskResultCollector(group, merger=KeyAgnosticKeyValueMerger(StepNormalizingMerger(self.ops.get(), base)))
        self.call_task_group(
            group, self.collect_channel,
            message_map={src: Message(args=options) for src, options in sources_and_options.items()},
            on_result=merger.push)
        aggregated = merger.result()
        return aggregated
