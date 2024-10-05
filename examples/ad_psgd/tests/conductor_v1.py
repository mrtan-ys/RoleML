"""
In version v1, passive nodes only train the local model after receiving a model and completing aggregation.
In version v2, passive nodes actively loop through the training of the local model.
current version is v1
"""

from roleml.core.actor.group.makers import Relationship
from roleml.library.roles.conductor.base import Conductor


class AdConductor(Conductor):

    def __init__(self, name: str = 'AD-PSGD'):
        super().__init__(name)
        self.cli.add_command('start', self.start, expand_arguments=True)
        # command template:
        # start --num-rounds 75

    # noinspection DuplicatedCode
    def start(self, num_rounds: int = 20):
        group = Relationship('active-coordinator')
        self.logger.info(f'total active coordinators {len(list(group.targets))}')
        self.call_task_group(group.targets, 'start', args={'num_rounds': num_rounds})

        group = Relationship('passive-coordinator')
        self.logger.info(f'total passive coordinators {len(list(group.targets))}')
        self.call_task_group(group.targets, 'start')


if __name__ == '__main__':
    from roleml.scripts.runner.single import run_actor_from_cli
    run_actor_from_cli(default_config_file='conductor-v1.yaml')
