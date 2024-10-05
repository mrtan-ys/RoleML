import logging
from collections import defaultdict
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Final, Optional

from roleml.core.role.exceptions import NoSuchRoleError
from roleml.core.status import Status, StatusControl


class RoleStatusManager:

    ignore_callback_error_when: Final = set([Status.TERMINATING, Status.FINALIZING, 
                                             Status.TERMINATED, Status.OFFLOADED])

    def __init__(self, lock: Optional[RLock] = None):
        self._roles: dict[str, StatusControl] = {}
        self._callbacks: defaultdict[Status, list[Callable[[str, Status], Any]]] = defaultdict(list)
        self._callbacks[Status.TERMINATED].append(self._on_terminated)
        self._logger = logging.getLogger('roleml.actor.status-manager')
        self._lock = lock or RLock()

        self.ctrls = MappingProxyType(self._roles)

    def ctrl(self, instance_name: str):
        with self._lock:
            try:
                return self._roles[instance_name]
            except KeyError:
                raise NoSuchRoleError(instance_name)

    def add_role(self, instance_name: str) -> StatusControl:
        with self._lock:
            if instance_name in self._roles:
                raise RuntimeError(f'role named {instance_name} already exists')
            sc = StatusControl(instance_name)
            sc.add_listener(self._listener_callback)
            self._roles[instance_name] = sc
            return sc   # note: other classes should NEVER store this reference

    def add_callback(self, status: Status, callback: Callable[[str, Status], Any]):
        self._callbacks[status].append(callback)

    def _listener_callback(self, instance_name: str, current_status: Status, old_status: Status):
        self._logger.debug(f'role status transfer ({instance_name} {old_status} -> {current_status})')
        for cb in self._callbacks[current_status]:
            try:
                cb(instance_name, old_status)
            except Exception:
                self._logger.exception(f'error in role status transfer callback ({old_status} -> {current_status})')
                if current_status not in self.ignore_callback_error_when:
                    raise

    def _on_terminated(self, instance_name: str, _):
        with self._lock:
            del self._roles[instance_name]
