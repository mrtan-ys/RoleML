import json
from pathlib import Path
from typing import cast
import unittest

from roleml.core.builders.actor import ActorBootstrapSpec
from roleml.core.builders.role import RoleBuilder
from tests.fixtures.actors.basic import TestActorBuilder
from tests.fixtures.roles.features.element import DataFetcher


class ElementPresetMechanismTestCase(unittest.TestCase):

    DEFAULT_OBJECT = b'Hello world!'
    ALTERED_OBJECT = b'Hello world!!'

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture_root = Path(__file__).parent.parent.parent.parent / 'fixtures'
    
    def setUp(self) -> None:
        self.builder = TestActorBuilder()
        with open(self.fixture_root / 'configs' / 'element.json') as f:
            self.base_config = cast(ActorBootstrapSpec, json.load(f))
        self.base_config['element_preset'] = {
            "tests.fixtures.roles.features.element.DataHolder": {
                'elements': {
                    'data': {
                        'impl': self.DEFAULT_OBJECT
                    }
                },
            }
        }

    def tearDown(self):
        RoleBuilder.clear_element_preset()

    def test_element_preset_normal(self):
        self.builder.load_config(self.base_config)
        actor = self.builder.build()
        actor.run()     # only starts the roles
        data_fetcher = cast(DataFetcher, actor.roles['data-fetcher'])
        self.assertEqual(data_fetcher.do_get_data(), self.DEFAULT_OBJECT)

    def test_element_preset_conflict_override(self):
        self.base_config['roles']['data-holder']['impl'] = {
            'data': {
                'impl': self.ALTERED_OBJECT
            }
        }
        self.builder.load_config(self.base_config)
        actor = self.builder.build()
        actor.run()     # only starts the roles
        data_fetcher = cast(DataFetcher, actor.roles['data-fetcher'])
        self.assertEqual(data_fetcher.do_get_data(), self.ALTERED_OBJECT)

    def test_element_preset_conflict_preset(self):
        self.base_config['roles']['data-holder']['impl'] = {
            'data': {
                'impl': self.ALTERED_OBJECT
            }
        }
        RoleBuilder.update_element_preset('tests.fixtures.roles.features.element.DataHolder', on_conflict='preset')
        self.builder.load_config(self.base_config)
        actor = self.builder.build()
        actor.run()     # only starts the roles
        data_fetcher = cast(DataFetcher, actor.roles['data-fetcher'])
        self.assertEqual(data_fetcher.do_get_data(), self.DEFAULT_OBJECT)

    def test_element_preset_conflict_preset_2(self):
        self.base_config['roles']['data-holder']['impl'] = {
            'data': {
                'impl': self.ALTERED_OBJECT
            }
        }
        self.base_config['element_preset']['tests.fixtures.roles.features.element.DataHolder']['on_conflict'] = 'preset'
        self.builder.load_config(self.base_config)
        actor = self.builder.build()
        actor.run()     # only starts the roles
        data_fetcher = cast(DataFetcher, actor.roles['data-fetcher'])
        self.assertEqual(data_fetcher.do_get_data(), self.DEFAULT_OBJECT)

    def test_element_preset_conflict_error(self):
        self.base_config['roles']['data-holder']['impl'] = {
            'data': {
                'impl': self.ALTERED_OBJECT
            }
        }
        RoleBuilder.update_element_preset('tests.fixtures.roles.features.element.DataHolder', on_conflict='error')
        self.builder.load_config(self.base_config)
        self.assertRaises(TypeError, self.builder.build)


if __name__ == '__main__':
    unittest.main()
