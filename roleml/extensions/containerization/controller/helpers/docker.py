import os
from pathlib import Path
import time
from typing import Optional, Union

import docker.models
import docker.models.configs
from docker.models.containers import Container
from docker.models.images import Image
import docker.errors


class DockerService:
    def __init__(self):
        self._docker_client = docker.from_env()

    def get_container(self, container_name: str) -> Optional[Container]:
        try:
            container = self._docker_client.containers.get(container_name)
            assert isinstance(container, Container)
            return container
        except docker.errors.NotFound:
            return None

    def get_image(self, tag: str) -> Optional[Image]:
        try:
            image = self._docker_client.images.get(tag)
            assert isinstance(image, Image)
            return image
        except docker.errors.ImageNotFound:
            return None

    def image_exists(self, tag: str) -> bool:
        return self.get_image(tag) is not None

    def build_image(
        self,
        tag: str,
        dockerfile_path: str,
        context_path: Optional[str] = None,
        **options,
    ) -> Image:
        """
        raises:
            - `docker.errors.BuildError`
        """

        ret = self._docker_client.images.build(
            dockerfile=dockerfile_path, tag=tag, path=context_path, rm=True, **options
        )
        assert isinstance(ret, tuple) and isinstance(ret[0], Image)
        image = ret[0]
        return image

    def create_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> Container:
        """
        raises:
            - `docker.errors.APIError`
        """
        container = self._docker_client.containers.create(
            image, cmd, 
            name=container_name, 
            extra_hosts={"host.docker.internal": "host-gateway"},
            **options
        )
        assert isinstance(container, Container)
        return container

    def run_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> Container:
        """
        raises:
            - `docker.errors.APIError`
        """
        container = self._docker_client.containers.run(
            image, cmd, 
            name=container_name, 
            extra_hosts={"host.docker.internal": "host-gateway"},
            detach=True,
            **options
        )
        return container

    def checkpoint_container(
        self, container_name: str, checkpoint_name: str, output_dir: str
    ) -> str:
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
        return tar_output_path

    def restore_container(self, container_name: str, checkpoint_path: str) -> Container:
        """
        raises:
            - `docker.errors.APIError`
        """
        container = self.get_container(container_name)
        if container is None:
            raise RuntimeError(f"Container {container_name} does not exist")

        assert isinstance(container, Container)
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
            f"cp -r {untar_dir_path} /var/lib/docker/containers/{container_id}/checkpoints/{untar_dir}"
        )
        if ret != 0:
            raise RuntimeError(
                f"Failed to restore checkpoint {checkpoint_path} when copying to docker checkpoint path, return code {ret}"
            )

        ret = os.system(f"docker start --checkpoint {untar_dir} {container_name}")
        if ret != 0:
            raise RuntimeError(
                f"Failed to restore checkpoint {checkpoint_path} when starting container, return code {ret}"
            )

        container = self.get_container(container_name)
        if container is None:
            raise RuntimeError(f"Container {container_name} does not exist")
        container.reload()
        return container
