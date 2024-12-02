from typing import Any
from typing_extensions import override

from fasteners import ReaderWriterLock

from roleml.core.context import ActorProfile
from roleml.core.messaging.base import ProcedureInvoker
from roleml.core.messaging.types import Args, Payloads, Tags


class ProcedureInvokerWrapper(ProcedureInvoker):

    def __init__(self, invoker: ProcedureInvoker):
        self._invoker = invoker
        self._lock = ReaderWriterLock()

    @override
    def invoke_procedure(
        self,
        target: str | ActorProfile,
        name: str,
        tags: Tags | None = None,
        args: Args | None = None,
        payloads: Payloads | None = None,
    ) -> Any:
        with self._lock.read_lock():
            target = target if isinstance(target, str) else target.name
            return self._invoker.invoke_procedure(target, name, tags, args, payloads)

    def block_invocation(self):
        self._lock.acquire_write_lock()

    def unblock_invocation(self):
        self._lock.release_write_lock()

    def __getattr__(self, name):
        return getattr(self._invoker, name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            return super().__setattr__(name, value)
        return setattr(self._invoker, name, value)
