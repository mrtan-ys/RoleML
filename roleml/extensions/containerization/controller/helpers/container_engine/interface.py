from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator, Optional, Union


class Container(ABC):

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def remove(self):
        pass

    @abstractmethod
    def reload(self):
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def id(self) -> str:
        pass

    @property
    @abstractmethod
    def status(self) -> str:
        pass

    @property
    @abstractmethod
    def attrs(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        pass
    
    @abstractmethod
    def get_stats_stream(self) -> Iterator[dict[str, Any]]:
        pass


class ContainerEngine(ABC):

    @abstractmethod
    def get_container(self, container_name: str) -> Container:
        pass

    @abstractmethod
    def container_exists(self, container_name: str) -> bool:
        pass

    @abstractmethod
    def image_exists(self, tag: str) -> bool:
        pass

    @abstractmethod
    def build_image(
        self,
        tag: str,
        dockerfile_path: str,
        context_path: Optional[str] = None,
        **options,
    ):
        pass

    @abstractmethod
    def create_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> Container:
        pass

    @abstractmethod
    def run_container(
        self,
        image: str,
        container_name: str,
        cmd: Optional[Union[str, list[str]]] = None,
        **options,
    ) -> Container:
        pass

    @abstractmethod
    def checkpoint_container(
        self, container_name: str, checkpoint_name: str, output_dir: str
    ) -> Path:
        pass

    @abstractmethod
    def restore_container(
        self, container_name: str, checkpoint_path: str
    ) -> Container:
        pass


class NoSuchContainerError(Exception):

    def __init__(self, container_name: str):
        super().__init__(f"Container {container_name} does not exist.")
