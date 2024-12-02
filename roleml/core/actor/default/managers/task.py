import logging
import pickle
import time
from concurrent.futures import Future, TimeoutError
from dataclasses import dataclass
from functools import wraps
from threading import Condition, RLock
from typing import Any, Callable, Generic, Optional, Union

from fasteners import ReaderWriterLock

from roleml.core.actor.default.managers.channels import ChannelCallManagerMixin
from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.actor.manager import BaseTaskManager
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.exceptions import InvocationRefusedError, ProcedureInvokerError
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.base import Role
from roleml.core.role.exceptions import ChannelNotFoundError, TaskResultTimeoutError, HandlerError, CallerError
from roleml.core.role.types import TaskInvocation, Message
from roleml.core.status import ExecutionTicket, Status
from roleml.shared.types import T, LOG_LEVEL_INTERNAL as INTERNAL


# region helpers

class WrappedFuture(Generic[T]):
    """ TaskInvocation implementation for local messages. Wraps the original concurrent.futures.Future class to adjust
    the exception classes. """

    __slots__ = ('future', 'channel', '_description')

    LOGGER = logging.getLogger('roleml.managers.task.wrapped-future')

    def __init__(self, future: Future, channel: str, description: str = ''):
        self.future = future
        self.channel = channel
        self._description = description

    def result(self, timeout: Optional[float] = None) -> T:
        try:
            return self.future.result(timeout)
        except (HandlerError, CallerError):
            raise
        except TimeoutError as e:
            raise TaskResultTimeoutError(str(e)) from e
        except Exception as e:
            raise HandlerError(str(e)) from e

    def exception(self, timeout: Optional[float] = None) -> Optional[Exception]:
        e = self.future.exception(timeout)
        if e:
            if isinstance(e, (HandlerError, CallerError)):
                return e
            if isinstance(e, TimeoutError):
                e_wrap = TaskResultTimeoutError(str(e))
            else:
                e_wrap = HandlerError(str(e))
            e_wrap.__cause__ = e
            return e_wrap
        return None

    def add_done_callback(self, func):
        @wraps(func)
        def cb_wrapped(_future):
            try:
                func(self)
            except Exception:  # noqa: using Logger.exception()
                WrappedFuture.LOGGER.exception(f'failed to execute callback {func!s} for task {self._description}')
        self.future.add_done_callback(cb_wrapped)


class Promise(Generic[T]):
    """ TaskInvocation implementation for remote messages. """

    __slots__ = ('_condition', '_done', '_result', '_exception', '_callbacks', '_description')

    LOGGER = logging.getLogger('roleml.managers.task.promise')
    LOCK = RLock()

    def __init__(self, description: str = ''):
        self._condition = Condition(Promise.LOCK)
        self._done = False
        self._result = None
        self._exception = None
        self._callbacks = []
        self._description = description

    def set_result(self, result):
        with self._condition:
            assert not self._done, f'attempting to set result of {self._description} after done'
            if isinstance(result, Exception):
                assert isinstance(result, (HandlerError, CallerError))
                self._exception = result
                self._result = None
            else:
                self._result = result
                self._exception = None
            self._done = True
            self._condition.notify_all()
            Promise.LOGGER.log(INTERNAL, f'task result for {self._description} is ready to be fetched, the execution '
                                         f'is a {"success" if self._exception is None else "failure"}')
        self._invoke_callbacks()

    def result(self, timeout: Optional[float] = None) -> T:
        if self._done:
            return self._get_result()
        with self._condition:
            self._condition.wait(timeout)
            if self._done:
                return self._get_result()
            Promise.LOGGER.info(f'result of {self._description} timeout after {timeout} seconds')
            raise TaskResultTimeoutError(f'{self._description}')

    def _get_result(self) -> T:
        assert self._done, f'attempting to call _get_result of {self._description} before done'
        if self._exception:
            raise self._exception
        return self._result     # type: ignore

    def exception(self, timeout: Optional[float] = None) -> Optional[Exception]:
        if self._done:
            return self._exception
        with self._condition:
            self._condition.wait(timeout)
            if self._done:
                return self._exception
            Promise.LOGGER.info(f'result of {self._description} timeout after {timeout} seconds')
            raise TaskResultTimeoutError(f'{self._description}')

    def add_done_callback(self, func):
        with self._condition:
            if self._done:
                self._invoke_callback(func)
            else:
                self._callbacks.append(func)

    def _invoke_callbacks(self):
        for cb in self._callbacks:
            self._invoke_callback(cb)

    def _invoke_callback(self, cb):
        try:
            cb(self)
        except Exception:   # noqa: using Logger.exception()
            Promise.LOGGER.exception(f'failed to execute callback {cb!s} for task {self._description}')


