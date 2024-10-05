from roleml.core.role.base import Role
from roleml.shared.interfaces import Runnable


class ClientInitiator(Role, Runnable):

    RELATIONSHIP_NAME = 'server'

    def __init__(self, rep_instance_name: str = 'trainer'):
        super().__init__()
        self.rep_instance_name = rep_instance_name

    def run(self):
        self.call(self.RELATIONSHIP_NAME, 'register', args={'instance_name': self.rep_instance_name})
