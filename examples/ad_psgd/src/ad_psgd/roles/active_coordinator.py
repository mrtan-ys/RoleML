from roleml.core.role.base import Role
from roleml.core.role.channels import Task, Event


class AdCoordinator(Role):

    train_completed = Event()

    @Task(expand=True)
    def start(self, _, num_rounds: int):
        self.logger.info(f'start AD-PSGD run, num of rounds is {num_rounds}')
        for i in range(num_rounds):
            self.call_task('trainer', 'train').result()
            self.call_task('aggregator', 'aggregate').result()
            test_result = self.call_task('trainer', 'test').result()
            self.logger.info(f'round {i + 1} aggregation done, test result is {test_result}')
        self.train_completed.emit()

