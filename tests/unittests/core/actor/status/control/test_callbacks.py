import threading
import time
import unittest

from roleml.core.status import Status, StatusControl


class RoleStatusControlCallbackTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_control = StatusControl()
        self.a = 1

    def test_callbacks_regular_flow(self):
        self.status_control.add_callback(Status.DECLARED, self._callback_declared_default)
        self.status_control.add_callback(Status.STARTING, self._callback_starting_default)
        self.status_control.add_callback(Status.READY, self._callback_ready_default)
        self.status_control.add_callback(Status.PAUSING, self._callback_pausing_default)
        self.status_control.add_callback(Status.PAUSED, self._callback_paused_default)
        self.status_control.add_callback(Status.TERMINATING, self._callback_terminating_default)
        self.status_control.add_callback(Status.FINALIZING, self._callback_finalizing_default)
        self.status_control.add_callback(Status.TERMINATED, self._callback_terminated_default)

        self.status_control.declared()
        self.status_control.ready()
        self.status_control.pause()
        self.status_control.terminate()

        self.assertEqual(self.a, 9)

    def test_callbacks_with_reversing(self):
        self.status_control.add_callback(Status.READY, self._callback_ready_advanced)
        self.status_control.add_callback(Status.PAUSING, self._callback_pausing_default)
        self.status_control.add_callback(Status.TERMINATING, self._callback_terminating_advanced)

        self.status_control.declared()
        self.status_control.ready()

        threading.Thread(target=self._task).start()
        time.sleep(1)
        self.status_control.try_pause(timeout=1)
        self.assertEqual(self.status_control.status, Status.READY)
        self.status_control.try_terminate(timeout=1)
        self.assertEqual(self.a, 6)

    def _task(self):
        with self.status_control.acquire_execution():
            time.sleep(5)

    def _callback_declared_default(self, old_status: Status):
        self.assertEqual(old_status, Status.DECLARING)
        self.a += 1

    def _callback_starting_default(self, old_status: Status):
        self.assertEqual(old_status, Status.DECLARED)
        self.a += 1

    def _callback_ready_default(self, old_status: Status):
        self.assertEqual(old_status, Status.STARTING)
        self.a += 1

    def _callback_ready_advanced(self, old_status: Status):
        self.assertIn(old_status, Status.PAUSING | Status.TERMINATING | Status.STARTING)
        self.a += 1

    def _callback_pausing_default(self, old_status: Status):
        self.assertEqual(old_status, Status.READY)
        self.a += 1

    def _callback_paused_default(self, old_status: Status):
        self.assertEqual(old_status, Status.PAUSING)
        self.a += 1

    def _callback_terminating_default(self, old_status: Status):
        self.assertEqual(old_status, Status.PAUSED)
        self.a += 1

    def _callback_terminating_advanced(self, old_status: Status):
        self.assertIn(old_status, Status.PAUSED | Status.READY)
        self.a += 1

    def _callback_finalizing_default(self, old_status: Status):
        self.assertEqual(old_status, Status.TERMINATING)
        self.a += 1

    def _callback_terminated_default(self, old_status: Status):
        self.assertEqual(old_status, Status.FINALIZING)
        self.a += 1


if __name__ == '__main__':
    unittest.main()
