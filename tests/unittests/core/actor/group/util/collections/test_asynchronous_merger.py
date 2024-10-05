import unittest

from roleml.core.actor.group.util.collections import AsynchronousKeyValueMerger, FilteredOut
from roleml.shared.collections.merger import CumulativeAddingValueMerger


class AsynchronousKeyValueMergerTestCase(unittest.TestCase):

    KEYS = 'a', 'b', 'c', 'd', 'e'
    SUCCESS_KEYS = 'a', 'b', 'c', 'd'
    FAILED_KEY = 'e'

    done: bool

    def setUp(self):
        self.done = False

    def data_filter(self, key, value):
        if key == self.FAILED_KEY and not self.done:
            self.done = True
            raise Exception('this is an exception')
        else:
            return key, value

    def test_exception_on_allow_append(self):
        merger = AsynchronousKeyValueMerger(
            self.KEYS, merger=CumulativeAddingValueMerger(), data_filter=self.data_filter, allow_append=True)
        for key in self.KEYS:
            try:
                merger.push(key, 1)
            except Exception:   # noqa
                pass
        merger.push(self.FAILED_KEY, 1)
        self.assertEqual(merger.result(1), len(self.KEYS))

    def data_filter_2(self, key, value):
        if key == self.FAILED_KEY and not self.done:
            self.done = True
            raise FilteredOut(True)
        else:
            return key, value

    def test_exception_on_allow_append_2(self):
        merger = AsynchronousKeyValueMerger(
            self.KEYS, merger=CumulativeAddingValueMerger(), data_filter=self.data_filter_2, allow_append=True)
        for key in self.KEYS:
            merger.push(key, 1)
        self.assertEqual(merger.result(1), len(self.KEYS) - 1)
        merger.push(self.FAILED_KEY, 1)
        self.assertEqual(merger.result(1), len(self.KEYS))


if __name__ == '__main__':
    unittest.main()
