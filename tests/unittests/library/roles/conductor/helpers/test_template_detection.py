import unittest

from roleml.library.roles.conductor.helpers import detect_templates, apply_templates


class TemplateDetectionTestCase(unittest.TestCase):

    def test_path_detection(self):
        config = {
            'a': 'b',
            'c': [1, 2, '$[1-10]'],
            'd': {
                'e': 'f',
                'g': '@[4-22]',
            },
        }
        producers = {}
        detect_templates(config, producers)
        expected_paths = [('c', 2), ('d', 'g')]
        self.assertEqual(list(producers.keys()), expected_paths)

    def test_template_application(self):
        original_config = {
            'a': '$[1-10]',
            'b': ['c', '$[11-20]']
        }
        expected_range_a = iter(range(1, 10 + 1))
        expected_range_b = iter(range(11, 20 + 1))
        producers = {}
        detect_templates(original_config, producers)
        for _ in range(10):
            de_randomized_config = apply_templates(original_config, producers)
            self.assertEqual(de_randomized_config, {'a': next(expected_range_a), 'b': ['c', next(expected_range_b)]})


if __name__ == '__main__':
    unittest.main()
