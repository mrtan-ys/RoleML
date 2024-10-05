from typing import Callable

from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler, Task
from roleml.core.role.elements import Element


class AdCoordinator(Role):

    def __init__(self):
        super().__init__()
        self.round = -1
        self.finish_peer_num = 0
        self.is_finished = False

    merge_op = Element(Callable, default_impl=lambda a, b, cnt: (a + b) / cnt)

    @Task(expand=True)
    def start(self, _, num_rounds: int):
        for i in range(num_rounds):
            if not self.is_finished:
                self.train_and_test()

    @EventHandler('relevant-coordinator', 'train-completed', expand=True)
    def on_active_coordinator_train_completed(self, *_, **__):
        self.finish_peer_num += 1
        group = self.ctx.relationships.get_relationship('peer')
        total_peer_num = len(list(group))
        if total_peer_num == self.finish_peer_num:
            self.is_finished = True
        self.logger.info(f'active peer finished: {self.finish_peer_num}/{total_peer_num}')

    # noinspection DuplicatedCode
    def train_and_test(self):
        self.round += 1
        update = self.call_task('trainer', 'train').result()
        self.logger.info(f'round {self.round} local training done')
        test_result = self.call_task('trainer', 'test').result()
        self.logger.info(f'round {self.round} test result is {test_result}')
        return update, test_result
