from roleml.core.role.base import Role
from roleml.extensions.plugins.partner.manager import PartnerManager
from tests.fixtures.actors.template import *


class TestPartnerActor(ActorTemplate):

    def __init__(self, profile: ActorProfile, *, context: Optional[Context] = None,
                 procedure_invoker: ProcedureInvoker, procedure_provider: ProcedureProvider,
                 collective_implementor: CollectiveImplementor,
                 handshakes: Optional[list[str]] = None):
        super().__init__(profile, context=context,
                         procedure_invoker=procedure_invoker, procedure_provider=procedure_provider,
                         collective_implementor=collective_implementor, handshakes=handshakes)

        init_args = (self.ctx, self.thread_manager, self.role_status_manager, procedure_invoker, procedure_provider)
        self.partner_manager = PartnerManager(*init_args)

    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        self.partner_manager.add_role(role)
