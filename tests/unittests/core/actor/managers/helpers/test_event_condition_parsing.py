import unittest

from roleml.core.actor.manager.helpers import parse_conditions, check_conditions


class RoleDynamicAssignmentTestCase(unittest.TestCase):

    def test_parse_conditions_cache(self):
        conditions = {'a': 'actor', 'b__gt': 2, 'c__contains': 3}
        pc1 = parse_conditions(conditions)
        pc2 = parse_conditions(conditions)
        self.assertEqual(id(pc1), id(pc2))

    def test_conditions_match(self):
        conditions = {'a': 'actor', 'b__gt': 2, 'c__contains': 3}
        parsed_conditions = parse_conditions(conditions)
        self.assertTrue(check_conditions({'a': 'actor', 'b': 5, 'c': [3, 4]}, parsed_conditions))
        self.assertFalse(check_conditions({'a': 'hello', 'b': 5, 'c': [3, 4]}, parsed_conditions))
        self.assertFalse(check_conditions({'a': 'actor', 'b': 2, 'c': [3, 4]}, parsed_conditions))
        self.assertFalse(check_conditions({'a': 'actor', 'b': 3, 'c': [2, 4]}, parsed_conditions))


if __name__ == '__main__':
    unittest.main()
