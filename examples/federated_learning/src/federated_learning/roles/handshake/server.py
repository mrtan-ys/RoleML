from typing import Optional
from typing_extensions import override

from roleml.core.messaging.types import MyArgs
from roleml.library.roles.initiator.server import ServerInitiator


class MyServerInitiator(ServerInitiator):

    def __init__(self, min_clients: int = 10, max_seconds: int = 86400, relationship_name: str = 'trainer',
                 num_rounds: int = 75, select_ratio: Optional[float] = None, count: int = 1):
        super().__init__(min_clients, max_seconds, relationship_name)
        # these arguments will be passed to the Coordinator
        self.num_rounds, self.select_ratio, self.count = num_rounds, select_ratio, count

    @override
    def start_impl(self):
        self.call_task('coordinator', 'run',
                       MyArgs(num_rounds=self.num_rounds, select_ratio=self.select_ratio, count=self.count))
