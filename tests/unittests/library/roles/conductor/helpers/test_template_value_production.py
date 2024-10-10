import unittest
from typing import Iterable

from roleml.library.roles.conductor.helpers import _build_template_value_producer   # noqa: in unit test


class TemplateValueProductionTestCase(unittest.TestCase):

    def test_broadcast_template_1(self):
        template = '$a[4-20]'
        producer = _build_template_value_producer(template)
        value = next(producer)
        for i in range(4, 20 + 1):
            self.assertIn(i, value)
        self.assertNotIn(3, value)
        self.assertNotIn(21, value)
        self.assertNotIn(27486, value)
        self.assertEqual(value, next(producer))

    def test_broadcast_template_2(self):
        template = '$a[4-20,99]'
        producer = _build_template_value_producer(template)
        value = next(producer)
        for i in range(4, 20 + 1):
            self.assertIn(i, value)
        self.assertIn(99, value)
        self.assertNotIn(3, value)
        self.assertNotIn(21, value)
        self.assertEqual(value, next(producer))

    def test_broadcast_template_invalid(self):
        template = '$a[4~20]'
        self.assertRaises(ValueError, _build_template_value_producer, template)

    def test_random_template_1(self):
        template = '$r[4, 20]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            value = next(producer)
            self.assertIn(value, range(4, 20 + 1))

    def test_random_template_2(self):
        template = '$r[4, 20, 2]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            value = next(producer)
            self.assertIn(value, range(4, 20 + 1, 2))

    def test_random_template_3(self):
        template = '$r[4, 20, 2, 2]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            values = next(producer)
            self.assertIsInstance(values, Iterable)
            for value in values:
                self.assertIn(value, range(4, 20 + 1, 2))
                # self.assertIn(value, range(4, 20 + 1))

    def test_random_template_invalid(self):
        template = '$r[4, 20, 2, 2, 5]'  # additional argument
        self.assertRaises(ValueError, _build_template_value_producer, template)

    def test_exclusion_template_1(self):
        template = '$e[1-100, 4-11]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            value = next(producer)
            self.assertIn(value, range(1, 100 + 1))
            self.assertNotIn(value, range(4, 11 + 1))

    def test_exclusion_template_2(self):
        template = '$e[1-100, 4-11, 61-70]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            value = next(producer)
            self.assertIn(value, range(1, 100 + 1))
            self.assertNotIn(value, range(4, 11 + 1))
            self.assertNotIn(value, range(61, 70 + 1))

    def test_exclusion_template_invalid(self):
        template = '$e[]'   # empty
        self.assertRaises(ValueError, _build_template_value_producer, template)
        template = '$e[1-100, 4~11]'    # empty
        self.assertRaises(ValueError, _build_template_value_producer, template)

    def test_scatter_template(self):
        template = '$c[5-21]'
        producer = _build_template_value_producer(template)
        for _ in range(100):
            for expected_value in range(5, 21 + 1):
                value = next(producer)
                self.assertEqual(value, expected_value)

    def test_scatter_template_invalid(self):
        template = '$c[4~99]'
        self.assertRaises(ValueError, _build_template_value_producer, template)


if __name__ == '__main__':
    unittest.main()
