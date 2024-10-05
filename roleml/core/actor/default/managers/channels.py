import logging
from contextlib import contextmanager
from typing import Any, Callable, Optional

from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import RoleInstanceID
from roleml.core.messaging.exceptions import InvocationRedirectError
from roleml.core.messaging.types import Args, Payloads
from roleml.core.role.exceptions import NoSuchRoleError, CallerError, HandlerError
from roleml.core.status import ExecutionTicket, RoleOffloadedError, StatusError


class ChannelCallManagerMixin:

    # initialized by manager
    logger: logging.Logger
    role_status_manager: RoleStatusManager

    @contextmanager
    def _execute_environment_for_role(self, instance_name: str, timeout: Optional[int] = 0):
        ticket = self._acquire_execution(instance_name, timeout)
        try:
            yield ticket
        finally:
            ticket.stop()
    
    def _acquire_execution(self, instance_name: str, timeout: Optional[int] = 0) -> ExecutionTicket:
        try:
            ctrl = self.role_status_manager.ctrl(instance_name)
            return ctrl.acquire_execution(timeout=timeout)
        except NoSuchRoleError as e:
            raise CallerError(f'the role {instance_name} does not exist') from e
        except RoleOffloadedError as e:
            raise InvocationRedirectError(e.offloaded_to.name) from e
        except StatusError as e:
            raise HandlerError(f'the role {instance_name} is not open') from e

    def _handle_call_impl(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, channel_name: str,
            handler: Callable[[RoleInstanceID, Args, Payloads], Any], args: Args, payloads: Payloads) -> Any:
        """ ``channel_name`` is handler side for service and task and caller side for event. """
        handler_desc = self._describe_handler(from_actor_name, from_instance_name, to_instance_name, channel_name)
        caller = RoleInstanceID(from_actor_name, from_instance_name)
        self.logger.debug(f'received call to {handler_desc}, caller = {caller!s}, {args=}')
        try:
            return handler(caller, args, payloads)
        except Exception:
            self.logger.exception(f'call to {handler_desc} fails, caller = {caller!s}, {args=}')
            raise

    def _describe_handler(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, channel_name: str
    ) -> str: ...
