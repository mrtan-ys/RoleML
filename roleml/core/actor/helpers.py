from typing import NamedTuple

from roleml.core.role.types import Args


class PayloadsPickledMessage(NamedTuple):
    args: Args
    payloads: bytes
