from typing import Any
from typing_extensions import override

from roleml.core.actor.default.managers.service import ServiceManager as DefaultServiceManager, SERVICE_UNIFIED_MESSAGING_CHANNEL
from roleml.core.messaging.exceptions import InvocationRefusedError, InvocationAbortError
from roleml.core.messaging.types import Args, Payloads
from roleml.core.role.exceptions import CallerError, ChannelNotFoundError, HandlerError
from roleml.extensions.containerization.controller.managers.mixin import ContainerInvocationMixin


class ServiceManager(DefaultServiceManager, ContainerInvocationMixin):

    @override
    def initialize(self):
        super().initialize()

    @override
    def _handle_service_call(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str,
            args: Args, payloads: Payloads) -> Any:
        if not self._is_role_containerized(to_instance_name):
            return super()._handle_service_call(from_actor_name, from_instance_name, 
                                                to_instance_name, to_channel_name, 
                                                args, payloads)
        else:
            with self._execute_environment_for_role(to_instance_name, None):
                description = self._describe_handler(
                    from_actor_name, from_instance_name, to_instance_name, to_channel_name)
                try:
                    return self._forward_service_call_to_container(
                        from_actor_name, from_instance_name, to_instance_name, to_channel_name, args, payloads)
                except InvocationRefusedError as e:
                    self.logger.info(f'attempting to call non-existent {description}')
                    raise ChannelNotFoundError(f'{description}')
                except InvocationAbortError as e:# todo
                    self.logger.error(f'failed to call {description} (caller error): {e}')
                    raise CallerError(str(e)) from e
                except Exception as e:# todo
                    self.logger.error(f'failed to call {description} (handler error): {e}')
                    raise HandlerError(str(e)) from e
    
    def _forward_service_call_to_container(
            self, from_actor_name: str, from_instance_name: str, to_instance_name: str, to_channel_name: str, 
            args: Args, payloads: Payloads) -> Any:
        return self._invoke_container(
            to_instance_name,
            SERVICE_UNIFIED_MESSAGING_CHANNEL, 
            {
                'from_actor_name': from_actor_name,
                'from_instance_name': from_instance_name,
                'to_instance_name': to_instance_name,
                'to_channel_name': to_channel_name
            }, 
            args, payloads
        )
