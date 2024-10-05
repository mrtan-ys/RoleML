from roleml.scripts.runner.recipes.measurement.resource.run import ResourceMeasurementSession


def run_resource_with_stage_pauses(app_name: str):
    with ResourceMeasurementSession(app_name=app_name):
        import time
        from logging import Logger
        from typing import Union

        from roleml.core.actor.base import BaseActor
        from roleml.core.actor.default.bootstrap import ActorBuilder
        from roleml.core.builders.role import RoleBuilder, RoleSpec
        from roleml.core.context import Context

        class CustomRoleBuilder(RoleBuilder):

            def install(self, actor: BaseActor, start: bool = False):
                if self.role is None:
                    raise RuntimeError('role is not built yet, please call build() first')
                actor.add_role(self.name, self.role)
                if elements := self.impls:
                    for element_name, element_impl in elements.items():
                        actor.implement_element(self.name, element_name, element_impl)
                        time.sleep(5)
                if start:
                    actor.start_role(self.name)

        class CustomActorBuilder(ActorBuilder):

            @staticmethod
            def _create_role_builder(name: str, spec: Union[str, RoleSpec]) -> RoleBuilder:
                return CustomRoleBuilder(name, spec)
            
            def _build_messaging(self, ctx: Context, logger: Logger):
                super()._build_messaging(ctx, logger)
                time.sleep(5)

        from roleml.scripts.runner.single import run_actor_from_cli
        run_actor_from_cli(builder_cls=CustomActorBuilder)


if __name__ == '__main__':
    run_resource_with_stage_pauses(app_name='FL')
