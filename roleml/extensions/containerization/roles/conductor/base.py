import threading
import time
from pathlib import Path
from typing import Optional, cast as c
import uuid
from typing_extensions import override

from roleml.core.context import ActorProfile, RoleInstanceID, parse_instances
from roleml.core.role.channels import Event, EventHandler, HandlerDecorator
from roleml.library.roles.conductor.base import Conductor as BaseConductor
from roleml.library.roles.conductor.types import RunSpec, RunSpecTemplate, validate_run_spec
from roleml.shared.yml import load_yaml, save_yaml


class RoleNameMap:
    def __init__(self):
        self._role_name_map: dict[tuple[str, str], list[str]] = {}
        self._unique_names: set[str] = set()
        self._lock = threading.RLock()

    def add_role(self, actor: str, role: str) -> str:
        # generate a unique name for the role
        # can not use the same name for different roles of the same actor
        with self._lock:
            if (actor, role) in self._role_name_map:
                raise ValueError(f"Role {role} of actor {actor} already exists")
            else:
                new_name = f"{role}_{uuid.uuid4().hex}"
                self._role_name_map[(actor, role)] = [new_name]
                self._unique_names.add(new_name)
                return new_name

    def get_unique_name(self, actor: str, role: str) -> str:
        with self._lock:
            if role in self._unique_names:
                return role
            roles = self._role_name_map[(actor, role)]
            if len(roles) == 1:
                return roles[0]
            else:
                raise ValueError(f"Role {role} of actor {actor} has multiple instances: {roles}, please specify")

    def change_role_owner(self, unique_name: str, new_actor: str):
        with self._lock:
            old_actor, usr_name = self.get_user_defined_name(unique_name)
            self._role_name_map.setdefault((new_actor, usr_name), []).append(unique_name)
            self._role_name_map[(old_actor, usr_name)].remove(unique_name)

    def get_user_defined_name(self, unique_name: str) -> tuple[str, str]:
        """根据唯一实例名获取用户定义的实例名，例如：role1_123456789 -> (node1, role1)"""
        with self._lock:
            for k, v in self._role_name_map.items():
                if unique_name in v:
                    return k
            raise ValueError(f"Unique name {unique_name} not found")


