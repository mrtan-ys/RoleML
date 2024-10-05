import unittest
from typing import Literal

from roleml.core.actor.manager import BaseManager
from roleml.core.context import ActorProfile
from roleml.core.role.base import Role
from roleml.core.role.exceptions import HandlerError, NoSuchRoleError
from roleml.core.status import Status, StatusTransferCallbackError
from tests.fixtures.actors.basic import TestActor
from tests.fixtures.roles.basic import Host, Guest
from tests.unittests.core.actor.templates.single import SingleActorTestCase


class ProblematicManager(BaseManager):

    mode: Literal['add', 'start', 'terminate', 'none']

    def initialize(self, mode: Literal['add', 'start', 'terminate', 'none'] = 'add'):
        self.role_status_manager.add_callback(Status.STARTING, self._on_role_status_starting)
        self.role_status_manager.add_callback(Status.TERMINATING, self._on_role_status_terminating)
        self.mode = mode

    def add_role(self, role: Role):
        if self.mode == 'add':
            raise RuntimeError("it's on purpose")

    def _on_role_status_starting(self, instance_name: str, _):
        if self.mode == 'start':
            raise RuntimeError("it's on purpose")

    def _on_role_status_terminating(self, instance_name: str, _):
        if self.mode == 'terminate':
            raise RuntimeError("it's on purpose")


class ProblematicActor(TestActor):

    def __init__(self, profile: ActorProfile, **kwargs):
        super().__init__(profile, **kwargs)
        init_args = (self.ctx,
                     self.thread_manager, self.role_status_manager, self.procedure_invoker, self.procedure_provider)
        self.problematic_manager = ProblematicManager(*init_args)

    def _add_role_to_managers(self, role: Role):
        super()._add_role_to_managers(role)
        self.problematic_manager.add_role(role)


class ActorManagerErrorTestCase(SingleActorTestCase[ProblematicActor]):

    @property
    def actor_class(self):
        return ProblematicActor

    def setUp(self):
        super().setUp()
        self.host = Host()
        self.guest = Guest(purpose='car racing')

    def tearDown(self):
        self.actor.stop()
        # if added to actor before, they should be terminated (and removed) properly
        self.assertRaises(NoSuchRoleError, self.actor.role_status_manager.ctrl, 'host')
        self.assertRaises(NoSuchRoleError, self.actor.role_status_manager.ctrl, 'guest')

    def test_manager_error_on_adding_role(self):
        self.actor.problematic_manager.mode = 'add'
        self.assertRaises(RuntimeError, self.actor.add_role, 'host', self.host)
        self.actor.problematic_manager.mode = 'none'
        self.actor.add_role('guest', self.guest)
        self.actor.start_role('guest')
        self.assertRaises(HandlerError, self.guest.do_visit)  # role not open

    def test_manager_error_on_starting_role(self):
        self.actor.problematic_manager.mode = 'start'
        self.actor.add_role('host', self.host)
        self.assertRaises(StatusTransferCallbackError, self.actor.start_role, 'host')
        self.assertRaises(NoSuchRoleError, self.actor.role_status_manager.ctrl, 'host')

    def test_manager_error_on_starting_role_2(self):
        self.actor.problematic_manager.mode = 'start'
        self.actor.add_role('host', self.host)
        # actor.stop() must be called when an error happens, here we put this in teardown()
        self.assertRaises(StatusTransferCallbackError, self.actor.run)

    def test_manager_error_on_terminating_role(self):
        self.actor.problematic_manager.mode = 'terminate'
        self.actor.add_role('host', self.host)
        self.actor.start_role('host')
        self.actor.stop_role('host')    # should raise no exception


if __name__ == '__main__':
    unittest.main()
