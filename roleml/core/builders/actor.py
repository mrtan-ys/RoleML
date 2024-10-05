import logging
import os
import sys
from abc import ABC, abstractmethod
from types import SimpleNamespace
from typing import Any, Generic, Iterable, Literal, Mapping, Optional, Union
from typing_extensions import TypedDict, Required, NamedTuple

from roleml.core.actor.group.base import CollectiveImplementor
from roleml.core.builders.helpers import ActorType
from roleml.core.builders.role import RoleBuilder, RoleElementPresetSpec, RoleSpec
from roleml.core.context import RoleInstanceID, ActorProfile, Context
from roleml.core.messaging.base import MessagingComponent, ProcedureInvoker, ProcedureProvider
from roleml.core.messaging.null import MessagingComponentDisabled, ProcedureInvokerDisabled, ProcedureProviderDisabled
from roleml.core.role.base import Role
from roleml.shared.importing import as_class, Descriptor, Spec, AnyType
from roleml.shared.types import LogLevel

__all__ = ['LogConsoleType', 'ActorBootstrapSpec', 'ComponentConfig', 'BaseActorBuilder']


LogConsoleType = Literal['single', 'shared']


class ActorBootstrapSpec(TypedDict, total=False):

    # profile
    name: Required[str]
    address: Required[str]

    # messaging
    procedure_invoker: Union[str, type[ProcedureInvoker], Spec[ProcedureInvoker]]
    procedure_provider: Union[str, type[ProcedureProvider], Spec[ProcedureProvider]]
    messaging_component: Union[str, type[MessagingComponent], Spec[MessagingComponent]]
    """ If specified, both `procedure_invoker` and `procedure_provider` will be ignored. """
    collective_implementor: Union[str, type[CollectiveImplementor], Spec[CollectiveImplementor]]

    # context
    roles: dict[str, Union[str, RoleSpec]]
    relationships: dict[str, list[str]]
    relationship_links: dict[str, str]
    """ Only used in context construction; will not be kept """
    contacts: dict[str, str]
    """ actor name => address """
    handshakes: list[str]
    handwaves: list[str]

    # role element preset
    element_preset: dict[str, RoleElementPresetSpec]

    # misc
    workdir: str
    """ Default to . """
    src: str
    """ Default to workdir specified """
    log_file_path: str
    """ Default to empty string or None for logging disabled; supports templates
    (please disable log to file when running multiple actors in the same process) """
    log_file_level: LogLevel
    log_console_type: LogConsoleType
    """ Default to 'single' """
    log_console_level: LogLevel
    debug: bool
    """ default to False; if True, will set all logging levels to DEBUG (ignoring all other configs) """
    seed: int
    """ default to -1 (will be saved to context when determined) """


class ComponentConfig(NamedTuple, Generic[AnyType]):
    cls: Descriptor[AnyType]
    options: dict[str, Any] = {}


