import time
import unittest

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from tests.fixtures.roles.features.task import TaskProvider
from tests.unittests.core.actor.default.managers.base import DefaultActorManagersTestCase


class DefaultTaskManagerConcurrencyTestCase(DefaultActorManagersTestCase):

    class TaskCaller(Role):
        def do_call_task(self, target: RoleInstanceID, channel_name: str):
            return self.call_task(target, channel_name)

    def test_concurrency_different_channels(self):
        self.actorB.add_role('task-provider', TaskProvider())
        self.actorB.start_role('task-provider')
        caller = DefaultTaskManagerConcurrencyTestCase.TaskCaller()
        self.actorA.add_role('task-caller', caller)
        self.actorA.start_role('task-caller')
        start = time.time()
        r1 = caller.do_call_task(RoleInstanceID(self.profileB.name, 'task-provider'), 'heavy-work')
        r2 = caller.do_call_task(RoleInstanceID(self.profileB.name, 'task-provider'), 'heavy-work-another')
        self.assertEqual(r1.result(), True)
        self.assertEqual(r2.result(), 1)
        end = time.time()
        # time should be roughly > 5s but far < 10s
        self.assertLess(end - start, 10.0, 'concurrency is not working')

    def test_concurrency_same_channel(self):
        self.actorB.add_role('task-provider', TaskProvider())
        self.actorB.start_role('task-provider')
        caller = DefaultTaskManagerConcurrencyTestCase.TaskCaller()
        self.actorA.add_role('task-caller', caller)
        self.actorA.start_role('task-caller')
        start = time.time()
        r1 = caller.do_call_task(RoleInstanceID(self.profileB.name, 'task-provider'), 'heavy-work-another')
        r2 = caller.do_call_task(RoleInstanceID(self.profileB.name, 'task-provider'), 'heavy-work-another')
        results = sorted([r1.result(), r2.result()])
        self.assertEqual(results, [1, 2])
        end = time.time()
        # time should be roughly > 5s but far < 10s
        self.assertLess(end - start, 10.0, 'concurrency is not working')


if __name__ == '__main__':
    unittest.main()
