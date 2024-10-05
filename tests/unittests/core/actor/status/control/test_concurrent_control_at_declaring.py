import threading
import time
import unittest

from roleml.core.status import Status, StatusControl


class RoleStatusConcurrentControlAtDeclaringTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()

    def test_concurrent_declaration_no_locking(self):
        a = 1

        def t1():
            nonlocal a
            time.sleep(1)
            if self.status_ctrl.status == Status.DECLARING:
                a += 1
                self.status_ctrl.declared()

        def t2():
            nonlocal a
            time.sleep(2)
            if self.status_ctrl.status == Status.DECLARING:
                a += 1
                self.status_ctrl.declared()

        threading.Thread(target=t1).start()
        threading.Thread(target=t2).start()
        time.sleep(3)
        self.assertNotEqual(a, 1)
        self.assertNotEqual(a, 3)

    def test_concurrent_declaration_with_locking(self):
        a = 1

        def t1():
            nonlocal a
            with self.status_ctrl.lock_status_for_execute(Status.DECLARING):
                time.sleep(1)
                a += 1

        def t2():
            nonlocal a
            a += 1
            time.sleep(2)
            self.status_ctrl.declared()

        threading.Thread(target=t1).start()
        threading.Thread(target=t2).start()
        time.sleep(3)
        self.assertEqual(a, 3)


if __name__ == '__main__':
    unittest.main()
