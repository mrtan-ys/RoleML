from typing import Union
from typing_extensions import override


from roleml.core.actor.default.managers.task import (
    TaskManager as DefaultTaskManager,
)
from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.types import Message, TaskInvocation
from roleml.extensions.containerization.runtime.managers.mixin import InterContainerMixin


class TaskManager(DefaultTaskManager, InterContainerMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def call_task(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  message: Union[Message, PayloadsPickledMessage]) -> TaskInvocation:
        target = self._convert_target_actor_name(target)
        return super().call_task(instance_name, target, channel_name, message)

    @override
    def _on_receive_task_result_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            from_actor_name = tags['from_actor_name']
        except KeyError:
            # raise AssertionError('unspecified from_actor_name in task result message')
            from_actor_name = sender
        from_actor_name = self._convert_actor_name(from_actor_name)
        super()._on_receive_task_result_message(from_actor_name, tags, args, payloads)


    @override
    def _on_receive_task_call_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        # should only be called by node controller.
        sender = self._convert_actor_name(sender)
        super()._on_receive_task_call_message(sender, tags, args, payloads)

    def update_instance_id(
        self, instance_id: RoleInstanceID, new_instance_id: RoleInstanceID
    ):
        with self.remote_tasks_lock:
            for task_id, task_info in self.waiting_tasks.items():
                if task_info.result_source == instance_id:
                    task_info.result_source = new_instance_id

            for task_id, task_info in self.running_tasks.items():
                if task_info.caller == instance_id:
                    task_info.caller = new_instance_id
