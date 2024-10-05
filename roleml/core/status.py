import logging
import threading as th
from contextlib import contextmanager
from enum import auto, Flag
from typing import Any, Callable, Optional, Union

from fasteners import ReaderWriterLock

from roleml.core.context import ActorProfile

__all__ = ['Status', 'StatusError', 'StatusTransferCallbackError', 'set_logger', 'ExecutionTicket', 'StatusControl']


class Status(Flag):

    DECLARING = auto()
    """ The initial status. """

    DECLARED = auto()
    """ After declaration (for a role, it means channels and elements are declared in the actor). """

    STARTING = auto()
    """ The object will be ready to use after some final initializations. The status goes to READY when such final
    initializations have finished. """

    READY = auto()
    """ The object is fully initialized and is ready to use. """

    PAUSING = auto()
    """ The object is pausing (e.g. in preparation for checkpointing). New calls will be rejected and incoming events 
    will be dropped. However, running handlers will continue their executions. The status goes to PAUSED after all 
    executing handlers have finished. """

    PAUSED = auto()
    """ The object has paused and no handler is being executed. New calls will be rejected and incoming events will be 
    dropped. A role at this stage is usually ready for checkpointing or migration. A PAUSED object can be brought back 
    to READY, while a TERMINATED object cannot. """

    TERMINATING = auto()
    """ The object is about to be terminated and waiting for running handlers to finish. New calls will be rejected and 
    incoming events will be dropped. The status goes to FINALIZING after all executing handlers have finished. """

    FINALIZING = auto()
    """ The object is doing some final work before termination. For example, the destructors of workload elements may be 
    called at this stage. If no further action is required, the status goes to TERMINATED. """

    TERMINATED = auto()
    """ The object has been terminated and is therefore out of service. """

    RESUMING = auto()
    """ The object is resuming from a paused state. """
    
    OFFLOADED = auto()
    """ The object has been offloaded to another node and is no longer in service here. """

    DECLARED_COMPATIBLE = DECLARED | STARTING | READY | PAUSING | PAUSED


class StatusError(ValueError):
    pass


class StatusTransferCallbackError(RuntimeError):
    pass


class RoleOffloadedError(StatusError):
    
    def __init__(self, instance_name: str, offloaded_to: ActorProfile):
        super().__init__(f'Role {instance_name} has been offloaded to {offloaded_to}')
        self.instance_name = instance_name
        self.offloaded_to = offloaded_to


LOGGER = logging.getLogger()


def set_logger(logger: Union[str, logging.Logger]):
    global LOGGER
    LOGGER = logging.getLogger(logger) if isinstance(logger, str) else logger


class ExecutionTicket:

    def __init__(self, ctrl, worker_id: int):
        self.ctrl = ctrl
        self.worker_id = worker_id
        self._should_stop = False
        self._stopped = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def ask_for_stopping(self):
        # should only be called by another thread
        self._should_stop = True

    @property
    def should_stop(self) -> bool:
        return self._should_stop

    def stop(self):
        self.ctrl.release_execution(self)
        self._stopped = True

    @property
    def is_stopped(self):
        return self._stopped


