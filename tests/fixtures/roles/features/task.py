import time
from threading import RLock

from roleml.core.role.base import Role
from roleml.core.role.channels import Task


class TaskProvider(Role):

    def __init__(self):
        super().__init__()
        self.num_calls = 0
        self.lock = RLock()

    @Task
    def heavy_work(self, *_, **__):
        time.sleep(5)
        return True

    @Task
    def heavy_work_another(self, *_, **__):
        with self.lock:
            self.num_calls += 1
            call_id = self.num_calls
        time.sleep(5)
        return call_id
