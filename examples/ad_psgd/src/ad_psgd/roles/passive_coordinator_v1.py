from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler, Task


class AdCoordinator(Role):

    def __init__(self):
        super().__init__()
        self.round = -1
        self.finish_peer_num = 0
        self.is_finished = False

    @Task(expand=True)
    def start(self, _):
        self.train_and_test()

    @EventHandler('aggregator', 'merge-completed', expand=True)
    def on_aggregator_merge_completed(self, *_, **__):
        self.train_and_test()

    # noinspection DuplicatedCode
    def train_and_test(self):
        self.round += 1
        update = self.call_task('trainer', 'train').result()
        self.logger.info(f'round {self.round} local training done')
        test_result = self.call_task('trainer', 'test').result()
        self.logger.info(f'round {self.round} test result is {test_result}')
        return update, test_result
