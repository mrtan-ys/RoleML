from copy import deepcopy
import ipaddress
import logging
from pathlib import Path
import time
from typing_extensions import override

import docker
import docker.models
import docker.models.containers
import requests

from roleml.core.actor.manager import BaseManager
from roleml.core.builders.role import RoleConfig, RoleSpec
from roleml.core.context import ActorProfile
from roleml.core.role.base import Role
from roleml.core.status import Status

from roleml.extensions.containerization.builders.spec import ContainerizationConfig
from roleml.extensions.containerization.controller.helpers.container_engine.docker import (
    DockerEngine,
)
from roleml.extensions.containerization.controller.helpers.container_engine.interface import (
    NoSuchContainerError,
)
from roleml.extensions.containerization.controller.managers.mixin import (
    ContainerInvocationMixin,
)
from roleml.extensions.containerization.controller.role import ContainerizedRole
from roleml.extensions.containerization.runtime.managers.status import (
    STATUS_RESUME_CHANNEL,
    STATUS_PAUSE_CHANNEL,
)


CONTAINER_OFFLOAD_CHANNEL = "CONTAINER_OFFLOAD"
CONTAINER_RESTORE_CHANNEL = "CONTAINER_RESTORE"


class ContainerManager(BaseManager, ContainerInvocationMixin):

    IMAGE_TAG = "roleml"
    RUNTIME_MESSAGING_PORT_IN_CONTAINER = 4000
    RUNTIME_SETUP_PORT_IN_CONTAINER = 4001

    @override
    def initialize(self, containerization_config: ContainerizationConfig):
        super().initialize()

        self._containerization_config = containerization_config
        self._container_service = DockerEngine()
        self._instance_name_to_container_name: dict[str, str] = {}
        self._instance_name_to_container_ip: dict[str, str] = (
            {}
        )  # ip address in container network

        self.role_status_manager.add_callback(Status.STARTING, self._on_status_starting)
        self.role_status_manager.add_callback(
            Status.FINALIZING, self._on_status_finalizing
        )
        self.role_status_manager.add_callback(Status.PAUSED, self._on_status_pausing)
        self.role_status_manager.add_callback(
            Status.OFFLOADED, self._on_status_offloaded
        )
        self.role_status_manager.add_callback(Status.RESUMING, self._on_status_resuming)

        self.logger = logging.getLogger("roleml.managers.container")

        self._profiling = False
        self._profiling_tracer_entries: int = 1000000
        self._profiling_save_path: str = ""
        try:
            from viztracer import get_tracer

            if tracer := get_tracer():
                self._profiling = True
                self._profiling_tracer_entries = tracer.tracer_entries
                self._profiling_save_path = (
                    Path(tracer.output_file).parent.absolute().as_posix()
                )
        except ModuleNotFoundError:
            pass

    @property
    def containers(
        self,
    ):
        for (
            instance_name,
            container_name,
        ) in self._instance_name_to_container_name.items():
            yield instance_name, self._container_service.get_container(container_name)  # type: ignore

    @property
    def containerized_roles(self) -> list[str]:
        return list(self._instance_name_to_container_name.keys())

    @override
    def add_role(self, role: Role):
        assert isinstance(role, ContainerizedRole)
        self.logger.info(f"Creating container for role {role.name}")
        self._create_role_container(role.name, use_run=True)
        # self.logger.info(f"Starting container for role {role.name}")
        # self._start_role_container(role.name)
        self._update_container_address(role.name)
        time.sleep(1)  # wait for the container server to start
        role_config = role.config
        self._setup_role_runtime(role.name, role_config)
        self._add_container_to_contacts(role.name)  # add contact for the role instance.
        self.logger.info(f"Role {role.name} added")

    def _add_container_to_contacts(self, instance_name: str):
        # TODO this concated name is a trick for ProcedureInvoker to obtain the correct address,
        # TODO others should not use this name.
        # TODO this is a temporary solution, should be replaced by a more elegant way.
        prof = ActorProfile(
            f"{self.context.profile.name}_{instance_name}",
            f"{self._instance_name_to_container_ip[instance_name]}:{self.RUNTIME_MESSAGING_PORT_IN_CONTAINER}",
        )
        self.context.contacts.add_contact(prof)

    def get_container(self, instance_name: str) -> docker.models.containers.Container:
        container_name = self._instance_name_to_container_name[instance_name]
        return self._container_service.get_container(container_name)  # type: ignore

    def checkpoint_container(self, instance_name: str, save_dir: Path) -> Path:
        ckpt_tar_path = self._container_service.checkpoint_container(
            self._instance_name_to_container_name[instance_name],
            f"checkpoint_{self.context.profile.name}_{instance_name}",
            save_dir.absolute().as_posix(),
        )
        return Path(ckpt_tar_path)

    def restore_container(self, instance_name: str, ckpt: Path):
        self._create_role_container(instance_name, use_run=True)
        self._container_service.restore_container(
            self._instance_name_to_container_name[instance_name],
            ckpt.absolute().as_posix(),
        )
        self._update_container_address(instance_name)
        self._add_container_to_contacts(instance_name)

    def _on_status_starting(self, instance_name: str, old_status: Status):
        if not self._is_role_containerized(instance_name):
            return

        self.logger.info(f"Run role {instance_name}")
        self._run_role(instance_name)
        self.logger.info(f"Role {instance_name} started")

    def _on_status_resuming(self, instance_name: str, old_status: Status):
        if not self._is_role_containerized(instance_name):
            return
        self._invoke_container(instance_name, STATUS_RESUME_CHANNEL, None, None, None)

    def _on_status_finalizing(self, instance_name: str, old_status: Status):
        if not self._is_role_containerized(instance_name):
            return

        self.logger.info(f"Stop signal sent to {instance_name}")
        try:
            resp = requests.post(
                f"http://{self._instance_name_to_container_ip[instance_name]}:{self.RUNTIME_SETUP_PORT_IN_CONTAINER}/stop",
                json={"timeout": 20},  # TODO configurable timeout
            )
            if resp.status_code != 200:
                try:
                    data = resp.json()
                    self.logger.error(
                        f"Error when stopping {instance_name}: {data['error']}"
                    )
                except:
                    self.logger.error(
                        f"Error when stopping {instance_name}: {resp.text}"
                    )
                # force stop
                self.logger.info(f"Force stopping {instance_name}")
                container = self._container_service.get_container(
                    self._instance_name_to_container_name[instance_name]
                )
                container.stop()
        except requests.exceptions.ConnectionError:
            # container is already stopped
            pass
        # container.remove()
        # self.logger.info(f"Container {container_name} removed")

    def _on_status_pausing(self, instance_name: str, old_status: Status):
        if not self._is_role_containerized(instance_name):
            return
        self._invoke_container(instance_name, STATUS_PAUSE_CHANNEL, None, None, None)

    def _on_status_offloaded(self, instance_name: str, old_status: Status):
        if not self._is_role_containerized(instance_name):
            return
        self.get_container(instance_name).remove()
        self._instance_name_to_container_ip.pop(instance_name)
        self._instance_name_to_container_name.pop(instance_name)

    def _create_role_container(self, instance_name: str, use_run: bool = False):
        container_name = f"roleml_{self.context.profile.name}_{instance_name}"
        try:
            container = self._container_service.get_container(container_name)
            self.logger.info(f"Container {container_name} already exists. Removing...")
            container.stop()
            container.remove()
            self.logger.info(f"Container {container_name} removed")
        except NoSuchContainerError:
            pass

        self.logger.info(f"Building image {self.IMAGE_TAG}")
        self._build_image()

        vols = {
            src: {
                "bind": dst,
            }
            for src, dst in self._containerization_config.mounts
        }
        vols[self._containerization_config.project_root.absolute().as_posix()] = {
            "bind": "/app",
            "mode": "ro",
        }
        if self._profiling:
            profiling_dir = self._profiling_save_path
            vols[profiling_dir] = {
                "bind": "/profiling",
                "mode": "rw",
            }

        py_script = (
            "from roleml.extensions.containerization.runtime.runner import RemoteRunner",
            f"runner = RemoteRunner()",
            f"runner.run({self.RUNTIME_SETUP_PORT_IN_CONTAINER})",
        )
        py_script = "; ".join(py_script)
        cmd = (
            "python",
            "-u",
            "-c",
            f'"{py_script}"',
        )
        cmd = " ".join(cmd)

        self.logger.info(f"Creating container {container_name}")
        if use_run:
            f = self._container_service.run_container
        else:
            f = self._container_service.create_container
        container = f(
            self.IMAGE_TAG,
            container_name,
            cmd,
            ports={
                self.RUNTIME_MESSAGING_PORT_IN_CONTAINER: None,
                self.RUNTIME_SETUP_PORT_IN_CONTAINER: None,
            },  # random port
            volumes=vols,
        )
        self.logger.info(f"Container {container_name} created")
        self._instance_name_to_container_name[instance_name] = container_name

    def _start_role_container(self, instance_name: str):
        container_name = self._instance_name_to_container_name[instance_name]
        container = self._container_service.get_container(container_name)
        assert container is not None
        self.logger.info(f"Starting container {container_name}")
        container.start()
        self.logger.info(f"Container {container_name} started")

    def _update_container_address(self, instance_name: str):
        container_name = self._instance_name_to_container_name[instance_name]
        container = self._container_service.get_container(container_name)
        assert container is not None
        container.reload()
        self._instance_name_to_container_ip[instance_name] = container.attrs[
            "NetworkSettings"
        ]["IPAddress"]

    def _convert_loopback_to_host(self, address: str):
        ip, port_str = address.split(":")
        if ip == "localhost" or ipaddress.ip_address(ip).is_loopback:
            return f"host.docker.internal:{port_str}"
        return address

    def _setup_role_runtime(self, instance_name: str, instance_config: RoleConfig):
        self.logger.info(f"Setting up runtime for role {instance_name}")

        role_cls = instance_config.cls
        assert isinstance(role_cls, str)
        role_spec: RoleSpec = {
            "class": role_cls,
            "impl": instance_config.impl,
            "options": instance_config.options,
        }

        runtime_actor_spec = deepcopy(self._containerization_config.actor_spec)
        runtime_actor_spec["name"] = (
            self.context.profile.name
        )  # currently keep the same
        runtime_actor_spec["address"] = (
            f"localhost:{self.RUNTIME_MESSAGING_PORT_IN_CONTAINER}"
        )
        runtime_actor_spec["contacts"] = {
            **{
                prof.name: self._convert_loopback_to_host(prof.address)
                for prof in self.context.contacts.all_actors()
            },
            self.context.profile.name: f"host.docker.internal:{self.context.profile.address.split(':')[1]}",
        }
        with self.context.relationships:
            runtime_actor_spec["relationship_links"] = {
                **self.context.relationships._relationship_links,
            }
            runtime_actor_spec["relationships"] = {
                **{
                    rel: [f"{inst.actor_name}/{inst.instance_name}" for inst in insts]
                    for rel, insts in self.context.relationships.all_relationships().items()
                    # 忽略别名
                    if rel not in self.context.relationships._relationship_links
                },
                # **{
                #     inst: [f"__node_controller/{inst}"]
                #     # inst: [f"{self.context.profile.name}/{inst}"]
                #     for inst in self._instance_name_to_container_name.keys()
                #     if inst != instance_name
                # }
            }
        runtime_actor_spec["roles"] = {instance_name: role_spec}
        runtime_actor_spec["handshakes"] = []
        runtime_actor_spec["handwaves"] = []
        runtime_actor_spec["containerize"] = True
        if runtime_actor_spec.get("element_preset", {}).get(role_cls):
            # only keep the element preset for the role
            runtime_actor_spec["element_preset"] = {
                role_cls: runtime_actor_spec["element_preset"][role_cls],  # type: ignore # already checked
            }
        runtime_actor_spec["workdir"] = "/app"
        runtime_actor_spec["src"] = "/app"
        runtime_actor_spec["log_file_path"] = (
            None  # disable logging to file, logs will be sent to the LogManager
        )

        resp = requests.post(
            f"http://{self._instance_name_to_container_ip[instance_name]}:{self.RUNTIME_SETUP_PORT_IN_CONTAINER}/setup",
            json={"instance_name": instance_name, "config": runtime_actor_spec},
        )
        if resp.status_code != 200:
            try:
                data = resp.json()
                self.logger.error(
                    f"Error when setting up runtime for {instance_name}: {data['error']}"
                )
            except:
                self.logger.error(
                    f"Error when setting up runtime for {instance_name}: {resp.text}"
                )
        resp.raise_for_status()

    def _run_role(self, instance_name: str):
        if not self._profiling:
            resp = requests.post(
                f"http://{self._instance_name_to_container_ip[instance_name]}:{self.RUNTIME_SETUP_PORT_IN_CONTAINER}/run"
            )
        else:
            resp = requests.post(
                f"http://{self._instance_name_to_container_ip[instance_name]}:{self.RUNTIME_SETUP_PORT_IN_CONTAINER}/run_with_profiling",
                json={
                    "save_path": "/profiling",
                    "tracer_entries": self._profiling_tracer_entries,
                },
            )
        if resp.status_code != 200:
            try:
                data = resp.json()
                self.logger.error(
                    f"Error when setting up runtime for {instance_name}: {data['error']}"
                )
            except:
                self.logger.error(
                    f"Error when setting up runtime for {instance_name}: {resp.text}"
                )
        resp.raise_for_status()

    def _build_image(self, force: bool = False):
        if self._container_service.image_exists(self.IMAGE_TAG) and not force:
            self.logger.info(f"Image {self.IMAGE_TAG} already exists. Skipping build")
            return

        dockerfile_path = self._generate_dockerfile()
        self._container_service.build_image(
            self.IMAGE_TAG,
            dockerfile_path.as_posix(),
            self._containerization_config.project_root.as_posix(),
        )
        self.logger.info(f"Image {self.IMAGE_TAG} built")

    def _generate_dockerfile(self) -> Path:
        req_exists = (
            self._containerization_config.project_root / "requirements.txt"
        ).exists()
        additional_python_paths = [
            "/roleml",  # for roleml package source, used when developing roleml
        ]
        python_paths = [
            *additional_python_paths,
            "$PYTHONPATH",
        ]
        content = f"""
FROM {self._containerization_config.base_image}
{'COPY requirements.txt /app/requirements.txt' if req_exists else ''}
WORKDIR /app
{'RUN pip install --no-cache-dir -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com' if req_exists else ''}
ENV PYTHONUNBUFFERED=1 PYTHONPATH={':'.join(python_paths)}
EXPOSE {self.RUNTIME_MESSAGING_PORT_IN_CONTAINER} {self.RUNTIME_SETUP_PORT_IN_CONTAINER}
"""
        save_path = self._containerization_config.temp_dir / "dockerfile"
        save_path.write_text(content, encoding="utf-8")
        return save_path
