from roleml.scripts.runner.recipes.measurement.base import MeasurementSession


class RPITemperatureMeasurementSession(MeasurementSession):
    
    def __init__(self, filename: str = 'temperature_rpi.log', app_name: str = 'app', *, default_time: int = 140):
        super().__init__(filename, app_name)

        import argparse
        import sys
        parser = argparse.ArgumentParser()
        parser.add_argument('--rpi:time', type=int, default=default_time, dest='time')
        args, argv = parser.parse_known_args()
        sys.argv = [sys.argv[0]] + argv     # consume rpi args and put remaining back to sys.argv for later consumption
        # Note: the bottom (last) argument parser must parse all arguments

        self.time = args.time
    
    def start_script(self):
        import os
        import subprocess as sp
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sp.Popen(['bash', f'{current_dir}/temperature_rpi.sh', str(self.time)], cwd=os.getcwd(), stdout=self.file)


def run_with_temperature_rpi_measurements(app_name: str = 'dml', *, default_time: int = 140, **options):
    import os
    workdir = os.getcwd()
    print(f'Working directory: {workdir}')
    with RPITemperatureMeasurementSession(f'{workdir}/temperature_rpi.log', app_name, default_time=default_time):
        from roleml.scripts.runner.single import run_actor_from_cli
        run_actor_from_cli(**options)


if __name__ == '__main__':
    run_with_temperature_rpi_measurements()
