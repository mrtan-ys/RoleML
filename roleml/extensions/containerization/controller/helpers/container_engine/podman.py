import os
from pathlib import Path
from typing import Any, Iterator, Optional, Union
from typing_extensions import override

from podman import PodmanClient
from podman.domain.containers import Container
import podman.errors

from roleml.extensions.containerization.controller.helpers.container_engine.interface import (
    ContainerEngine,
    Container as ContainerInterface,
    NoSuchContainerError,
)


class PodmanContainer(ContainerInterface):

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
        return self._container.stats(stream=False, decode=True)  # type: ignore

    @override
    def get_stats_stream(self) -> Iterator[dict[str, Any]]:
        return self._container.stats(stream=True, decode=True)  # type: ignore


class PodmanEngine(ContainerEngine):

    def __init__(self):
        pass

    @override
    def get_container(self, container_name: str) -> ContainerInterface:
        try:
            with PodmanClient() as client:
                container = client.containers.get(container_name)
                return PodmanContainer(container)
        except podman.errors.NotFoundError:
            raise NoSuchContainerError(container_name) from None

    @override
    def container_exists(self, container_name: str) -> bool:
        with PodmanClient() as client:
            return client.containers.exists(container_name)

    @override
    def image_exists(self, tag: str) -> bool:
        with PodmanClient() as client:
            return client.images.exists(tag)

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
            - `podman.errors.BuildError`
        """
        with PodmanClient() as client:
            image, logs = client.images.build(
                dockerfile=dockerfile_path,
                tag=tag,
                path=context_path,
                rm=True,
                **options,
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
            - `podman.errors.APIError`
        """
        with PodmanClient() as client:
            container = client.containers.create(
                image,
                cmd,
                name=container_name,
                extra_hosts={"host.docker.internal": "host-gateway"},
                **options,
            )
            return PodmanContainer(container)

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
            - `podman.errors.APIError`
        """
        with PodmanClient() as client:
            container = client.containers.run(
                image,
                cmd,
                name=container_name,
                extra_hosts={"host.docker.internal": "host-gateway"},
                detach=True,
                **options,
            )
            assert isinstance(container, Container)
            return PodmanContainer(container)

    @override
    def checkpoint_container(
        self, container_name: str, checkpoint_name: str, output_dir: str
    ) -> Path:
        _ = self.get_container(container_name)
        tar_output_path = os.path.join(output_dir, f"{checkpoint_name}.tar.gz")
        cmd = f"podman container checkpoint -e {tar_output_path} {container_name}"
        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError(
                f"Failed to checkpoint container {container_name} with command {cmd}, return code {ret}"
            )
        return Path(tar_output_path)

    @override
    def restore_container(
        self, container_name: str, checkpoint_path: str
    ) -> ContainerInterface:
        """
        raises:
            - `podman.errors.APIError`
        """
        if self.container_exists(container_name):
            container = self.get_container(container_name)
            container.stop()
            container.remove()
        ret = os.system(
            f"podman container restore -i {checkpoint_path} -n {container_name}"
        )
        if ret != 0:
            raise RuntimeError(
                f"Failed to restore checkpoint {checkpoint_path} when starting container, return code {ret}"
            )
        container = self.get_container(container_name)
        container.reload()
        return container
