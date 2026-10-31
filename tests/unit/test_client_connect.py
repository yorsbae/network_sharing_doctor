"""Pasang printer di sisi client. Adapter palsu; BUKAN bukti di Windows asli."""
import unittest

from nsd.application.client_connect import connect_printer
from nsd.windows.powershell import USER_LEVEL_OPERATIONS, OpResult, RealWindowsAdapter
from tests.fixtures.fakes import FakeAdapter, ok


class A(FakeAdapter):
    def __init__(self, installs=True, apply_res=None):
        super().__init__({"list_local_printers": lambda: ok([{"Name": "\\\\SERVER01\\EPSON"}] if self.done else [])})
        self.done, self.installs, self.apply_res = False, installs, apply_res

    def apply(self, op, **p):
        self.calls.append((op, p))
        self.done = self.installs
        return self.apply_res or OpResult(True, data=[])


class ConnectTests(unittest.TestCase):
    def test_verified(self):
        self.assertEqual(connect_printer(A(), "SERVER01", "EPSON").outcome, "verified")

    def test_no_effect_is_unverified(self):
        self.assertEqual(connect_printer(A(installs=False), "SERVER01", "EPSON").outcome, "unverified")

    def test_failure_and_refusal(self):
        self.assertEqual(connect_printer(A(apply_res=OpResult(False, error="x")), "SERVER01", "EPSON").outcome, "failed")
        self.assertEqual(connect_printer(A(apply_res=OpResult(False, error="x", unsupported=True)), "S", "E").outcome, "refused")

    def test_bad_input_refused_before_any_call(self):
        a = A()
        self.assertEqual(connect_printer(a, "a;b", "EPSON").outcome, "refused")
        self.assertEqual(a.calls, [])

    def test_user_level_op_skips_admin_but_still_needs_mutation_flag(self):
        self.assertEqual(USER_LEVEL_OPERATIONS, {"add_printer_connection"})
        ad = RealWindowsAdapter(platform="win32", allow_mutation=False)
        self.assertIn("dinonaktifkan", ad.apply("add_printer_connection", unc="\\\\S\\E").error)
        self.assertIn("administrator", RealWindowsAdapter(platform="win32", allow_mutation=True).apply("start_service", service="Spooler").error
                      if not RealWindowsAdapter(platform="win32").is_elevated() else "administrator")


if __name__ == "__main__":
    unittest.main()
