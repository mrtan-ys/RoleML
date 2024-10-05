from concurrent.futures import Future
from typing import Any
from typing_extensions import override

from roleml.core.actor.default.managers.task import (
    ExecutionTaskInfo,
    Promise,
    WaitingTaskInfo,
    TASK_UNIFIED_MESSAGING_CHANNEL,
    TASK_RESULT_UNIFIED_MESSAGING_CHANNEL,
    TaskManager as DefaultTaskManager,
)
from roleml.core.context import ActorProfile, RoleInstanceID
from roleml.core.messaging.exceptions import InvocationRefusedError
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.exceptions import ChannelNotFoundError
from roleml.core.status import ExecutionTicket
from roleml.extensions.containerization.controller.managers.mixin import ContainerInvocationMixin


class TaskManager(DefaultTaskManager, ContainerInvocationMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def _on_receive_task_result_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            task_id = tags['task_id']
            to_instance_name = tags['to_instance_name']
        except KeyError:
            raise AssertionError('unspecified to instance name')

        # 避免node controller对自己的容器的调用的结果被错误地转发到其他容器
        task_exists = False
        with self.remote_tasks_lock:
            if self.waiting_tasks.get(task_id) is not None:
                task_exists = True

        if task_exists or not self._is_role_containerized(to_instance_name): # 第二个条件似乎已经被包含在第一个条件中了，总之先保留
            super()._on_receive_task_result_message(sender, tags, args, payloads)
        else:
            with self._execute_environment_for_role(to_instance_name, None):
                # throws ProcedureInvokerError, just let it propagate
                self._foward_task_result_message_to_container(to_instance_name, sender, tags, args, payloads)

    def _foward_task_result_message_to_container(self, to_instance_name: str, original_sender: str, tags: Tags, args: Args, payloads: Payloads):
        tags = {
            **tags,
            'from_actor_name': original_sender,
        }
        self._invoke_container(
            to_instance_name, TASK_RESULT_UNIFIED_MESSAGING_CHANNEL, tags, args, payloads)

    @override
    def _submit_task_call(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str,
            args: Args, payloads: Payloads) -> Future:
        if not self._is_role_containerized(to_instance_name):
            return super()._submit_task_call(from_actor_name, from_instance_name, 
                                      to_instance_name, to_channel_name, 
                                      args, payloads)
        else:
            ticket = self._acquire_execution(to_instance_name, None)
            description = self._describe_handler(
                from_actor_name, from_instance_name, to_instance_name, to_channel_name)
            try:
                promise = self._forward_task_call_to_container(
                    from_actor_name, from_instance_name, to_instance_name, to_channel_name, args, payloads)
            except InvocationRefusedError as e:
                self.logger.info(f'attempting to call non-existent {description}')
                ticket.stop()
                raise ChannelNotFoundError(f'{description}')
            except Exception as e:
                self.logger.exception(f'error when calling {description} which is in a container')
                ticket.stop()
                raise
            # wait for the result from the container
            future = self.thread_manager.add_threaded_task(self._wait_for_container_task_result, (promise, ticket))
            return future

    def _forward_task_call_to_container(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str, \
            args: Args, payloads: Payloads) -> Promise:
        target = RoleInstanceID(self.context.profile.name, to_instance_name)
        task_id = self._generate_task_id(target, to_channel_name)
        promise = Promise(task_id)
        with self.remote_tasks_lock:
            self.waiting_tasks[task_id] = WaitingTaskInfo(task_id, f'{target}/{to_channel_name}', target, promise)

        try:
            self._invoke_container(
                to_instance_name,
                TASK_UNIFIED_MESSAGING_CHANNEL, 
                {
                    'task_id': task_id,
                    'from_actor_name': from_actor_name,
                    'from_instance_name': from_instance_name,
                    'to_instance_name': to_instance_name,
                    'to_channel_name': to_channel_name
                }, 
                args, payloads
            )
            return promise
        except:
            # remove the temporary task
            with self.remote_tasks_lock:
                del self.waiting_tasks[task_id]
            # rethrow the exception, let `_submit_task_call` handle it
            raise

    def _wait_for_container_task_result(self, task_promise: Promise, ticket: ExecutionTicket, timeout: float | None = None) -> Any:
        try:
            return task_promise.result(timeout)
        finally:
            ticket.stop()

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
