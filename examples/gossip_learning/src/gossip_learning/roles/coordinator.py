from threading import Lock
from typing import Any, Callable

from roleml.core.role.base import Role
from roleml.core.role.channels import Event, EventHandler, Task
from roleml.core.role.elements import Element


class GLCoordinator(Role):

    def __init__(self):
        super().__init__()
        self.current_round = -1
        self.num_rounds = 0
        self.update_lock = Lock()

    gl_completed = Event()

    merge_op: Element[Callable[[Any, Any, int], Any]] \
        = Element(Callable, default_impl=lambda a, b, cnt: (a + b) / cnt)   # type: ignore

    @EventHandler('aggregator', 'gossip-accepted', expand=True)
    def on_aggregator_gossip_accepted(self, *_, **__):
        data, count = self.call('aggregator', 'get-data')
        if count == 0:
            return
        with self.update_lock:
            self.current_round += 1
            self.logger.debug(f'round {self.current_round} fetching gossip data of {count} items')
            # average with local model and apply
            local_model = self.call('trainer', 'get-model')
            averaged_model = self.merge_op()(local_model, data, count + 1)
            self.call('trainer', 'apply-update', payloads={'update': averaged_model})
            # train for another epoch
            new_update = self.call_task('trainer', 'train').result()
            test_result = self.call_task('trainer', 'test').result()
            self.logger.info(f'round {self.current_round} test result is: {test_result}')
            # propagate to another peer
            if self.current_round < self.num_rounds:
                self.call('aggregator', 'propagate-gossip', payloads={'data': new_update})
            else:
                self.logger.info('GL is done!!!!')
                self.gl_completed.emit()

    @Task(expand=True)
    def start(self, _, num_rounds: int):
        self.num_rounds = num_rounds
        initial_model, test_result = self.train_and_test()
        self.logger.info(f'initial training done, test result is {test_result}')
        self.call('aggregator', 'propagate-gossip', payloads={'data': initial_model})
        self.logger.info('initial trained model submitted for propagation')

    def train_and_test(self):
        self.current_round += 1
        update = self.call_task('trainer', 'train').result()
        test_result = self.call_task('trainer', 'test').result()
        return update, test_result
