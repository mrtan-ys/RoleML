from roleml.core.role.base import Role
from roleml.core.role.channels import Task
from roleml.extensions.plugins.partner.base import Partner


class RacingDriver(Role):

    @Task(expand=True)
    def practice(self, _):
        return "I am ready!"

    @Task(expand=True)
    def take_pole(self, _):
        return "Let's go!"

    @Task(expand=True)
    def win(self, _):
        return 'Yes!'


class RaceEngineer(Role):

    def __init__(self):
        super().__init__()
        self.won = False

    driver = Partner('driver')

    def race_week(self):
        self.driver.task('practice').result()
        self.driver.task('take-pole').result()
        self.driver.task('win').result()
        self.won = True
