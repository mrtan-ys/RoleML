import time
import unittest

from roleml.core.context import RoleInstanceID
from roleml.core.role.base import Role
from roleml.core.role.channels import EventHandler
from tests.fixtures.roles.features.event import EventProvider
from tests.unittests.core.actor.default.managers.base import DefaultActorManagersTestCase


class DefaultEventManagerBasicTestCase(DefaultActorManagersTestCase):

    def test_event_pubsub(self):
        self.actorB.add_role('ev-provider', EventProvider())
        self.actorB.start_role('ev-provider')

        self.actorA.ctx.relationships.add_to_relationship(
            'event-provider', RoleInstanceID(self.profileB.name, 'ev-provider'))

        class EventSubscriber(Role):
            def __init__(self):
                super().__init__()
                self.passed = False
            @EventHandler('event-provider', 'visited', expand=True)     # noqa: blank line
            def on_event_provider_visited(self_, source: RoleInstanceID, info: str, **_):   # noqa: parameter naming
                self.assertEqual(info, 'Event triggered!')
                self_.passed = True
            def do_visit(self):    # noqa: parameter naming
                self.call('event-provider', 'visit')
        subscriber = EventSubscriber()

        self.actorA.add_role('ev-subscriber', subscriber)
        self.actorA.start_role('ev-subscriber')
        subscriber.do_visit()
        time.sleep(1)
        self.assertTrue(subscriber.passed)


if __name__ == '__main__':
    unittest.main()
