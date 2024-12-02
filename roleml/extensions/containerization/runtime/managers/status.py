import logging
from threading import Event
from typing_extensions import override

from fasteners import ReaderWriterLock

from roleml.core.actor.manager.bases import BaseManager
from roleml.core.actor.status import RoleStatusManager
from roleml.core.context import Context
from roleml.core.messaging.base import ProcedureInvoker, ProcedureProvider
from roleml.core.messaging.types import Args, Payloads, Tags
from roleml.core.role.base import Role
from roleml.extensions.containerization.runtime.managers.wrapper import ProcedureInvokerWrapper
from roleml.shared.interfaces import Runnable
from roleml.shared.multithreading.management import ThreadManager


STATUS_PAUSE_CHANNEL = "STATUS_PAUSE"
STATUS_RESUME_CHANNEL = "STATUS_RESUME"


class _WaitForResume(Runnable):
    
        def __init__(self, paused_event: Event, m: "StatusManager"):
            self._paused_event = paused_event
            self._m = m
    
        def run(self):
            self._m._wait_for_resume(self._paused_event)
            
        def stop(self):
            self._m._resumed_event.set()


class StatusManager(BaseManager):

    def __init__(
        self,
        context: Context,
        thread_manager: ThreadManager,
        role_status_manager: RoleStatusManager,
        procedure_invoker: ProcedureInvoker,
        procedure_provider: ProcedureProvider,
        **kwargs,
    ):
        super().__init__(
            context,
            thread_manager,
            role_status_manager,
            procedure_invoker,
            procedure_provider,
            **kwargs,
        )

    @override
    def initialize(self, communication_lock: ReaderWriterLock):
        super().initialize()
        self._pausing = False
        self._resumed_event = Event()
        self._communication_lock = communication_lock

        self.procedure_provider.add_procedure(
            STATUS_PAUSE_CHANNEL, self._on_pause
        )
        self.procedure_provider.add_procedure(
            STATUS_RESUME_CHANNEL, self._on_resume
        )
        
        self.logger = logging.getLogger('roleml.managers.status')

    def _on_pause(self, sender: str, tags: Tags, args: Args, _: Payloads):
        if self._pausing:
            raise AssertionError("Already pausing")
        self._pausing = True
        paused_event = Event()
        self.logger.debug("Pausing")
        # self.thread_manager.add_threaded_task(
        #     self._wait_for_resume, (paused_event,)
        # )
        self.thread_manager.add_threaded_component(
            _WaitForResume(paused_event, self)
        )
        
        paused_event.wait()

    def _wait_for_resume(self, paused_event: Event):
        assert isinstance(self.procedure_invoker, ProcedureInvokerWrapper)
        self._communication_lock.acquire_write_lock()
        self.procedure_invoker.block_invocation()
        # all communication is done here
        paused_event.set()  # notify the main thread that communication is done
        self.logger.debug("Paused")
        
        self._resumed_event.wait()
        self._pausing = False
        self._resumed_event.clear()
        self.procedure_invoker.unblock_invocation()
        self._communication_lock.release_write_lock()
        self.logger.debug("Resumed")

    def _on_resume(self, sender: str, tags: Tags, args: Args, _: Payloads):
        self.logger.debug("Resuming")
        self._resumed_event.set()

    def add_role(self, role: Role):
        pass  # don't care about roles