@dataclass
class ExecutionTaskInfo:    # maintained by task handler side
    task_id: str
    channel: str
    caller: RoleInstanceID


@dataclass
class WaitingTaskInfo:      # maintained by task caller side
    task_id: str
    full_channel_name: str
    result_source: RoleInstanceID
    promise: Promise

# endregion


TASK_UNIFIED_MESSAGING_CHANNEL = 'TASK'
TASK_RESULT_UNIFIED_MESSAGING_CHANNEL = 'TASK_RESULT'


class TaskManager(BaseTaskManager, ChannelCallManagerMixin):

    channels: dict[str, dict[str, Callable[[RoleInstanceID, Args, Payloads], Any]]]
    channel_lock: ReaderWriterLock
    """ Locks outer dict of `channels` """

    # for remote tasks
    running_tasks: dict[int, ExecutionTaskInfo]     # id of local future => ExecutionTaskInfo (where to return on done)
    waiting_tasks: dict[str, WaitingTaskInfo]       # task_id => WaitingTaskInfo (where to fetch and which Promise)
    remote_tasks_lock: RLock    # shared by both dicts

    def initialize(self):
        self.channels = {}
        self.channel_lock = ReaderWriterLock()
        self.running_tasks = {}
        self.waiting_tasks = {}
        self.remote_tasks_lock = RLock()
        self.logger = logging.getLogger('roleml.managers.task')
        self.procedure_provider.add_procedure(
            TASK_UNIFIED_MESSAGING_CHANNEL, self._on_receive_task_call_message)
        self.procedure_provider.add_procedure(
            TASK_RESULT_UNIFIED_MESSAGING_CHANNEL, self._on_receive_task_result_message)
        self.role_status_manager.add_callback(Status.FINALIZING, self._on_role_status_finalizing)

    def add_role(self, role: Role):
        with self.channel_lock.write_lock():
            tasks = self.channels[role.name] = {}
        for channel_name, attribute_name in role.tasks.items():
            handler = getattr(role, attribute_name)
            tasks[channel_name] = handler

    def _on_role_status_finalizing(self, instance_name: str, _):
        with self.channel_lock.write_lock():
            del self.channels[instance_name]

    def _is_local_instance(self, instance_name: RoleInstanceID) -> bool:
        return instance_name.actor_name == self.context.profile.name

    def call_task(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                  message: Union[Message, PayloadsPickledMessage]) -> TaskInvocation:
        self.logger.debug(f'calling task on {target}/{channel_name} from {instance_name}, args = {message.args}')
        if self._is_local_instance(target):
            return self._call_local(instance_name, target.instance_name, channel_name, message)
        else:
            return self._call_remote(instance_name, target, channel_name, message)

    def _call_local(self, from_instance_name: str, to_instance_name, channel_name: str,
                    message: Union[Message, PayloadsPickledMessage]) -> WrappedFuture:
        from_actor_name = self.context.profile.name
        future = self._submit_task_call(
            from_actor_name, from_instance_name, to_instance_name, channel_name, message.args,
            pickle.loads(message.payloads) if isinstance(message, PayloadsPickledMessage) else message.payloads)
        wrapped_future = WrappedFuture(future, f'{to_instance_name}/{channel_name}')
        wrapped_future.add_done_callback(self._after_local_task)
        return wrapped_future

    def _after_local_task(self, future: WrappedFuture):
        e = future.exception()
        if e:
            self.logger.error(f'failed to handle task call to {future.channel}: {e}')

    def _call_remote(self, instance_name: str, target: RoleInstanceID, channel_name: str,
                     message: Union[Message, PayloadsPickledMessage]) -> Promise:
        task_id = self._generate_task_id(target, channel_name)
        promise = Promise(task_id)
        # task information must be registered first in case that the handler finishes very fast
        with self.remote_tasks_lock:
            self.waiting_tasks[task_id] = WaitingTaskInfo(task_id, f'{target}/{channel_name}', target, promise)

        tags = {'task_id': task_id, 'from_instance_name': instance_name, 'to_instance_name': target.instance_name,
                'to_channel_name': channel_name}
        try:
            self.procedure_invoker.invoke_procedure(
                target.actor_name, TASK_UNIFIED_MESSAGING_CHANNEL, tags, message.args, message.payloads)
            return promise
        except InvocationRefusedError as e:
            with self.remote_tasks_lock:
                del self.waiting_tasks[task_id]
            self.logger.error(f'cannot find task channel {target.instance_name}/{channel_name}')
            raise ChannelNotFoundError(str(e)) from None
        except ProcedureInvokerError:
            with self.remote_tasks_lock:
                del self.waiting_tasks[task_id]
            self.logger.exception(f'failed to call task {target.instance_name}/{channel_name}')
            raise CallerError(f'cannot perform task call to {target}/{channel_name}') from None
        except Exception as e:
            with self.remote_tasks_lock:
                del self.waiting_tasks[task_id]
            self.logger.exception(f'error when attempting to call task {target.instance_name}/{channel_name}')
            raise HandlerError(str(e)) from None

    def _generate_task_id(self, target: RoleInstanceID, channel_name: str):
        return f'{self.context.profile.name}-{target}/{channel_name}-{time.time_ns()}'

    def _on_receive_task_call_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        try:
            task_id: str = tags['task_id']
            from_instance_name: str = tags['from_instance_name']
            to_instance_name: str = tags['to_instance_name']
            to_channel_name: str = tags['to_channel_name']
        except KeyError:
            raise AssertionError('incomplete task call info')

        try:
            future = self._submit_task_call(
                sender, from_instance_name, to_instance_name, to_channel_name, args, payloads)
        except ChannelNotFoundError as e:
            raise InvocationRefusedError(str(e))
        else:
            caller = RoleInstanceID(sender, from_instance_name)
            execution_info = ExecutionTaskInfo(task_id, f'{to_instance_name}/{to_channel_name}', caller)
            with self.remote_tasks_lock:
                self.running_tasks[id(future)] = execution_info
            try:
                future.add_done_callback(self._send_task_result)
            except Exception:
                self.logger.exception(f'failed to send task result #{task_id}')
                raise

            return task_id  # unimportant

    def _send_task_result(self, future: Future):    # future is local Future representing the execution thread
        with self.remote_tasks_lock:
            info = self.running_tasks.pop(id(future))
        common_tags = {'task_id': info.task_id, 'to_instance_name': info.caller.instance_name,}
        e = future.exception()
        if e:
            self.logger.error(f'failed to handle task call {info.channel} from {info.caller}: {e}')
            tags: dict[str, str] = {**common_tags, 'error': 'True'}
            if isinstance(e, CallerError):
                args = {'error_type': 'caller', 'error_message': str(e)}
            else:
                args = {'error_type': 'handler'}
            payloads = {}
        else:
            tags, args, payloads = {**common_tags}, {}, {}
            result = future.result()
            if result is not None:
                payloads['result'] = result
        self.procedure_invoker.invoke_procedure(
            info.caller.actor_name, TASK_RESULT_UNIFIED_MESSAGING_CHANNEL, tags, args, payloads)

    def _on_receive_task_result_message(self, sender: str, tags: Tags, args: Args, payloads: Payloads):
        task_id = tags['task_id']
        with self.remote_tasks_lock:
            try:
                info = self.waiting_tasks.pop(task_id)
            except KeyError:
                # should not happen normally through
                raise ProcedureInvokerError(f'task result for invalid task ID {task_id}')
        if sender != info.result_source.actor_name:
            self.logger.warning(f'unexpected result source for task #{task_id}: '
                                f'expected {info.result_source.actor_name}, got {sender}')

        promise = info.promise
        if 'error' in tags:
            if args['error_type'] == 'caller':
                promise.set_result(CallerError(args.get('error_message')))
            else:
                promise.set_result(HandlerError(f'task {info.full_channel_name}'))
            # self.logger.error(f'failed to call task {info.full_channel_name}: {e}')
        else:
            promise.set_result(None if not payloads else payloads['result'])

    def _submit_task_call(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str,
            args: Args, payloads: Payloads) -> Future:
        ticket = self._acquire_execution(to_instance_name, None)
        try:
            with self.channel_lock.read_lock():
                handler = self.channels[to_instance_name][to_channel_name]
        except KeyError:
            description = self._describe_handler(
                from_actor_name, from_instance_name, to_instance_name, to_channel_name)
            self.logger.info(f'attempting to call non-existent {description}')
            ticket.stop()
            raise ChannelNotFoundError(f'{description}')
        except Exception:
            ticket.stop()
            raise
        else:
            # for simplicity, we do not perform additional checks on task call before putting in a thread
            thread_args = \
                from_actor_name, from_instance_name, to_instance_name, to_channel_name, handler, ticket, args, payloads
            future = self.thread_manager.add_threaded_task(self._handle_task_call, thread_args)
            return future

    def _handle_task_call(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str,
            handler: Callable[[RoleInstanceID, Args, Payloads], Any], ticket: ExecutionTicket,
            args: Args, payloads: Payloads) -> Any:
        try:
            return self._handle_call_impl(
                from_actor_name, from_instance_name, to_instance_name, to_channel_name, handler, args, payloads)
        except AssertionError as e:
            raise CallerError(str(e)) from e
        finally:
            ticket.stop()

    def _describe_handler(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, channel_name: str) -> str:
        return f'task channel {to_instance_name}/{channel_name}'
