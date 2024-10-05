import time
import unittest
from threading import Thread

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusAtPausedTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()
        self.status_ctrl.declared()
        self.status_ctrl.ready()
        self.status_ctrl.pause()

    def test_current_status(self):
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)
        self.status_ctrl.pause(False)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)
        self.status_ctrl.pause(True)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)
        self.assertEqual(self.status_ctrl.is_declared_only, False)
        self.assertEqual(self.status_ctrl.is_declared, True)
        self.assertEqual(self.status_ctrl.is_ready, False)
        self.assertEqual(self.status_ctrl.is_paused, True)
        self.assertEqual(self.status_ctrl.is_terminated, False)

    def test_to_declared(self):
        self.assertRaises(StatusError, self.status_ctrl.declared)

    def test_to_ready(self):
        self.status_ctrl.ready()
        self.assertEqual(self.status_ctrl.status, Status.READY)

    def test_to_terminated_unforced(self):
        self.status_ctrl.terminate(force=False)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)

    def test_to_terminated_forced(self):
        self.status_ctrl.terminate(force=True)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)

    def test_to_terminate_while_thread_waiting_for_execution(self):
        error = None

        def waiting_thread():
            nonlocal error
            try:
                with self.status_ctrl.acquire_execution(timeout=None):
                    error = False
            except StatusError:
                error = True

        Thread(target=waiting_thread).start()
        time.sleep(2)
        self.status_ctrl.terminate(force=True)
        time.sleep(1)   # wait for waiting_thread to handle exception
        self.assertEqual(error, True)


if __name__ == '__main__':
    unittest.main()
