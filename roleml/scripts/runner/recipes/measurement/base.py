import time


class MeasurementSession:

    def __init__(self, filename: str, app_name: str = 'app'):
        self.filename = filename
        self.app_name = app_name
        self.file = None

    def __enter__(self):
        self.begin()
    
    def begin(self, initial_state_time: int = 10):
        self.file = open(self.filename, mode='a')
        self.file.write(f'\nBELOW IS {self.app_name.upper()}\n')
        self.file.flush()
        self.start_script()
        if initial_state_time:
            print(f'Please wait for {initial_state_time}s while measuring initial state...')
            time.sleep(10)
        return self
    
    def start_script(self): ...

    def __exit__(self, exc_type, exc_val, exc_traceback):
        self.end()

    def end(self):
        self.file.close()   # type: ignore