class BaseActorBuilder(Generic[ActorType], ABC):
    # not thread-safe, but should be OK

    procedure_invoker: ComponentConfig
    procedure_provider: ComponentConfig
    messaging_component: ComponentConfig    # will ignore the above two if this is specified
    collective_implementor: ComponentConfig

    artifacts: SimpleNamespace
    """ used to store intermediate artifacts or artifacts that will be passed to actor """

    def __init__(self):
        self.profile: ActorProfile = None       # type: ignore  # to be filled later

        self.relationships: dict[str, Iterable[RoleInstanceID]] = {}
        self.relationship_links: dict[str, str] = {}    # only used in context construction; will not be kept
        self.contacts: dict[str, str] = {}      # actor name => address
        self.handshakes: list[str] = []
        self.handwaves: list[str] = []

        self.native_role: Optional[type[Role]] = None
        self.roles: dict[str, RoleBuilder] = {}

        self.workdir: str = '.'
        self.src: Optional[str] = None
        self.log_file_path: Optional[str] = None
        self.log_file_level: LogLevel = 'INFO'
        self.log_console_type: LogConsoleType = 'single'
        self.log_console_level: LogLevel = 'INFO'
        self.debug: bool = False
        self.seed: int = -1

        self._config_loaded: bool = False

        self.artifacts = SimpleNamespace()

    def load_config(self, config: ActorBootstrapSpec):
        """ Load actor config from a config dict. This dict may be parsed from an external file (e.g. YAML).
        Please only call this method once. To load another config file, please create another actor builder. """
        if self._config_loaded:
            raise RuntimeError('load_config() called twice')
        self._load_config(config)
        self._config_loaded = True

    def _load_config(self, config: ActorBootstrapSpec):
        # TODO schema validation
        name, address = config['name'], config['address']
        self.profile = ActorProfile(name, address)

        if spec_messaging := config.get('messaging_component'):
            self.messaging_component = self._create_component_config(spec_messaging)
        else:
            if spec_invoker := config.get('procedure_invoker'):
                self.procedure_invoker = self._create_component_config(spec_invoker)
            if spec_provider := config.get('procedure_provider'):
                self.procedure_provider = self._create_component_config(spec_provider)

        if spec_collective_implementor := config.get('collective_implementor'):
            self.collective_implementor = self._create_component_config(spec_collective_implementor)

        spec_roles = config.get('roles', {})
        for role_name, spec in spec_roles.items():
            self.roles[role_name] = self._create_role_builder(role_name, spec)

        conf_relationships = config.get('relationships', {})
        for relationship_name, instance_names in conf_relationships.items():
            if isinstance(instance_names, str):
                self.relationships[relationship_name] = [self._parse_instance_name(instance_names, name)]
            else:
                assert isinstance(instance_names, list)
                self.relationships[relationship_name] = [self._parse_instance_name(i, name) for i in instance_names]

        self.relationship_links = config.get('relationship_links', {})
        self.contacts = config.get('contacts', {})
        self.handshakes = config.get('handshakes', [])
        self.handwaves = config.get('handwaves', [])

        if element_preset_mapping := config.get('element_preset', {}):
            for role_cls, spec in element_preset_mapping.items():
                RoleBuilder.update_element_preset(role_cls, spec.get('elements', {}), spec.get('on_conflict'))

        self.workdir = config.get('workdir', '.')
        self.src = config.get('src', None)
        self.log_file_path = config.get('log_file_path', None)
        self.log_file_level = config.get('log_file_level', 'INFO')
        self.log_console_type = config.get('log_console_type', 'single')
        self.log_console_level = config.get('log_console_level', 'INFO')
        self.debug = config.get('debug', False)
        self.seed = config.get('seed', -1)

    @staticmethod
    def _create_component_config(spec: Union[str, type, Mapping]) -> ComponentConfig:
        if isinstance(spec, (str, type)):
            return ComponentConfig(spec)
        else:
            return ComponentConfig(spec['type'], spec.get('options', {}))
    
    @staticmethod
    def _create_role_builder(name: str, spec: Union[str, RoleSpec]) -> RoleBuilder:
        return RoleBuilder(name, spec)
    
    def _parse_instance_name(self, instance_name: str, default_name: str) -> RoleInstanceID:
        if instance_name[0] == '/':
            return RoleInstanceID(default_name, instance_name[1:])
        li = instance_name.rsplit('/', maxsplit=2)
        if len(li) != 2:
            raise ValueError(f'invalid role instance {instance_name}')
        return RoleInstanceID(li[0], li[1])

    def build(self) -> ActorType:
        """ Caller should then start the actor with ``actor.start()`` where ``actor`` is the returned Actor object. """
        if not self.profile:
            raise ValueError('missing actor profile')

        ctx = self._build_context()
        root_logger = logging.getLogger('roleml')
        try:
            self._build_logging(ctx, root_logger)   # name of any other logger created: roleml.<custom-name>
            self._build_messaging(ctx, root_logger)
            root_logger.info('message components built')
            self._build_roles(root_logger)
            root_logger.info('roles built')
            actor = self._create_actor(ctx, self.handshakes)
            root_logger.info('actor built')
            self._setup(actor)  # actor methods will log the progress
        except Exception:   # noqa: using Logger.exception()
            root_logger.exception('error in building actor')
            raise

        return actor

    def _build_context(self) -> Context:
        return Context.build(
            self.profile, workdir=self.workdir, src=self.src, seed=self.seed,
            initial_relationships=self.relationships, initial_relationship_links=self.relationship_links,
            initial_contacts=(ActorProfile(name, address) for name, address in self.contacts.items()))

    @abstractmethod
    def _create_actor(self, ctx: Context, handshakes: Optional[list[str]]) -> ActorType: ...

    def _build_logging(self, ctx: Context, root_logger: logging.Logger = logging.getLogger('roleml')):
        root_logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        formatter = logging.Formatter(fmt='%(asctime)s %(levelname)7s | [%(name)s] %(message)s')

        if self.log_console_level.upper() != 'DISABLED' and not root_logger.hasHandlers():
            # supports single-process DML simulation; only one handler will be added
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setLevel(
                'DEBUG' if self.debug and self.log_console_level != 'INTERNAL' else self.log_console_level)
            if self.log_console_type == 'shared':
                stdout_handler.setFormatter(
                    logging.Formatter(fmt='%(asctime)s %(levelname)7s - %(processName)20s | [%(name)s] %(message)s'))
            else:
                stdout_handler.setFormatter(formatter)
            root_logger.addHandler(stdout_handler)

        if self.log_file_path and self.log_file_level.upper() != 'DISABLED':
            log_path = ctx.apply_general_template(self.log_file_path)
            log_abspath = os.path.abspath(os.path.join(ctx.workdir, log_path))
            if not os.path.exists(log_abspath):
                os.makedirs(log_abspath, exist_ok=True)
            log_filename = os.path.join(log_abspath, f'{self.profile.name}-{ctx.start_time_formatted}.log')
            file_handler = logging.FileHandler(log_filename)
            file_handler.setLevel(
                'DEBUG' if self.debug and self.log_file_level != 'INTERNAL' else self.log_file_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        root_logger.info(f"working directory is {ctx.workdir}")
        root_logger.info(f"source directory is {ctx.src}")
        root_logger.debug("debug mode enabled")  # does not really log when debug is disabled
        # the rest of logging done by actor and roles

    def _build_messaging(self, ctx: Context, logger: logging.Logger):
        # messaging component (combination of procedure invoker and provider)
        if hasattr(self, 'messaging_component'):
            component_class = as_class(self.messaging_component.cls)
            if not issubclass(component_class, MessagingComponent):
                raise TypeError(f'invalid messaging component class {component_class}')
            if issubclass(component_class, MessagingComponentDisabled):
                logger.warning('messaging component disabled, cannot interact with other actors/nodes')
            messaging_component = component_class(
                ctx.profile.name, ctx.profile.address, ctx.contacts, **self.messaging_component.options)
            self.artifacts.procedure_provider = self.artifacts.procedure_invoker = messaging_component

        # separated invoker and provider
        else:
            if not hasattr(self, 'procedure_invoker'):
                self.procedure_invoker = ComponentConfig(ProcedureInvokerDisabled)
            invoker_class = as_class(self.procedure_invoker.cls)
            if not issubclass(invoker_class, ProcedureInvoker):
                raise TypeError(f'invalid procedure invoker class {invoker_class}')
            if issubclass(invoker_class, ProcedureInvokerDisabled):
                logger.warning('procedure invoker disabled, cannot send message to other actors/nodes')
            self.artifacts.procedure_invoker = invoker_class(
                ctx.profile.name, ctx.profile.address, ctx.contacts, **self.procedure_invoker.options)

            if not hasattr(self, 'procedure_provider'):
                self.procedure_provider = ComponentConfig(ProcedureProviderDisabled)
            provider_class = as_class(self.procedure_provider.cls)
            if not issubclass(provider_class, ProcedureProvider):
                raise TypeError(f'invalid procedure provider class {provider_class}')
            if issubclass(provider_class, ProcedureProviderDisabled):
                logger.warning('procedure provider disabled, cannot receive message from other actors/nodes')
            self.artifacts.procedure_provider = provider_class(
                ctx.profile.name, ctx.profile.address, ctx.contacts, **self.procedure_provider.options)

        # collective implementor
        if not hasattr(self, 'collective_implementor'):
            from roleml.core.actor.group.impl.null import CollectiveImplementorDisabled
            self.collective_implementor = ComponentConfig(CollectiveImplementorDisabled)
            logger.warning('collective implementor disabled, cannot use call_group/call_actor_group APIs')
        collective_implementor_class = as_class(self.collective_implementor.cls)
        if not issubclass(collective_implementor_class, CollectiveImplementor):
            raise TypeError(f'invalid collective implementor class {collective_implementor_class}')
        ci = collective_implementor_class(**self.collective_implementor.options)    # noqa: overridable __init__
        self.artifacts.collective_implementor = ci

    def _build_roles(self, logger: logging.Logger):     # noqa: overridable method
        for name, builder in self.roles.items():
            builder.build()

    def _setup(self, actor: ActorType):
        for role_builder in self.roles.values():
            role_builder.install(actor, start=False)
