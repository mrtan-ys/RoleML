from roleml.library.roles.conductor.base import Conductor


class ELConductor(Conductor):

    def __init__(self, name: str = 'EL'):
        super().__init__(name)
        self.cli.add_command('start', self.start, expand_arguments=True)
        # command template:
        # start --num-rounds 75

    def start(self, num_rounds: int = 75):
        self.call_task('coordinator', 'run', args={'num_rounds': num_rounds}).result()


if __name__ == '__main__':
    from roleml.scripts.runner.single import run_actor_from_cli
    run_actor_from_cli(default_config_file='conductor.yaml')
