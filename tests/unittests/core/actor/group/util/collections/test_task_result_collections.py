import unittest

from roleml.core.actor.default.managers.task import Promise
from roleml.core.actor.group.helpers import ErrorHandlingStrategy
from roleml.core.actor.group.util.collections import TaskResultCollector, MergingFailedError
from roleml.core.role.exceptions import HandlerError
from roleml.shared.collections.merger import make_kv_merger, CumulativeAddingValueMerger


class TaskResultCollectionTestCase(unittest.TestCase):
    """ Here we do not actually call tasks but construct TaskInvocation objects directly. """

    KEYS = 'a', 'b', 'c', 'd', 'e'
    SUCCESS_KEYS = 'a', 'b', 'c', 'd'
    FAILED_KEY = 'e'

    def test_normal_case(self):
        collector = TaskResultCollector(self.KEYS, merger=make_kv_merger(CumulativeAddingValueMerger()))
        for key in self.KEYS:
            promise = Promise()
            promise.set_result(1)
            collector.push(key, promise)
        self.assertEqual(collector.result(), len(self.KEYS))

    def _test_task_error_case(self, on_error: ErrorHandlingStrategy) -> TaskResultCollector:
        collector = TaskResultCollector(
            self.KEYS,
            merger=make_kv_merger(CumulativeAddingValueMerger()), on_error=on_error)
        for key in self.SUCCESS_KEYS:
            promise = Promise()
            promise.set_result(1)
            collector.push(key, promise)
        return collector

    def test_task_error_case_with_ignore(self):
        collector = self._test_task_error_case(ErrorHandlingStrategy.IGNORE)
        promise_err = Promise()
        promise_err.set_result(HandlerError('this is an exception'))
        collector.push(self.FAILED_KEY, promise_err)
        self.assertEqual(collector.result(), len(self.KEYS) - 1)

    def test_task_error_case_with_ignore_append(self):
        collector = self._test_task_error_case(ErrorHandlingStrategy.IGNORE)
        promise_err = Promise()
        promise_err.set_result(HandlerError('this is an exception'))
        collector.push(self.FAILED_KEY, promise_err)
        self.assertEqual(collector.result(), len(self.KEYS) - 1)
        self.assertRaises(TypeError, collector.push, self.FAILED_KEY, 1)    # append not allowed
        # this is a hack; don't do this in production code
        collector._merger.push(self.FAILED_KEY, 1)
        self.assertEqual(collector._merger.merge(), len(self.KEYS))

    def test_task_error_case_with_raise_first(self):
        collector = self._test_task_error_case(ErrorHandlingStrategy.RAISE_FIRST)
        promise_err = Promise()
        promise_err.set_result(HandlerError('this is an exception'))
        self.assertRaises(HandlerError, collector.push, self.FAILED_KEY, promise_err)   # usually in another thread
        self.assertRaises(MergingFailedError, collector.result)

    def test_task_error_with_keep(self):
        collector = self._test_task_error_case(ErrorHandlingStrategy.KEEP)
        promise_err = Promise()
        promise_err.set_result(HandlerError('this is an exception'))
        self.assertRaises(TypeError, collector.push, self.FAILED_KEY, promise_err)  # int + Exception
        self.assertRaises(MergingFailedError, collector.result)


if __name__ == '__main__':
    unittest.main()
