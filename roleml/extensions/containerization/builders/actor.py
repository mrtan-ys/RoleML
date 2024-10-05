from concurrent.futures import ThreadPoolExecutor
from logging import Logger
import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from typing_extensions import override
import warnings

from roleml.core.actor.base import BaseActor
from roleml.core.builders.actor import (
    ActorBootstrapSpec,
    BaseActorBuilder,
)
from roleml.core.builders.role import RoleBuilder, RoleSpec
from roleml.core.context import Context, RoleInstanceID
from roleml.core.messaging.base import ProcedureInvoker
from roleml.extensions.containerization.builders.role import ContainerizedRoleBuilder
from roleml.extensions.containerization.builders.spec import ActorBootstrapSpec, ContainerizationConfig
from roleml.extensions.containerization.controller.impl import NodeController
from roleml.extensions.containerization.runtime.impl import RoleRuntime
from roleml.extensions.containerization.runtime.managers.wrapper import ProcedureInvokerWrapper


__all__ = ["NodeControllerBuilder", "RoleRuntimeBuilder"]


class NodeControllerBuilder(BaseActorBuilder[BaseActor]):

    def __init__(self):
        super().__init__()

    @override
    def _load_config(self, config: ActorBootstrapSpec):
        super()._load_config(config)

        temp_dir = config.get("temp_dir")
        base_image = config.get("base_image")
        mounts: list[tuple[str, str]] = []

        project_root = self.src or self.workdir
        project_root = Path(project_root).expanduser()
        req_exists = (project_root / "requirements.txt").exists()
        if not base_image:
            base_image = "python:3.11.10-bullseye"
            if not req_exists:
                raise ValueError(
                    "requirements.txt is required "
                    "to install dependencies in containers "
                    "when `base_image` is not specified. "
                    "Please specify base_image or create "
                    f"requirements.txt in `src`: {project_root.absolute()}. "
                )
        else:
            if not req_exists:
                warnings.warn(
                    (
                        f"requirements.txt not find in `src`: {project_root.absolute()}. "
                        "It may cause dependency issues in containers "
                        "if `base_image` does not contain all dependencies"
                    )
                )

        for mount in config.get("mounts") or []:
            split = mount.split(":", 1)
            if len(split) != 2:
                raise ValueError(
                    f"Invalid mount {mount}, should be host_path:container_path"
                )
            mounts.append((split[0], split[1]))

        self.artifacts.containerization_config = ContainerizationConfig(
            project_root=project_root,
            temp_dir=Path(temp_dir) if temp_dir else Path.home() / ".roleml" / "temp",
            base_image=base_image,
            mounts=mounts,
            actor_spec=config,
        )

    @override
    def _create_actor(self, ctx: Context, handshakes: Optional[list[str]]) -> BaseActor:
        actor = NodeController(
            self.profile,
            context=ctx,
            procedure_invoker=self.artifacts.procedure_invoker,
            procedure_provider=self.artifacts.procedure_provider,
            collective_implementor=self.artifacts.collective_implementor,
            handshakes=handshakes,
            containerization_config=self.artifacts.containerization_config,
        )
        return actor

    @override
    def _parse_instance_name(
        self, instance_name: str, default_name: str
    ) -> RoleInstanceID:
        if instance_name[0] == "/":
            return RoleInstanceID(default_name, instance_name[1:])
        li = instance_name.rsplit("/", maxsplit=2)
        # add support for native role
        return (
            RoleInstanceID(li[0], li[1])
            if len(li) == 2
            else RoleInstanceID(li[0], "actor")
        )

    @override
    @staticmethod
    def _create_role_builder(name: str, spec: str | RoleSpec) -> RoleBuilder:
        # todo: 当前只支持Containerized模式，需要支持Default模式
        return ContainerizedRoleBuilder(name, spec)



class RoleRuntimeBuilder(BaseActorBuilder[BaseActor]):

    def __init__(self):
        super().__init__()

    @override
    def _load_config(self, config: ActorBootstrapSpec):
        super()._load_config(config)
        if len(self.roles) > 1:
            raise ValueError("Only one role is allowed in RoleRuntime")

    @override
    def _create_actor(self, ctx: Context, handshakes: Optional[list[str]]) -> BaseActor:
        actor = RoleRuntime(
            self.profile,
            context=ctx,
            procedure_invoker=self.artifacts.procedure_invoker,
            procedure_provider=self.artifacts.procedure_provider,
            collective_implementor=self.artifacts.collective_implementor,
            handshakes=handshakes,
        )
        return actor

    @override
    def _parse_instance_name(
        self, instance_name: str, default_name: str
    ) -> RoleInstanceID:
        if instance_name[0] == "/":
            return RoleInstanceID(default_name, instance_name[1:])
        li = instance_name.rsplit("/", maxsplit=2)
        # add support for native role
        return (
            RoleInstanceID(li[0], li[1])
            if len(li) == 2
            else RoleInstanceID(li[0], "actor")
        )

    @override
    def build(self) -> BaseActor:
        """ Caller should then start the actor with ``actor.start()`` where ``actor`` is the returned Actor object. """
        if not self.profile:
            raise ValueError('missing actor profile')

        ctx = self._build_context()
        root_logger = logging.getLogger('roleml')
        try:
            self._build_logging(ctx, root_logger)   # name of any other logger created: roleml.<custom-name>
            self._build_messaging(ctx, root_logger)
            self.artifacts.procedure_invoker = ProcedureInvokerWrapper(self.artifacts.procedure_invoker)
            root_logger.info('message components built')
            self._add_logger_handlers(ctx, root_logger)
            self._build_roles(root_logger)
            root_logger.info('roles built')
            actor = self._create_actor(ctx, self.handshakes)
            root_logger.info('actor built')
            self._setup(actor)  # actor methods will log the progress
        except Exception:   # noqa: using Logger.exception()
            root_logger.exception('error in building actor')
            raise

        return actor
    
    def _add_logger_handlers(self, ctx: Context, logger: Logger):
        procedure_invoker: ProcedureInvoker = self.artifacts.procedure_invoker
        assert procedure_invoker is not None, "ProcedureInvoker is not built"
        role_name = list(self.roles.keys())[0]
        remote_handler = RemoteLogHandler(role_name, ctx, procedure_invoker)
        # add filter to ignore procedure_invoker logs, otherwise it will cause infinite loop
        remote_handler.addFilter(lambda record: record.name != procedure_invoker.logger.name)
        logger.addHandler(remote_handler)

        
class RemoteLogHandler(logging.Handler):
    def __init__(self, role_name: str, ctx: Context, procedure_invoker: ProcedureInvoker) -> None:
        super().__init__()
        self._role_name = role_name
        self._ctx = ctx
        self._procedure_invoker = procedure_invoker
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="RemoteLogHandler")

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self._executor.submit(self._send_log, record)

    def _send_log(self, record: logging.LogRecord) -> None:
        try:
            _ = self.format(record)  # fill some attributes of record
            tags = {
                "instance_name": self._role_name,
            }
            args = record.__dict__
            args.pop("exc_info", None) # remove traceback object to avoid pickling error
            self._procedure_invoker.invoke_procedure(
                "__node_controller",
                "LOG_EMIT",
                tags=tags,
                args=args,
                payloads=None,
            )
        except:
            self.handleError(record)
