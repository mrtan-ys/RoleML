from typing import Any

from roleml.core.context import ActorNotFoundError, Context
from roleml.core.messaging.base import ProcedureInvoker
from roleml.core.messaging.types import Args, Payloads, Tags


class ContainerInvocationMixin:

    context: Context
    procedure_invoker: ProcedureInvoker

    def _is_role_containerized(self, instance_name: str) -> bool:
        try:
            self.context.contacts.get_actor_profile(
                f"{self.context.profile.name}_{instance_name}"
            )
            return True
        except ActorNotFoundError:
            return False

    def _invoke_container(
        self,
        target_instance_name: str,
        name: str,
        tags: Tags | None = None,
        args: Args | None = None,
        payloads: Payloads | bytes | None = None,
    ) -> Any:
        profile = self.context.contacts.get_actor_profile(
            f"{self.context.profile.name}_{target_instance_name}"
        )
        return self.procedure_invoker.invoke_procedure(
            profile, name, tags, args, payloads
        )
