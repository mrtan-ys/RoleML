import random
from threading import Lock

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import Task, Event


class AdAggregator(Role):

    def __init__(self):
        super().__init__()
        self.model_lock = Lock()

    merge_completed = Event()

    @Task(expand=True)
    def aggregate(self, _,):
        selected_peer = self.select_peer()
        with self.model_lock:
            local_model = self.call('trainer', 'get-model')
            merged_model = self.call_task(selected_peer, 'merge-model', payloads={'data': local_model}).result()
            self.call('trainer', 'apply-update', payloads={'update': merged_model})
            self.merge_completed.emit(args={'peer': selected_peer})

    def select_peer(self) -> RoleInstanceID:
        peers = list(self.ctx.relationships.get_relationship('peer'))
        return random.sample(peers, k=1)[0]
