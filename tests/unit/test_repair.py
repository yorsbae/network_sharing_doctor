import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from nsd.repairs.executor import RepairExecutor, finding_for_rule
from nsd.rules.loader import load_rules
from nsd.storage.database import open_database
from nsd.storage.repositories import AuditRepository, CaseRepository, RepairRepository
from nsd.windows.powershell import MUTATING_OPERATIONS, READ_OPERATIONS, RealWindowsAdapter
from tests.fixtures.fakes import FakeServiceAdapter

RULES = load_rules().rules
STOPPED = {"Spooler": {"Status": "Stopped", "StartType": "Automatic"}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = open_database(Path(self.tmp.name) / "t.db")
        self.cases, self.repo, self.audit = CaseRepository(self.conn), RepairRepository(self.conn), AuditRepository(self.conn)
        self.case = self.cases.create_case("client", "printer", "SRV\\EPSON", "", "Win", True, "d")

    def tearDown(self):
        self.conn.close(); self.tmp.cleanup()

    def ex(self, ad, enabled=True, **kw):
        return RepairExecutor(ad, self.repo, self.audit, enabled, sleep=lambda s: None, verify_timeout=kw.get("t", 0), poll_interval=0)

    def events(self):
        return [e["event_type"] for e in self.audit.list(self.case)]

    def finding(self, rid="PRN-SPOOLER-001"):
        return finding_for_rule(RULES, rid)


class Success(Base):
    def test_start_snapshot_verify_audit(self):
        ad = FakeServiceAdapter(STOPPED)
        res = self.ex(ad).execute(self.finding(), self.case, approved=True)
        self.assertEqual(res.outcome, "verified"); self.assertTrue(res.success); self.assertTrue(res.rollback_available)
        self.assertEqual(ad.applied, [("start_service", "Spooler")])
        snap = self.repo.snapshot_for_action(res.action_id)
        self.assertEqual(json.loads(snap["payload_json"])["Status"], "Stopped")
        self.assertEqual(self.repo.get_action(res.action_id)["success"], 1)
        self.assertEqual(self.repo.verifications(self.case)[0]["status"], "pass")
        self.assertEqual(self.events(), ["repair_started", "repair_verified"])

    def test_already_running_is_noop(self):
        ad = FakeServiceAdapter({"Spooler": {"Status": "Running", "StartType": "Automatic"}})
        res = self.ex(ad).execute(self.finding(), self.case, True)
        self.assertEqual(res.outcome, "noop"); self.assertEqual(ad.applied, [])
        self.assertEqual(self.repo.actions(self.case), [])

    def test_startup_type_change_is_flagged(self):
        res = self.ex(FakeServiceAdapter(STOPPED, change_startup=True)).execute(self.finding(), self.case, True)
        self.assertTrue(any("tipe startup berbeda" in s for s in res.steps))


class Refusals(Base):
    def refused(self, ad, finding=None, enabled=True, approved=True, fragment=""):
        res = self.ex(ad, enabled).execute(finding or self.finding(), self.case, approved)
        self.assertEqual(res.outcome, "refused", res.message)
        self.assertIn(fragment, res.message)
        self.assertEqual(ad.applied, [])
        self.assertEqual(self.repo.actions(self.case), [])
        self.assertIn("repair_refused", self.events())

    def test_disabled(self): self.refused(FakeServiceAdapter(STOPPED), enabled=False, fragment="belum diaktifkan")
    def test_not_approved(self): self.refused(FakeServiceAdapter(STOPPED), approved=False, fragment="persetujuan")
    def test_not_elevated(self): self.refused(FakeServiceAdapter(STOPPED, elevated=False), fragment="administrator")
    def test_blocked_rule(self): self.refused(FakeServiceAdapter(STOPPED), self.finding("SEC-SMB1-001"), fragment="blocked")
    def test_advice_only_rule(self): self.refused(FakeServiceAdapter(STOPPED), self.finding("NET-NAME-001"), fragment="")
    def test_medium_risk_stopped_by_policy_gate(self):
        self.refused(FakeServiceAdapter(STOPPED), self.finding("FW-SHARING-001"), fragment="Kebijakan")
        self.refused(FakeServiceAdapter(STOPPED), self.finding("PRN-SHARE-001"), fragment="Kebijakan")

    def test_unsupported_operation_even_if_low_risk(self):
        f = self.finding(); f.actions = [{"operation": "set_network_profile_private"}]
        self.refused(FakeServiceAdapter(STOPPED), f, fragment="belum didukung")

    def test_unreadable_state_changes_nothing(self):
        ad = FakeServiceAdapter(STOPPED); ad.reads_ok = False
        self.refused(ad, fragment="tidak terbaca")

    def test_snapshot_failure_blocks_apply(self):
        ad = FakeServiceAdapter(STOPPED)
        with mock.patch.object(self.repo, "add_snapshot", side_effect=RuntimeError("disk penuh")):
            self.refused(ad, fragment="Snapshot gagal")

    def test_tampered_service_name_refused(self):
        f = self.finding(); f.actions = [{"operation": "start_service", "service_name": "WinDefend"}]
        self.refused(FakeServiceAdapter({"WinDefend": {"Status": "Stopped", "StartType": "Automatic"}}), f, fragment="tidak valid")

    def test_two_actions_refused(self):
        f = self.finding(); f.actions = f.actions * 2
        self.refused(FakeServiceAdapter(STOPPED), f, fragment="satu aksi")

    def test_finding_comes_from_rules_not_db(self):
        self.assertIsNone(finding_for_rule(RULES, "XXX-YYY-999"))


class HonestFailures(Base):
    def test_start_fails_disabled_service(self):
        ad = FakeServiceAdapter({"Spooler": {"Status": "Stopped", "StartType": "Disabled"}}, start_fails="Cannot start service")
        res = self.ex(ad).execute(self.finding(), self.case, True)
        self.assertEqual(res.outcome, "failed"); self.assertFalse(res.success)
        self.assertIn("Disabled", res.message)
        self.assertEqual(self.repo.get_action(res.action_id)["success"], 0)
        self.assertEqual(self.repo.verifications(self.case), [])
        self.assertIn("repair_failed", self.events())

    def test_sent_but_not_running_is_not_success(self):
        res = self.ex(FakeServiceAdapter(STOPPED, stays_stopped=True)).execute(self.finding(), self.case, True)
        self.assertEqual(res.outcome, "applied_unverified"); self.assertFalse(res.success)
        self.assertIn("Jangan menganggap", res.message)
        self.assertEqual(self.repo.verifications(self.case)[0]["status"], "fail")


class Rollback(Base):
    def run_repair(self, ad):
        return self.ex(ad).execute(self.finding(), self.case, True)

    def test_rollback_restores_stopped(self):
        ad = FakeServiceAdapter(STOPPED); res = self.run_repair(ad)
        rb = self.ex(ad).rollback(self.case, res.action_id, True)
        self.assertEqual(rb.outcome, "verified"); self.assertEqual(ad.states["Spooler"]["Status"], "Stopped")
        self.assertEqual(ad.applied[-1], ("stop_service", "Spooler"))
        self.assertIn("rollback_verified", self.events())

    def test_rollback_requires_approval_enabled_admin(self):
        ad = FakeServiceAdapter(STOPPED); res = self.run_repair(ad); n = len(ad.applied)
        self.assertEqual(self.ex(ad).rollback(self.case, res.action_id, False).outcome, "refused")
        self.assertEqual(self.ex(ad, enabled=False).rollback(self.case, res.action_id, True).outcome, "refused")
        ad.elevated = False
        self.assertEqual(self.ex(ad).rollback(self.case, res.action_id, True).outcome, "refused")
        self.assertEqual(len(ad.applied), n)

    def test_rollback_wrong_case_or_action(self):
        ad = FakeServiceAdapter(STOPPED); res = self.run_repair(ad); n = len(ad.applied)
        self.assertEqual(self.ex(ad).rollback("lain", res.action_id, True).outcome, "refused")
        self.assertEqual(self.ex(ad).rollback(self.case, 9999, True).outcome, "refused")
        self.assertEqual(len(ad.applied), n)

    def test_rollback_noop_when_already_stopped(self):
        ad = FakeServiceAdapter(STOPPED); res = self.run_repair(ad)
        ad.states["Spooler"]["Status"] = "Stopped"; n = len(ad.applied)
        self.assertEqual(self.ex(ad).rollback(self.case, res.action_id, True).outcome, "noop")
        self.assertEqual(len(ad.applied), n)

    def test_snapshot_not_restorable_when_initial_not_stopped(self):
        ad = FakeServiceAdapter({"Spooler": {"Status": "Paused", "StartType": "Automatic"}})
        res = self.run_repair(ad)
        self.assertFalse(res.rollback_available)
        self.assertEqual(self.ex(ad).rollback(self.case, res.action_id, True).outcome, "refused")


class RealAdapterGuards(unittest.TestCase):
    def proc(self):
        m = mock.Mock(); m.stdout, m.stderr, m.returncode = b'{"Status":"Running"}', b"", 0
        return m

    def test_mutating_ops_are_minimal_and_separate(self):
        self.assertEqual(set(MUTATING_OPERATIONS), {"start_service", "stop_service", "set_network_private",
                                                    "enable_sharing_firewall", "share_printer", "add_printer_connection"})
        self.assertFalse(set(MUTATING_OPERATIONS) & set(READ_OPERATIONS))
        for spec in MUTATING_OPERATIONS.values():
            self.assertNotIn("-Force", spec.script)
            self.assertNotIn("Set-Service", spec.script)   # tipe startup tidak diubah
            self.assertNotIn("Disable-NetFirewall", spec.script)   # firewall tidak pernah dimatikan
            self.assertNotIn("Set-NetFirewallProfile", spec.script)

    def test_run_cannot_mutate(self):
        a = RealWindowsAdapter(platform="win32", allow_mutation=True)
        with mock.patch("nsd.windows.powershell.subprocess.run") as run:
            self.assertTrue(a.run("start_service", service="Spooler").unsupported)
            run.assert_not_called()

    def test_apply_gated(self):
        with mock.patch("nsd.windows.powershell.subprocess.run", return_value=self.proc()) as run:
            self.assertIn("dinonaktifkan", RealWindowsAdapter(platform="win32").apply("start_service", service="Spooler").error)
            a = RealWindowsAdapter(platform="win32", allow_mutation=True)
            with mock.patch.object(a, "is_elevated", return_value=False):
                self.assertIn("administrator", a.apply("start_service", service="Spooler").error)
            self.assertIn("tidak diizinkan", a.apply("Remove-Item").error)
            run.assert_not_called()
            with mock.patch.object(a, "is_elevated", return_value=True):
                self.assertTrue(a.apply("start_service", service="Spooler").ok)
            args, kw = run.call_args
            self.assertIs(kw["shell"], False); self.assertEqual(kw["env"]["NSD_P_SERVICE"], "Spooler")
            self.assertNotIn("Spooler", " ".join(args[0]))

    def test_apply_rejects_injection(self):
        from nsd.security.allowlist import ValidationError
        a = RealWindowsAdapter(platform="win32", allow_mutation=True)
        with mock.patch.object(a, "is_elevated", return_value=True), mock.patch("nsd.windows.powershell.subprocess.run") as run:
            for bad in ("Spooler; calc", "WinDefend", ""):
                with self.assertRaises(ValidationError):
                    a.apply("start_service", service=bad)
            run.assert_not_called()


class CliRepair(unittest.TestCase):
    def test_plan_then_refusal_on_non_windows_then_setting(self):
        from nsd.bootstrap import bootstrap
        from nsd.main import main
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"NSD_DATA_DIR": d}):
            ctx = bootstrap(Path(d))
            cid = ctx.cases.create_case("client", "printer", "SRV\\EPSON", "", "Win", False, "x")
            f = finding_for_rule(RULES, "PRN-SPOOLER-001")
            ctx.cases.finish_case(cid, "masalah_ditemukan", [], [f])
            def run(*argv):
                buf = StringIO()
                with redirect_stdout(buf):
                    code = main(list(argv))
                return code, buf.getvalue()
            code, out = run("repair", "--case", cid, "--rule", "PRN-SPOOLER-001")
            self.assertEqual(code, 0); self.assertIn("Belum ada perubahan", out); self.assertIn("start_service", out)
            code, out = run("repair", "--case", cid, "--rule", "PRN-SPOOLER-001", "--confirm")
            self.assertEqual(code, 1); self.assertIn("belum diaktifkan", out)
            code, out = run("settings", "--set", "execution_enabled=true")
            self.assertIn("PERINGATAN", out)
            code, out = run("repair", "--case", cid, "--rule", "PRN-SPOOLER-001", "--confirm")
            self.assertEqual(code, 1); self.assertIn("refused", out)       # Linux: layanan tak terbaca → tak ada perubahan
            self.assertEqual(run("settings", "--set", "policy_level=3")[0], 2)  # terkunci
            self.assertEqual(run("repair", "--case", "nope", "--rule", "PRN-SPOOLER-001")[0], 2)


