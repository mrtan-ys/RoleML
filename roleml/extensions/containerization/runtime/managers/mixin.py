
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
            return target
        # target is in another container
        return RoleInstanceID("__node_controller", target.instance_name)
    
    def _convert_actor_name(self, actor_name) -> str:
        if actor_name == self.context.profile.name:
            # runtime's profile name is same as the controller's actor name
            return "__node_controller"
        return actor_name