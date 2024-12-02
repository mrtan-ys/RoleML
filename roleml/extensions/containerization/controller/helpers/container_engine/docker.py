import os
from pathlib import Path
import time
from typing import Any, Iterator, Optional, Union
import warnings
from typing_extensions import override

import docker.models
import docker.models.configs
from docker.models.containers import Container
import docker.errors

from roleml.extensions.containerization.controller.helpers.container_engine.interface import (
    ContainerEngine,
    Container as ContainerInterface,
    NoSuchContainerError
)


class DockerContainer(ContainerInterface):

    def __init__(self, container: Container):
        self._container = container

    @override
    def start(self):
        self._container.start()

    @override
    def stop(self):
        self._container.stop()

    @override
    def remove(self):
        self._container.remove()

    @override
    def reload(self):
        self._container.reload()

    @property
    @override
    def name(self) -> str:
        assert self._container.name is not None
        return self._container.name

    @property
    @override
    def id(self) -> str:
        assert self._container.id is not None
        return self._container.id

    @property
    @override
    def status(self) -> str:
        return self._container.status

    @property
    @override
    def attrs(self) -> dict[str, Any]:
        return self._container.attrs

    @override
    def get_stats(self) -> dict[str, Any]:
        return self._container.stats(stream=False, decode=True)
    
    @override
    def get_stats_stream(self) -> Iterator[dict[str, Any]]:
        return self._container.stats(stream=True, decode=True)

class DockerEngine(ContainerEngine):

    def __init__(self):
        # TODO https://github.com/checkpoint-restore/criu/issues/2453
        warnings.warn(
            (
                "You are using DockerEngine, which has issues with checkpoint/restore "
                "and may not work properly in automatical offloading. "
                "See https://github.com/checkpoint-restore/criu/issues/2453 for more details. "
                # "Please consider using PodmanEngine instead."
            ),
            UserWarning,
        )
        self._docker_client = docker.from_env()

    @override
    def get_container(self, container_name: str) -> ContainerInterface:
        """
        raises:
            - `NoSuchContainerError`
        """
        try:
            container = self._docker_client.containers.get(container_name)
            container = DockerContainer(container)
            return container
        except docker.errors.NotFound:
            raise NoSuchContainerError(container_name) from None

    @override
    def container_exists(self, container_name: str) -> bool:
        try:
            self._docker_client.containers.get(container_name)
            return True
        except docker.errors.NotFound:
            return False

    @override
    def image_exists(self, tag: str) -> bool:
        try:
            self._docker_client.images.get(tag)
            return True
        except docker.errors.ImageNotFound:
            return False

    @override
    def build_image(
        self,
        tag: str,
        dockerfile_path: str,
        context_path: Optional[str] = None,
        **options,
    ):
        """
        raises:
            - `docker.errors.BuildError`
        """
        self._docker_client.images.build(
            dockerfile=dockerfile_path, tag=tag, path=context_path, rm=True, **options
        )

    @override
    def create_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> ContainerInterface:
        """
        raises:
            - `docker.errors.APIError`
        """
        container = self._docker_client.containers.create(
            image,
            cmd,
            name=container_name,
            extra_hosts={"host.docker.internal": "host-gateway"},
            **options,
        )
        container = DockerContainer(container)
        return container

    @override
    def run_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> ContainerInterface:
        """
        raises:
            - `docker.errors.APIError`
        """
        container = self._docker_client.containers.run(
            image,
            cmd,
            name=container_name,
            extra_hosts={"host.docker.internal": "host-gateway"},
            detach=True,
            **options,
        )
        container = DockerContainer(container)
        return container

    @override
    def checkpoint_container(
        self, container_name: str, checkpoint_name: str, output_dir: str
    ) -> Path:
        container = self.get_container(container_name)
        if container is None:
            raise RuntimeError(f"Container {container_name} does not exist")

        container_id = container.id
        cmd = f"docker checkpoint create {container_name} {checkpoint_name} --checkpoint-dir {output_dir}"
        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError(
                f"Failed to checkpoint container {container_name} with command {cmd}, return code {ret}"
            )

        # output_dir = f'/var/lib/docker/containers/{container_id}/checkpoints/'
        checkpoint_path = os.path.join(output_dir, checkpoint_name)

        # tar
        tar_output_path = os.path.join(output_dir, f"{checkpoint_name}.tar.gz")
        ret = os.system(f"tar -czvf {tar_output_path} -C {checkpoint_path} .")
        if ret != 0:
            raise RuntimeError(
                f"Failed to tar checkpoint {checkpoint_path}, return code {ret}"
            )
        os.system(f"rm -rf {checkpoint_path}")
        return Path(tar_output_path)

    @override
    def restore_container(
        self, container_name: str, checkpoint_path: str
    ) -> ContainerInterface:
        """
        raises:
            - `docker.errors.APIError`
            - `RuntimeError`
        """
        container = self.get_container(container_name)
        container.stop()

        untar_dir = f'{container_name}_{time.strftime("%Y%m%d%H%M%S")}'
        untar_dir_path = os.path.join(os.path.dirname(checkpoint_path), untar_dir)

        os.makedirs(untar_dir_path, exist_ok=True)
        # logger.info(f"Untar checkpoint {checkpoint_path} to {untar_dir_path}")
        # untar
        ret = os.system(f"tar -xzvf {checkpoint_path} -C {untar_dir_path}")
        if ret != 0:
            raise RuntimeError(
                f"Failed to untar checkpoint {checkpoint_path}, return code {ret}"
            )

        # restore
        container_id = container.id
        ret = os.system(
            f"mv {untar_dir_path} /var/lib/docker/containers/{container_id}/checkpoints/{untar_dir}"
        )
        if ret != 0:
            raise RuntimeError(
                f"Failed to restore checkpoint {checkpoint_path} when copying to docker checkpoint path, return code {ret}"
            )

        ret = os.system(f"docker start --checkpoint {untar_dir} {container_name}")
        os.system(f"rm -rf /var/lib/docker/containers/{container_id}/checkpoints/{untar_dir}")
        if ret != 0:
            raise RuntimeError(
                f"Failed to restore checkpoint {checkpoint_path} when starting container, return code {ret}"
            )

        container = self.get_container(container_name)
        if container is None:
            raise RuntimeError(f"Container {container_name} does not exist")
        container.reload()
        return container
