import unittest
from pathlib import Path
from typing import Callable, Any, Literal, IO

from roleml.core.actor.manager.bases.elements import ElementImplementation
from tests.fixtures.roles.features.element import DataHolder, DataFetcher
from tests.unittests.core.actor.default.managers.base import DefaultActorManagersTestCase


class DefaultElementManagerSerializationTestCase(DefaultActorManagersTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.data = {'a': 1, 'b': True, 'c': {'d': 0.0, 'e': []}}

    def test_json_serialization(self):
        import json
        self._test_serialization(Path.cwd() / 'data.json', json.dump, 'text', json.load, 'text')

    def test_pickle_serialization(self):
        import pickle
        self._test_serialization(Path.cwd() / 'data.pkl', pickle.dump, 'binary', pickle.load, 'binary')

    def _test_serialization(
            self, save_path: Path,
            serializer_func: Callable[[Any, IO], None], serializer_mode: Literal['binary', 'text'],
            deserializer_func: Callable[[IO], Any], deserializer_mode: Literal['binary', 'text']):
        save_filename = str(save_path)

        def serializer(obj):
            with open(save_filename, 'wb' if serializer_mode == 'binary' else 'w') as file:
                serializer_func(obj, file)

        def deserializer() -> Any:
            with open(save_filename, 'rb' if deserializer_mode == 'binary' else 'r') as file:
                return deserializer_func(file)

        self.actorA.add_role('data-holder', DataHolder())
        self.actorA.implement_element(
            'data-holder', 'data',
            ElementImplementation(loader=lambda: self.data, serializer=serializer, eager_load=True))
        self.actorA.start_role('data-holder')
        self.actorA.stop()

        self.actorB.add_role('data-holder', DataHolder())
        self.actorB.implement_element(
            'data-holder', 'data',
            ElementImplementation(loader=deserializer, eager_load=True))
        self.actorB.start_role('data-holder')
        data_fetcher = DataFetcher()
        self.actorB.add_role('data-fetcher', data_fetcher)
        self.actorB.start_role('data-fetcher')

        self.assertEqual(data_fetcher.do_get_data(), self.data)
        save_path.unlink()


if __name__ == '__main__':
    unittest.main()
