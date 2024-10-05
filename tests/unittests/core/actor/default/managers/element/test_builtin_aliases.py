import json
import os
import time
import unittest
from threading import Thread

from roleml.core.actor.default import ActorBuilder
from roleml.core.builders.actor import ActorBootstrapSpec
from tests.fixtures.roles.features.element import DataHolder


class ElementSpecialPartAliasGettingTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.data = {'a': 1}

    # noinspection PyTypeChecker
    def test_special_json(self):
        filename = 'data.json'
        conf: ActorBootstrapSpec = {
            'name': 'User1',
            'address': '127.0.0.1',
            'roles': {
                'data-holder': {
                    'class': DataHolder,
                    'impl': {
                        'data': {
                            'impl': self.data,
                            'serializer': 'json',
                            'serializer_destination': filename,
                            'serializer_mode': 'text',
                        }
                    }
                }
            }
        }
        builder = ActorBuilder()
        builder.load_config(conf)
        actor = builder.build()
        Thread(target=actor.run).start()
        time.sleep(1)
        actor.stop()
        with open(filename) as f:
            recovered_data = json.load(f)
        self.assertEqual(recovered_data, self.data)
        os.remove(filename)


if __name__ == '__main__':
    unittest.main()
