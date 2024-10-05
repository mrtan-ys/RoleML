import unittest

from roleml.core.status import Status, StatusError, StatusControl


class RoleStatusAtDeclaringTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.status_ctrl = StatusControl()

    def test_current_status(self):
        self.assertEqual(self.status_ctrl.status, Status.DECLARING)
        self.assertEqual(self.status_ctrl.is_declared_only, False)
        self.assertEqual(self.status_ctrl.is_declared, False)
        self.assertEqual(self.status_ctrl.is_ready, False)
        self.assertEqual(self.status_ctrl.is_paused, False)
        self.assertEqual(self.status_ctrl.is_terminated, False)

    def test_to_declared(self):
        self.status_ctrl.declared()
        self.assertEqual(self.status_ctrl.status, Status.DECLARED)

    def test_to_ready(self):
        self.assertRaises(StatusError, self.status_ctrl.ready)

    def test_to_paused(self):
        self.assertRaises(StatusError, self.status_ctrl.pause, False)
        self.assertRaises(StatusError, self.status_ctrl.pause, True)

    def test_to_terminated(self):
        self.status_ctrl.terminate()
        self.assertEqual(self.status_ctrl.status, Status.TERMINATED)


if __name__ == '__main__':
    unittest.main()
