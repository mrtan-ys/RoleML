from enum import auto, Enum
from typing import Any, Callable, Mapping

__all__ = ['Args', 'Payloads', 'Tags', 'MyArgs', 'MyPayloads', 'MessageHandler', 'MessagePart']


Args = Mapping[str, Any]
Payloads = Mapping[str, Any]
Tags = Mapping[str, str]
MessageHandler = Callable[[str, Tags, Args, Payloads], Any]

MyArgs = dict[str, Any]
MyPayloads = dict[str, Any]


class MessagePart(Enum):
    ARGS = auto()
    PAYLOADS = auto()