if __name__ == "__main__":
    unittest.main()


class RescanAfterRepair(unittest.TestCase):
    def _run(self, spooler_state):
        from nsd.application.scan_service import ScanService
        from nsd.main import _rescan
        from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses, svc
        resp = healthy_responses()
        resp["get_service"] = lambda service: svc(service, spooler_state if service == "Spooler" else "Running")
        seen = {}
        class Ctx:
            def scan_service(self_inner):
                s = ScanService(FakeAdapter(resp, True), net=FakeNet())
                orig = s.run
                s.run = lambda req, *a, **k: (seen.setdefault("req", req), orig(req, *a, **k))[1]
                return s
        row = {"target": "SRV-KANTOR\\EPSON", "role": "client", "target_type": "printer", "error_code": ""}
        buf = StringIO()
        with redirect_stdout(buf):
            _rescan(Ctx(), row, "PRN-SPOOLER-001")
        return seen["req"], buf.getvalue()

    def test_resolved_vs_still_present(self):
        req, out = self._run("Running")
        self.assertEqual((req.host, req.share), ("SRV-KANTOR", "EPSON"))
        self.assertIn("tidak lagi terdeteksi", out)
        _, out = self._run("Stopped")
        self.assertIn("MASIH terdeteksi", out)
        self.assertIn("tetap diperlukan", out)
