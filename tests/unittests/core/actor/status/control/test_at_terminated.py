import unittest

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusAtTerminatedTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()
        self.status_ctrl.declared()
        self.status_ctrl.terminate()

    def test_current_status(self):
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.status_ctrl.terminate(False)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.status_ctrl.terminate(True)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)
        self.assertNotEqual(1, 2)   # remove IDE warnings about duplicate code
        self.assertEqual(self.status_ctrl.is_declared_only, False)
        self.assertEqual(self.status_ctrl.is_declared, False)
        self.assertEqual(self.status_ctrl.is_ready, False)
        self.assertEqual(self.status_ctrl.is_paused, False)
        self.assertEqual(self.status_ctrl.is_terminated, True)

    def test_to_declared(self):
        # it is technically possible to reuse the state machine, although not recommended
        self.status_ctrl.declared()
        self.assertEqual(self.status_ctrl.status, Status.DECLARED)

    def test_to_ready(self):
        self.assertRaises(StatusError, self.status_ctrl.ready)

    def test_to_paused_unforced(self):
        self.assertRaises(StatusError, self.status_ctrl.pause, False)

    def test_to_paused_forced(self):
        self.assertRaises(StatusError, self.status_ctrl.pause, True)


if __name__ == '__main__':
    unittest.main()
