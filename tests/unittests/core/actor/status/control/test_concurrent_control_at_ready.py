import threading
import time
import unittest

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusConcurrentControlAtReadyTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()
        self.status_ctrl.declared()
        self.status_ctrl.ready()
        self.a = 1

    def _task(self, duration: float):
        with self.status_ctrl.acquire_execution():
            time.sleep(duration)
            self.a += 1

    def test_concurrent_pause(self):
        threading.Thread(target=self._task, args=(3, )).start()
        time.sleep(1)
        threading.Thread(target=self.status_ctrl.pause).start()
        time.sleep(1)
        self.status_ctrl.pause()
        self.assertEqual(self.status_ctrl.status, Status.PAUSED)
        self.assertEqual(self.a, 2)

    def test_concurrent_pause_and_resume(self):
        def pause():
            self.status_ctrl.pause()
            self.a += 1
        threading.Thread(target=self._task, args=(3, )).start()
        time.sleep(1)
        threading.Thread(target=pause).start()
        time.sleep(1)   # make sure pause in progress first
        self.status_ctrl.ready()
        self.assertEqual(self.status_ctrl.status, Status.READY)
        self.assertEqual(self.a, 3)

    def test_concurrent_pause_and_terminate(self):
        def pause():
            self.status_ctrl.pause()
            self.a += 1
        threading.Thread(target=self._task, args=(3.5, )).start()
        time.sleep(1)
        threading.Thread(target=pause).start()
        time.sleep(1)   # make sure pause in progress first
        self.status_ctrl.terminate()
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.assertEqual(self.a, 3)

    def test_concurrent_resume_from_paused(self):
        def pause():
            self.status_ctrl.pause()
            self.a += 1

        def resume_should_succeed():
            self.status_ctrl.ready()
            self.assertEqual(self.status_ctrl.status, Status.READY)
            self.a += 1

        threading.Thread(target=self._task, args=(3, )).start()
        time.sleep(1)
        threading.Thread(target=pause).start()
        time.sleep(1)   # make sure pause in progress first
        threading.Thread(target=resume_should_succeed).start()
        threading.Thread(target=resume_should_succeed).start()
        time.sleep(2)
        self.assertEqual(self.a, 5)

    def test_concurrent_terminate(self):
        threading.Thread(target=self._task, args=(3, )).start()
        time.sleep(1)
        threading.Thread(target=self.status_ctrl.terminate).start()
        time.sleep(1)
        self.status_ctrl.terminate()
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.assertEqual(self.a, 2)

    def test_concurrent_resume_and_terminate(self):
        def pause():
            self.status_ctrl.pause()
            self.a += 1

        def resume():
            self.status_ctrl.ready()
            self.a += 1

        threading.Thread(target=self._task, args=(5, )).start()
        time.sleep(1)
        threading.Thread(target=pause).start()
        time.sleep(1)
        threading.Thread(target=resume).start()
        time.sleep(1)
        self.status_ctrl.terminate()
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.assertEqual(self.a, 4)

    def test_concurrent_terminate_and_pause(self):
        def pause_should_fail():
            self.assertRaises(StatusError, self.status_ctrl.pause)
            self.a += 1

        threading.Thread(target=self._task, args=(3, )).start()
        time.sleep(1)
        threading.Thread(target=self.status_ctrl.terminate).start()     # task has 2s
        time.sleep(1)
        threading.Thread(target=pause_should_fail).start()              # task has 1s
        time.sleep(2)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.assertEqual(self.a, 3)


if __name__ == '__main__':
    unittest.main()
