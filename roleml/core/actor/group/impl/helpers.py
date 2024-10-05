import logging
import pickle
from threading import RLock
from typing import Any, Callable, Iterable, Optional, Mapping, Union

from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.actor.helpers import PayloadsPickledMessage
from roleml.core.actor.manager.bases import BaseServiceManager, BaseTaskManager
from roleml.core.context import RoleInstanceID
from roleml.core.role.types import Message, TaskInvocation

__all__ = ['ServiceCallPerformer', 'TaskCallPerformer']


def pre_serialize_payloads(message: Message) -> PayloadsPickledMessage:
    return PayloadsPickledMessage(message.args, pickle.dumps(message.payloads))


class BaseCallPerformer:

    def __init__(self, local_name: str, caller_instance_name: str, channel_name: str, *,
                 message: Optional[Message],
                 message_map: Optional[Mapping[RoleInstanceID, Message]], messages: Optional[Iterable[Message]]):
        self.local_name = local_name
        self.instance_name = caller_instance_name
        self.channel_name = channel_name

        self.message_map = message_map
        if messages is not None and message is not None:
            raise ValueError('cannot simultaneously specify message(s) for broadcast and scatter')
        self.messages = iter(messages) if messages else None
        self.message = message or Message({}, {})
        self.message_pre_serialized: Optional[PayloadsPickledMessage] = None
        self.pre_serialization_lock = RLock()

    def _find_message(self, target: RoleInstanceID) -> Union[Message, PayloadsPickledMessage]:
        if self.message_map and (target in self.message_map):
            return self.message_map[target]
        else:
            if self.messages:
                try:
                    return next(self.messages)
                except StopIteration:
                    raise RuntimeError('not enough messages to supply group messaging')
            else:
                if target.actor_name == self.local_name:
                    return self.message
                else:
                    if not self.message_pre_serialized:
                        with self.pre_serialization_lock:
                            if not self.message_pre_serialized:
                                self.message_pre_serialized = pre_serialize_payloads(self.message)
                    return self.message_pre_serialized


class ServiceCallPerformer(BaseCallPerformer):

    def __init__(self, local_name: str, caller_instance_name: str, channel_name: str, manager: BaseServiceManager, *,
                 message: Optional[Message],
                 message_map: Optional[Mapping[RoleInstanceID, Message]], messages: Optional[Iterable[Message]],
                 on_result: Optional[Callable[[RoleInstanceID, Any], Any]], on_error: ErrorHandlingStrategy,
                 on_error_cb: Optional[Callable[[RoleInstanceID, Exception], Any]],     # for IGNORE only
                 should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]]):
        super().__init__(local_name, caller_instance_name, channel_name,
                         message=message, message_map=message_map, messages=messages)
        self.logger = logging.getLogger('roleml.managers.service.collective-performer')

        self.manager = manager

        self.on_result = on_result
        self.on_error = on_error
        self.on_error_cb = on_error_cb
        self.should_retry = should_retry if should_retry is not None else lambda i, e: True

    def call(self, target: RoleInstanceID):
        try:
            if self.on_error == ErrorHandlingStrategy.RETRY:
                result = self.call_with_retries(target)
            else:
                result = self.manager.call(self.instance_name, target, self.channel_name, self._find_message(target))
        except Exception as e:
            self.logger.exception(f'error calling service {self.channel_name} of {target} in collective interaction')
            if self.on_error == ErrorHandlingStrategy.KEEP:
                if callable(self.on_result):
                    try:
                        self.on_result(target, e)
                    except Exception:   # noqa: using Logger.exception()
                        self.logger.exception(f'error invoking on_result callback (keeping error) when calling service '
                                              f'channel {self.channel_name} of {target} in collective interaction')
            elif self.on_error == ErrorHandlingStrategy.IGNORE:
                if callable(self.on_error_cb):
                    try:
                        self.on_error_cb(target, e)
                    except Exception:   # noqa: using Logger.exception()
                        self.logger.exception(f'error invoking on_error callback when calling service channel '
                                              f'{self.channel_name} of {target} in collective interaction')
            else:
                raise e
        else:
            if callable(self.on_result):
                try:
                    self.on_result(target, result)
                except Exception:   # noqa: using Logger.exception()
                    self.logger.exception(f'error invoking on_result callback when calling service '
                                          f'channel {self.channel_name} of {target} in collective interaction')

    def call_with_retries(self, target: RoleInstanceID):
        message = self._find_message(target)
        while True:
            try:
                result = self.manager.call(self.instance_name, target, self.channel_name, message)
                return result
            except Exception as e:
                if not self.should_retry(target, e):
                    break


class TaskCallPerformer(BaseCallPerformer):

    def __init__(self, local_name: str, caller_instance_name: str, channel_name: str, manager: BaseTaskManager, *,
                 message: Optional[Message],
                 message_map: Optional[Mapping[RoleInstanceID, Message]], messages: Optional[Iterable[Message]],
                 on_call_error: ErrorHandlingStrategy,
                 on_result: Optional[Callable[[RoleInstanceID, TaskInvocation], Any]],
                 should_retry: Optional[Callable[[RoleInstanceID, Exception], bool]]):
        if on_call_error == ErrorHandlingStrategy.KEEP:
            raise ValueError('task on_call_error does not support ErrorHandlingStrategy.KEEP')

        super().__init__(local_name, caller_instance_name, channel_name,
                         message=message, message_map=message_map, messages=messages)
        self.logger = logging.getLogger('roleml.managers.task.collective-performer')

        self.manager = manager

        self.on_result = on_result or (lambda source, task: None)
        self.on_call_error = on_call_error
        self.should_retry = should_retry if should_retry is not None else lambda i, e: True

        self.id_to_source: dict[int, RoleInstanceID] = {}

    def callback(self, task: TaskInvocation):
        source = self.id_to_source.get(id(task), None)
        try:
            self.on_result(source, task)
        except Exception:   # noqa: using Logger.exception()
            self.logger.exception(f'error invoking on_result callback when calling task '
                                  f'channel {self.channel_name} of {source} in collective interaction')

    def call_task(self, target: RoleInstanceID):
        try:
            if self.on_call_error == ErrorHandlingStrategy.RETRY:
                task = self.call_task_with_retries(target)
            else:
                task = self.manager.call_task(self.instance_name, target, self.channel_name, self._find_message(target))
        except Exception as e:
            self.logger.exception(f'error calling task {self.channel_name} of {target} in collective interaction')
            if self.on_call_error == ErrorHandlingStrategy.IGNORE:
                pass
            else:
                assert self.on_call_error == ErrorHandlingStrategy.RAISE_FIRST
                raise e
        else:
            self.id_to_source[id(task)] = target
            if self.on_result is not None:
                task.add_done_callback(self.callback)

    def call_task_with_retries(self, target: RoleInstanceID) -> TaskInvocation:
        message = self._find_message(target)
        while True:
            try:
                result = self.manager.call_task(self.instance_name, target, self.channel_name, message)
                return result
            except Exception as e:
                if not self.should_retry(target, e):
                    raise
