import unittest

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusAtDeclaredTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()
        self.status_ctrl.declared()

    def test_current_status(self):
        self.assertEqual(self.status_ctrl.status, Status.DECLARED)
        self.status_ctrl.declared()
        self.assertEqual(self.status_ctrl.status, Status.DECLARED)
        self.assertEqual(self.status_ctrl.is_declared_only, True)
        self.assertEqual(self.status_ctrl.is_declared, True)
        self.assertEqual(self.status_ctrl.is_ready, False)
        self.assertEqual(self.status_ctrl.is_paused, False)
        self.assertEqual(self.status_ctrl.is_terminated, False)

    def test_to_ready(self):
        self.status_ctrl.ready()
        self.assertEqual(self.status_ctrl.status, Status.READY)

    def test_to_paused_unforced(self):
        self.assertRaises(StatusError, self.status_ctrl.pause, False)

    def test_to_paused_forced(self):
        self.assertRaises(StatusError, self.status_ctrl.pause, True)

    def test_to_terminated_unforced(self):
        self.status_ctrl.terminate(force=False)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)

    def test_to_terminated_forced(self):
        self.status_ctrl.terminate(force=True)
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)


if __name__ == '__main__':
    unittest.main()
