from threading import Lock
from typing import Any, Callable

from roleml.core.role.base import Role
from roleml.core.role.channels import Event, Task
from roleml.core.role.elements import Element


class AdAggregator(Role):

    def __init__(self):
        super().__init__()
        self.model_lock = Lock()

    merge_op: Element[Callable[[Any, Any, int], Any]] \
        = Element(Callable, default_impl=lambda a, b, cnt: (a + b) / cnt)     # type: ignore
    merge_completed = Event()

    @Task(expand=True)
    def merge_model(self, _, data: Any):
        with self.model_lock:
            local_model = self.call('trainer', 'get-model')
            merged_model = self.merge_op()(local_model, data, 2)
            self.call('trainer', 'apply-update', payloads={'update': merged_model})
        self.merge_completed.emit()
        return merged_model
