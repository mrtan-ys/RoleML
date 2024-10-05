from roleml.core.actor.group.makers import Relationship
from roleml.library.roles.conductor.base import Conductor


class GLConductor(Conductor):

    def __init__(self, name: str = 'GL'):
        super().__init__(name)
        self.cli.add_command('start', self.start, expand_arguments=True)
        # command template:
        # start --num-rounds 75

    def start(self, num_rounds: int = 75):
        group = Relationship('coordinator')
        self.logger.info(f'total coordinators {len(list(group.targets))}')
        self.call_task_group(group.targets, 'start', args={'num_rounds': num_rounds})


if __name__ == '__main__':
    from roleml.scripts.runner.single import run_actor_from_cli
    run_actor_from_cli(default_config_file='conductor.yaml')
