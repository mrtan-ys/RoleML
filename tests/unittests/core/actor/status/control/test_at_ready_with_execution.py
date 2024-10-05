import threading
import time
import unittest

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusAtReadyWithExecutionTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()
        self.status_ctrl.declared()
        self.status_ctrl.ready()
        self.a = 1

    def test_acquire_execution(self):
        a = 1
        with self.status_ctrl.acquire_execution():
            a += 1
        self.assertEqual(a, 2)
        with self.status_ctrl.acquire_execution(timeout=20):
            a += 2
        self.assertEqual(a, 4)

    def _task(self):
        with self.status_ctrl.acquire_execution():
            time.sleep(5)
            self.a += 1

    def _task_stoppable(self):
        with self.status_ctrl.acquire_execution() as et:
            time.sleep(2)
            self.a += 1
            if et.should_stop:
                et.stop()
            else:
                time.sleep(3)
                self.a += 1

    def test_acquire_execution_at_pausing(self):
        threading.Thread(target=self._task).start()
        time.sleep(2)
        threading.Thread(target=self.status_ctrl.pause).start()
        self.assertRaises(StatusError, self.status_ctrl.acquire_execution, timeout=1)

    def test_try_acquire_and_wait_for_resume(self):
        def pause_and_resume():
            self.status_ctrl.pause()
            time.sleep(3)
            self.status_ctrl.ready()

        threading.Thread(target=pause_and_resume).start()
        time.sleep(1.5)
        with self.status_ctrl.acquire_execution(timeout=5):
            self.a += 1
        self.assertEqual(self.a, 2)

    def test_try_acquire_and_wait_for_resume_advanced(self):
        def pause_and_resume():
            self.status_ctrl.pause()    # will be PAUSING first
            self.status_ctrl.ready()

        threading.Thread(target=self._task).start()
        time.sleep(1.5)
        threading.Thread(target=pause_and_resume).start()
        time.sleep(1.5)
        with self.status_ctrl.acquire_execution(timeout=5):
            self.a += 1
        self.assertEqual(self.a, 3)

    def test_to_declared(self):
        threading.Thread(target=self._task).start()
        self.assertRaises(StatusError, self.status_ctrl.declared)

    def test_pause_with_running_thread(self):
        threading.Thread(target=self._task).start()
        self.status_ctrl.pause()
        self.assertEqual(self.a, 2)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)

    def test_pause_with_running_stoppable_thread(self):
        threading.Thread(target=self._task_stoppable).start()
        self.status_ctrl.pause()
        self.assertEqual(self.a, 3)     # we are not forcing here
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)

    def test_pause_forced_with_running_stoppable_thread(self):
        threading.Thread(target=self._task_stoppable).start()
        self.status_ctrl.pause(force=True)
        self.assertEqual(self.a, 2)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)

    def test_try_pause_with_running_thread_success(self):
        threading.Thread(target=self._task).start()
        self.status_ctrl.try_pause(10)
        self.assertEqual(self.a, 2)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)

    def test_try_pause_forced_with_running_stoppable_thread_success(self):
        threading.Thread(target=self._task_stoppable).start()
        time.sleep(1)
        self.status_ctrl.try_pause(10, force=True)
        self.assertEqual(self.a, 2)
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)

    def test_try_pause_with_running_thread_not_success(self):
        threading.Thread(target=self._task).start()
        self.status_ctrl.try_pause(2.5)
        self.assertEqual(self.a, 1)
        self.assertEqual(self.status_ctrl.status, Status.READY)

    def test_try_terminate_with_running_thread_success(self):
        threading.Thread(target=self._task).start()
        self.status_ctrl.try_terminate(10)
        self.assertEqual(self.a, 2)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)

    def test_try_terminate_with_running_thread_not_success(self):
        threading.Thread(target=self._task).start()
        self.status_ctrl.try_terminate(2.5)
        self.assertEqual(self.a, 1)
        self.assertEqual(self.status_ctrl.status, Status.READY)


if __name__ == '__main__':
    unittest.main()