class StatusControl:

    def __init__(self, name: str = 'object', *, status_transfer_lock: Optional[th.RLock] = None):
        self._name = name
        self._status = Status.DECLARING
        self._status_access_lock = ReaderWriterLock()
        self._status_transfer_lock = status_transfer_lock or th.RLock()
        self._threads: dict[int, ExecutionTicket] = {}
        self._threads_lock = th.RLock()

        self._callbacks: dict[Status, list[Callable[[Status], Any]]] = {}   # arg is previous status
        self._listeners: set[Callable[[str, Status, Status], Any]] = set()

        self._check_execute = th.Event()
        self._stage = th.Event()    # can only be reset when transferring status
        self._stage.set()

        self._offloaded_to: ActorProfile | None = None

    def _transfer_status(self, status: Status, callback_anyway: bool,
                         *, required_old_status: Optional[Status] = None, ignore_callback_error: bool = False, 
                         slient: Optional[bool] = False):
        with self._status_transfer_lock:
            with self._status_access_lock.write_lock():
                if required_old_status:
                    self._require_status(required_old_status)
                old_status = self._status
                self._status = status
            if not slient and (callback_anyway or old_status != status):
                for cb in self._callbacks.get(status, []):
                    try:
                        cb(old_status)
                    except Exception as e:
                        LOGGER.exception(f'error in executing callback of status transfer {old_status} -> {status}')
                        if not ignore_callback_error:
                            raise StatusTransferCallbackError(f'callback {cb.__name__} at {status!s}') from e
                for cbl in self._listeners:
                    try:
                        cbl(self._name, status, old_status)
                    except Exception as e:
                        LOGGER.exception(f'error in executing listener at status transfer {old_status} -> {status}')
                        if not ignore_callback_error:
                            raise StatusTransferCallbackError(f'listener {cbl.__name__} at {status!s}') from e

    def _require_status(self, status: Status):
        with self._status_access_lock.read_lock():
            if not self._is_status(status):
                raise StatusError(f'operation requiring {status} is not allowed when {self._name} is at {self._status}')

    def _is_status(self, status: Status):
        with self._status_access_lock.read_lock():
            return self._status in status

    @property
    def status(self):
        return Status(self._status.value)

    @status.setter
    def status(self, new_status: Status):
        if new_status == Status.DECLARED:
            self.declared()
        elif new_status == Status.READY:
            self.ready()
        elif new_status == Status.PAUSED:
            self.pause()
        elif new_status == Status.TERMINATED:
            self.terminate()
        else:
            raise StatusError(f'Cannot manually set status value to {new_status}')

    @contextmanager
    def lock_status_for_execute(self, status: Status):
        with self._status_access_lock.read_lock():
            self._require_status(status)
            yield status

    def add_callback(self, status: Status, func: Callable[[Status], Any]):
        callbacks = self._callbacks.setdefault(status, [])
        callbacks.append(func)

    def add_listener(self, func: Callable[[str, Status, Status], Any]):
        self._listeners.add(func)

    def declared(self, ignore_callback_error: bool = False):
        self._transfer_status(
            Status.DECLARED, False,
            required_old_status=Status.DECLARING | Status.DECLARED | Status.TERMINATED,
            ignore_callback_error=ignore_callback_error)

    @property
    def is_declared(self):
        return self._is_status(Status.DECLARED_COMPATIBLE)

    @property
    def is_declared_only(self):
        return self._is_status(Status.DECLARED)

    def ready(self, ignore_callback_error: bool = False):
        """ WARNING: if `ignore_callback_error` is False (default) and a `StatusTransferCallbackError` has been raised,
        the method caller should immediately call `terminate()` after performing necessary actions (such as logging) or
        the behavior will be undefined. """
        with self._status_transfer_lock:
            self._require_status(Status.DECLARED_COMPATIBLE)
            if self._is_status(Status.DECLARED):
                self._transfer_status(Status.STARTING, False, ignore_callback_error=ignore_callback_error)
            elif self._is_status(Status.PAUSED):
                self._transfer_status(Status.RESUMING, False, ignore_callback_error=ignore_callback_error)
            self._transfer_status(Status.READY, False, ignore_callback_error=ignore_callback_error)
            self._check_execute.set()

    @property
    def is_ready(self):
        return self._is_status(Status.READY)

    def acquire_execution(self, worker_id: Optional[int] = None, *, timeout: Optional[float] = None) -> ExecutionTicket:
        if worker_id is None:
            worker_id = th.get_ident()
        self._status_access_lock.acquire_read_lock()
        try:
            if self._is_status(Status.READY):
                return self._set_execution_ticket(worker_id)
            elif self._is_status(Status.PAUSING | Status.PAUSED):
                self._status_access_lock.release_read_lock()
                self._check_execute.wait(timeout)
                self._status_access_lock.acquire_read_lock()
                if not self._is_status(Status.READY):
                    # we need to notify the calling thread if the object has been terminated
                    raise StatusError(f'Cannot acquire execution after timeout; {self._name} is now at {self.status}')
                return self._set_execution_ticket(worker_id)
            elif self._is_status(Status.OFFLOADED):
                assert self._offloaded_to is not None
                raise RoleOffloadedError(self._name, self._offloaded_to)
            else:
                raise StatusError(f'Cannot acquire execution for {self._name} in status {self.status}')
        finally:
            self._status_access_lock.release_read_lock()

    def _set_execution_ticket(self, worker_id: int) -> ExecutionTicket:
        ticket = ExecutionTicket(self, worker_id)
        with self._threads_lock:
            self._threads[worker_id] = ticket
            self._stage.clear()
        return ticket

    def release_execution(self, ticket: ExecutionTicket):
        worker_id = ticket.worker_id
        with self._threads_lock:
            self._threads.pop(worker_id, None)
            if len(self._threads) == 0:
                self._stage.set()

    def pause(self, force: bool = False, *, ignore_callback_error_on_revert: bool = False):
        paused = self._pause(None, force, ignore_callback_error_on_revert)
        if not paused:
            raise StatusError(f'{self._name} not paused successfully, current status is {self.status}')

    def try_pause(self, timeout: float, *, force: bool = False, ignore_callback_error_on_revert: bool = False) -> bool:
        return self._pause(timeout, force, ignore_callback_error_on_revert)

    def _pause(self, timeout: Optional[float], force: bool, ignore_callback_error_on_revert: bool = False) -> bool:
        with self._status_transfer_lock:
            if self._is_status(Status.PAUSED):
                return True
            elif self._is_status(Status.READY):
                try:
                    self._transfer_status(Status.PAUSING, False, ignore_callback_error=False)
                except:
                    self._transfer_status(Status.READY, False, ignore_callback_error=ignore_callback_error_on_revert)
                    raise
                self._check_execute.clear()
                # now locked at PAUSING, new tickets cannot be registered
                with self._threads_lock:
                    if force:
                        for ticket in self._threads.values():
                            ticket.ask_for_stopping()
                if not self._stage.wait(timeout):
                    # only when timeout is not None, which means we will need to revert to the READY status
                    self._transfer_status(Status.READY, False, ignore_callback_error=ignore_callback_error_on_revert)
                    self._check_execute.set()
                    return False
                else:
                    self._transfer_status(Status.PAUSED, False, ignore_callback_error=True)
                    return True
            else:
                raise StatusError(f'Cannot pause {self._name} in status {self.status}')

    @property
    def is_paused(self):
        return self._is_status(Status.PAUSED)

    def terminate(self, force: bool = False, *, ignore_callback_error_on_revert: bool = False):
        while not self._terminate(None, force, ignore_callback_error_on_revert):
            pass    # if not terminated successfully, retry

    def try_terminate(
            self, timeout: float, *, force: bool = False, ignore_callback_error_on_revert: bool = False) -> bool:
        return self._terminate(timeout, force, ignore_callback_error_on_revert)

    def _terminate(self, timeout: Optional[float], force: bool, ignore_callback_error_on_revert: bool) -> bool:
        with self._status_transfer_lock:
            if self._is_status(Status.DECLARED | Status.TERMINATED):
                self._transfer_status(Status.TERMINATED, False, ignore_callback_error=True)
                return True
            elif self._is_status(Status.DECLARING | Status.STARTING | Status.READY | Status.PAUSED):
                # STARTING only when ready() fails (callback error)
                prev_status = self.status
                self._transfer_status(Status.TERMINATING, False, ignore_callback_error=True)
                self._check_execute.clear()
                # now locked at TERMINATING, new tickets cannot be registered
                with self._threads_lock:
                    if force:
                        for ticket in self._threads.values():
                            ticket.ask_for_stopping()
                if not self._stage.wait(timeout):
                    self._transfer_status(prev_status, False, ignore_callback_error=ignore_callback_error_on_revert)
                    if prev_status == Status.READY:
                        self._check_execute.set()
                    return False
                else:
                    # everything is ready, object is in TERMINATING status, terminate now
                    self._transfer_status(Status.FINALIZING, True, ignore_callback_error=True)
                    self._transfer_status(Status.TERMINATED, True, ignore_callback_error=True)
                    self._check_execute.set()   # waiting execution requests cannot proceed anymore
                    return True
            elif self._is_status(Status.OFFLOADED):
                return True
            else:
                assert False

    @property
    def is_terminated(self):
        return self._is_status(Status.TERMINATED)

    def terminate_as_offloaded(self, offloaded_to: ActorProfile):
        with self._status_transfer_lock:
            self._offloaded_to = offloaded_to
            self._transfer_status(Status.OFFLOADED, False, required_old_status=Status.PAUSED)
            self._check_execute.set()