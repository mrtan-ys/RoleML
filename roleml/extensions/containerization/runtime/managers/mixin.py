from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import Context, RoleInstanceID


class InterContainerMixin:
    
    context: Context
    role_status_manager: RoleStatusManager
    
    def _convert_target_actor_name(self, target: RoleInstanceID) -> RoleInstanceID:
        print(f"target: {target} {self.context.profile.name=}")
        if target.actor_name != self.context.profile.name:
            return target
        if target.instance_name in self.role_status_manager.ctrls:
            # target is a native role
            return RoleInstanceID("__this", target.instance_name)
        # target is in another container
        return target