class Conductor(BaseConductor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 将用户配置的角色实例名映射到内部使用的实例名
        # 可以根据所在节点名和角色名来查询到它的唯一实例名，例如：(node1, role1) -> role1_123456789
        # 需要注意的是，角色迁移完成后，需要更新这个映射
        self.role_unique_name_map = RoleNameMap()

        self.cli.add_command("offload", self.offload, expand_arguments=True)

    @override
    def configure(self, config_file: str, path: Optional[str] = None):
        """Configure actors in preparation for a DML run. All actors must be started first.

        Basically this function does the following things, according to the specification given (or converted from
        template if necessary):

        1. sends connection information to all the actors (physical topology).
        2. sends role assignments to all the actors (including role class, options, fillings, etc.), and wait for the
           actors to finish initialization.
        3. sends relationship information to all the actors (active logical topology), and wait for the actors to finish
           setup.
        """
        raw_spec = load_yaml(config_file)
        if not isinstance(raw_spec, dict):
            raise ValueError("Config or config template is not a dict")

        if raw_spec.get("fixed") is True:
            spec = c(RunSpec, raw_spec)
            save = False
        else:
            spec = self._generate_run_configuration(c(RunSpecTemplate, raw_spec))
            save = True

        validate_run_spec(spec)  # will raise error if not valid

        connections = spec.get("connections", dict())
        role_assignments = spec.get("roles", dict())
        relationships = spec.get("relationships", dict())
        relationship_links = spec.get("relationship_links", dict())
        deployment_order = spec.get("deployment_order", list())
        non_deployed_actors: set[str] = set()
        bandwidth_config: dict[str, dict[str, float]] = spec.get("bandwidth", dict())

        for actor_spec in spec["profiles"]:
            self.ctx.contacts.add_contact(
                ActorProfile(**actor_spec)
            )  # keys: name, address
            non_deployed_actors.add(actor_spec["name"])

        # final validation of config
        for actor_name in deployment_order:
            if actor_name not in non_deployed_actors:
                raise ValueError(f"invalid deployment target: {actor_name}")

        if save:
            if path is None:
                save_path = Path(config_file).parent
            else:
                save_path = Path(path)
            save_path.mkdir(parents=True, exist_ok=True)
            save_filename = (
                save_path
                / f'run-{time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time()))}.yaml'
            )
            save_yaml(save_filename, spec)
            self.logger.info(
                f"successfully saved actual configurations for this run to {save_filename}"
            )

        def iterate_over_actors():
            yield self.ctx.profile.name
            for _actor_name in deployment_order:
                yield _actor_name
                non_deployed_actors.remove(_actor_name)
            for _actor_name in non_deployed_actors:
                yield _actor_name

        for actor_name, actor_assignments in role_assignments.items():
            for instance_name, role_spec in actor_assignments.items():
                self.role_unique_name_map.add_role(actor_name, instance_name)

        for actor_name in iterate_over_actors():
            native_role = RoleInstanceID(actor_name, "actor")
            # 1. physical connection information (contacts)
            if targets := connections.get(actor_name):
                send_profiles = {
                    target: self.ctx.contacts.get_actor_profile(target).address
                    for target in targets
                }
                self.call(native_role, "update-contacts", {"contacts": send_profiles})
                self.logger.info(f"{actor_name}: deployed contacts")

            # 2. relationships and links
            if actor_relationships := relationships.get(actor_name):
                for relationship_name, instance_strings in actor_relationships.items():
                    if instance_strings:
                        instances = parse_instances(instance_strings, relationship_name)
                        # convert to unique names
                        instances = [
                            RoleInstanceID(
                                instance.actor_name,
                                self.role_unique_name_map.get_unique_name(
                                    instance.actor_name, instance.instance_name
                                ),
                            )
                            for instance in instances
                        ]
                        self.call(
                            native_role,
                            "update-relationship",
                            {
                                "relationship_name": relationship_name,
                                "op": "add",
                                "instances": instances,
                            },
                        )
                self.logger.info(f"{actor_name}: deployed relationships")
            if actor_relationship_links := relationship_links.get(actor_name):
                for from_name, to_name in actor_relationship_links.items():
                    self.call(
                        native_role,
                        "add-relationship-link",
                        {
                            "from_relationship_name": from_name,
                            "to_relationship_name": to_name,
                        },
                    )
                self.logger.info(f"{actor_name}: deployed relationship links")

            # 3. roles
            if actor_assignments := role_assignments.get(actor_name):
                for instance_name, role_spec in actor_assignments.items():
                    # convert to unique name
                    instance_name = self.role_unique_name_map.get_unique_name(
                        actor_name, instance_name
                    )
                    self.call_task(
                        native_role,
                        "assign-role",
                        {"name": instance_name, "spec": role_spec},
                    ).result()
                self.logger.info(f"{actor_name}: deployed roles")

        self.bandwidth_config_updated_event.emit({"config": bandwidth_config})

        self.logger.info("deploy completed")

    bandwidth_config_updated_event = Event("bandwidth_config_updated")
    
    @EventHandler("/", "contact-updated", expand=True)
    def on_contacts_updated(self, _, name: str):
        profile = self.ctx.contacts.get_actor_profile(name)
        executor_id = RoleInstanceID(name, "offloading_executor")
        self.subscribe(
            executor_id,
            "offload-started",
            self.on_offload_started,
        )
        self.subscribe(
            executor_id,
            "offload-succeeded",
            self.on_offload_succeeded,
        )
        self.subscribe(
            executor_id,
            "offload-failed",
            self.on_offload_failed,
        )
        
        offloading_manager = self.base.convert_relationship_to_instance("offloading_manager")
        if offloading_manager.actor_name != self.ctx.profile.name:
            self.call(
                RoleInstanceID(offloading_manager.actor_name, "actor"),
                "update-contacts",
                {
                    "contacts": {name: profile.address},
                },
            )

    def offload(self, src_actor: str, role: str, dst_actor: str):
        """Offload a role from one actor to another.

        Usage:
            `offload <src_actor> <role> <dst_actor>`
        """
        if src_actor == dst_actor:
            raise ValueError("src and dst cannot be the same")
        try:
            role_unique_name = self.role_unique_name_map.get_unique_name(
                src_actor, role
            )
        except KeyError:
            raise ValueError(f"Role {src_actor}/{role} not found")

        self.call_task(
            "offloading_manager",
            "offload-roles",
            {"plan": {RoleInstanceID(src_actor, role_unique_name): dst_actor}},
        ).result()

    @HandlerDecorator(expand=True)
    def on_offload_started(
        self, _, source_actor_name: str, instance_name: str, destination_actor_name: str
    ):
        self.logger.info(
            f"Offloading role {source_actor_name}/{instance_name} to {destination_actor_name} started"
        )

    @HandlerDecorator(expand=True)
    def on_offload_succeeded(
        self,
        _,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
        destination_actor_address: str,
        # timer: dict[str, float],
    ):
        self.role_unique_name_map.change_role_owner(
            instance_name, destination_actor_name
        )
        self.logger.info(
            f"Offloading role {source_actor_name}/{instance_name} to {destination_actor_name} succeeded"
        )

    @HandlerDecorator(expand=True)
    def on_offload_failed(
        self,
        _,
        source_actor_name: str,
        instance_name: str,
        destination_actor_name: str,
        error: str,
    ):
        self.logger.error(
            f"Offloading role {source_actor_name}/{instance_name} to {destination_actor_name} failed: {error}"
        )
