from typing import Any

from fasteners import ReaderWriterLock
from roleml.core.context import Context


class ContextProxy:
    """A proxy class for context object that allows to update the context object."""

    def __init__(self, context: Context):
        self._context = context
        self._context_rwlock = ReaderWriterLock()

    def __getattr__(self, name: str) -> Any:
        with self._context_rwlock.read_lock():
            return getattr(self._context, name)

    def update_context_object(self, context: Context):
        with self._context_rwlock.write_lock():
            self._context = context
