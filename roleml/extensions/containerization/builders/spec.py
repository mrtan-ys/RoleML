from pathlib import Path
from typing import Optional


from roleml.core.builders.actor import (
    ActorBootstrapSpec as BaseActorBootstrapSpec,
)


class ActorBootstrapSpec(BaseActorBootstrapSpec):
    containerize: Optional[bool]  # default: False
    temp_dir: Optional[str]  # default: None
    base_image: Optional[str]  # default: python:3.11.10-bullseye
    mounts: Optional[list[str]]


class ContainerizationConfig:
    def __init__(
        self,
        *,
        project_root: Path,
        temp_dir: Path,
        base_image: str,
        mounts: list[tuple[str, str]],
        actor_spec: ActorBootstrapSpec,
    ):
        self.project_root = project_root
        self.temp_dir = temp_dir
        self.base_image = base_image
        self.mounts = mounts
        self.actor_spec = actor_spec
