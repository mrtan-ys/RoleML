from typing import Optional

from roleml.library.roles.conductor.base import Conductor


class FLConductor(Conductor):

    def __init__(self, name: str = 'FL'):
        super().__init__(name)
        self.cli.add_command('start', self.start, expand_arguments=True)
        # command template:
        # start --num-rounds 75 --select-ratio 0.25

    def start(self, num_rounds: int = 75, select_ratio: float = 0.0, count: int = 1):
        # epoch stands for local epochs on each client
        self.logger.info(f'start FL, {num_rounds=}, {select_ratio=}, {count=}')
        self.call_task('coordinator', 'run', args={
            'num_rounds': num_rounds, 'select_ratio': select_ratio, 'count': count
        }).result()


if __name__ == '__main__':
    from roleml.scripts.runner.single import run_actor_from_cli
    run_actor_from_cli(default_config_file='conductor.yaml')
