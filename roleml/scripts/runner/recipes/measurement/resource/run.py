from roleml.scripts.runner.recipes.measurement.base import MeasurementSession


class ResourceMeasurementSession(MeasurementSession):

    def __init__(self, filename: str = 'resource.log', app_name: str = 'app'):
        super().__init__(filename, app_name)
    
    def start_script(self):
        import os
        import subprocess as sp
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sp.Popen(['bash', f'{current_dir}/resource.sh', f'{os.getpid()}'], cwd=os.getcwd(), stdout=self.file)


def run_with_resource_measurements(app_name: str = 'dml', **options):
    import os
    workdir = os.getcwd()
    print(f'Working directory: {workdir}')
    with ResourceMeasurementSession(f'{workdir}/resource.log', app_name):
        from roleml.scripts.runner.single import run_actor_from_cli
        run_actor_from_cli(**options)


if __name__ == '__main__':
    run_with_resource_measurements()
