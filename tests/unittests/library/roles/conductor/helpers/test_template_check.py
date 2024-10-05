import unittest

from roleml.library.roles.conductor.helpers import _is_template     # noqa: in unit test


class TemplateCheckTestCase(unittest.TestCase):

    def test_correct_template_detection(self):
        templates = '@[4-11]', '^[4, 11]', '^[4, 11, 2]', '^[4, 11, 2, 3]', '~[1-100, 4-11]', '$[4-11]'
        for template in templates:
            self.assertTrue(_is_template(template))

    def test_incorrect_template_detection(self):
        templates = '#[4-11]', '*[4, 11]', '![4, 11, 2]', '&[4, 11, 2, 3]', '&[1-100', '$1'
        for template in templates:
            self.assertFalse(_is_template(template))


if __name__ == '__main__':
    unittest.main()
