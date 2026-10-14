import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from nsd.application.policy_service import PolicyLevel, decide
from nsd.application.report_service import build_json, build_text
from nsd.application.scan_service import ScanService
from nsd.models import Finding, Role, ScanRequest, TargetType
from nsd.storage.database import DatabaseCorrupt, open_database
from nsd.storage.repositories import AuditRepository, CaseRepository, SettingsRepository
from nsd.app_config import DEFAULT_SETTINGS
from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses


def finding(**kw):
    base = dict(rule_id="X-Y-001", version=1, title="t", explanation="e", confidence="sedang", risk="low",
                auto_policy="auto_if_approved", requires_admin=True,
                actions=[{"operation": "start_service", "service_name": "Spooler"}], verification=["v"],
                rollback={"type": "r"}, escalation="x", matched_conditions=[], matched_error_code=False)
    base.update(kw)
    return Finding(**base)


class PolicyTests(unittest.TestCase):
    def test_nothing_executes_at_any_level_in_phase1(self):
        for lvl in PolicyLevel:
            self.assertEqual(decide(finding(), lvl)[0], "suggest_only")

    def test_blocked_and_high_risk(self):
        for lvl in PolicyLevel:
            self.assertEqual(decide(finding(auto_policy="blocked"), lvl)[0], "blocked")
            self.assertEqual(decide(finding(risk="high", auto_policy="requires_confirmation"), lvl)[0], "blocked")
            self.assertEqual(decide(finding(risk="security_sensitive"), lvl)[0], "blocked")

    def test_advise_only_is_read_only(self):
        f = finding(actions=[{"operation": "advise", "text": "x"}], risk="read_only", auto_policy="always_read_only")
        self.assertEqual(decide(f, PolicyLevel.ADVANCED_APPROVED)[0], "read_only")

    def test_future_levels_when_execution_enabled(self):
        with mock.patch("nsd.application.policy_service.EXECUTION_AVAILABLE", True):
            self.assertEqual(decide(finding(), PolicyLevel.DIAGNOSE_ONLY)[0], "suggest_only")
            self.assertEqual(decide(finding(), PolicyLevel.SAFE_AUTO)[0], "needs_confirmation")
            self.assertEqual(decide(finding(risk="medium"), PolicyLevel.SAFE_AUTO)[0], "suggest_only")
            self.assertEqual(decide(finding(risk="medium"), PolicyLevel.ADVANCED_APPROVED)[0], "needs_confirmation")
            self.assertEqual(decide(finding(auto_policy="blocked"), PolicyLevel.ADVANCED_APPROVED)[0], "blocked")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def _scan(self, conn, **kw):
        ad = FakeAdapter(healthy_responses(), elevated=True)
        svc = ScanService(ad, CaseRepository(conn), AuditRepository(conn), net=FakeNet(**kw))
        return svc.run(ScanRequest(Role.CLIENT, TargetType.FOLDER, "SRV", "DATA", "password=abc123 0x80070035"))

    def test_roundtrip_and_audit(self):
        conn = open_database(self.dir / "t.db")
        out = self._scan(conn, resolve_error=True)
        repo = CaseRepository(conn)
        row = repo.list_cases()[0]
        self.assertEqual(row["id"], out.case_id); self.assertEqual(row["status"], "masalah_ditemukan")
        self.assertEqual(len(repo.get_checks(out.case_id)), len(out.checks))
        self.assertTrue(repo.get_plans(out.case_id))
        ev = AuditRepository(conn).list(out.case_id)
        self.assertEqual(ev[0]["event_type"], "scan_completed"); self.assertEqual(ev[0]["policy_decision"], "read_only")
        dump = json.dumps([dict(r) for r in repo.get_checks(out.case_id)])
        self.assertNotIn("abc123", dump)

    def test_prune_and_clear(self):
        conn = open_database(self.dir / "t.db"); repo = CaseRepository(conn)
        for _ in range(3): self._scan(conn)
        conn.execute("UPDATE cases SET started_at='2000-01-01T00:00:00Z' WHERE rowid=1"); conn.commit()
        self.assertEqual(repo.prune(180, 500), 1)
        self.assertEqual(len(repo.list_cases()), 2)
        self.assertEqual(repo.prune(180, 1), 1)
        self.assertEqual(len(repo.list_cases()), 1)
        repo.clear_history()
        self.assertEqual(repo.list_cases(), [])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM diagnostic_checks").fetchone()[0], 0)  # cascade

    def test_settings(self):
        conn = open_database(self.dir / "t.db"); s = SettingsRepository(conn, DEFAULT_SETTINGS)
        self.assertEqual(s.get("retention_days"), 180)
        s.set("retention_days", 30); self.assertEqual(s.get("retention_days"), 30)
        with self.assertRaises(KeyError): s.set("sembarang", 1)

    def test_corrupt_db_is_quarantined_not_deleted(self):
        p = self.dir / "t.db"; p.write_bytes(b"ini bukan sqlite" * 100)
        conn = open_database(p)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0], 0)
        self.assertEqual(len(list(self.dir.glob("t.db.corrupt-*"))), 1)

    def test_newer_schema_refused(self):
        p = self.dir / "t.db"; c = sqlite3.connect(p); c.execute("PRAGMA user_version=99"); c.commit(); c.close()
        with self.assertRaises(DatabaseCorrupt): open_database(p)
        self.assertTrue(p.exists())

    def test_reopen_is_idempotent(self):
        p = self.dir / "t.db"; open_database(p).close()
        conn = open_database(p)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)


class ReportTests(unittest.TestCase):
    def setUp(self):
        resp = healthy_responses()
        resp["test_unc"] = FakeAdapter and __import__("tests.fixtures.fakes", fromlist=["ok"]).ok(
            {"Ok": False, "ErrorType": "UnauthorizedAccessException", "HResult": -2147024891, "Message": "denied"})
        self.out = ScanService(FakeAdapter(resp, elevated=True), net=FakeNet()).run(
            ScanRequest(Role.CLIENT, TargetType.FOLDER, "SRV-KANTOR", "KEUANGAN", "gagal password=Rahasia1 0x80070005"))

    def test_text_redacted_by_default(self):
        t = build_text(self.out)
        for secret in ("SRV-KANTOR", "KEUANGAN", "192.168.1.10", "Rahasia1"):
            self.assertNotIn(secret.lower(), t.lower(), secret)
        self.assertIn("BACA-SAJA", t); self.assertIn("Tidak ada perubahan", t)
        self.assertIn("[GAGAL]", t); self.assertIn("FLD-ACCESS-001", t)

    def test_text_unredacted_still_hides_passwords_in_error_text_only_when_redacting(self):
        raw = build_text(self.out, redact=False)
        self.assertIn("SRV-KANTOR", raw)

    def test_json_valid_and_redacted(self):
        doc = json.loads(build_json(self.out))
        self.assertTrue(doc["read_only"]); self.assertEqual(doc["overall"], "masalah_ditemukan")
        self.assertNotIn("srv-kantor", json.dumps(doc).lower())
        self.assertEqual(doc["findings"][0]["rule_id"], "FLD-ACCESS-001")

    def test_statuses_have_text_tags_not_only_color(self):
        t = build_text(self.out)
        for tag in ("[GAGAL]", "[LULUS]"): self.assertIn(tag, t)


class CliTests(unittest.TestCase):
    def test_rules_validate_and_bad_scan(self):
        from nsd.main import main
        buf = StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["rules-validate"]), 0)
        self.assertIn("aturan valid", buf.getvalue())
        buf = StringIO()
        with redirect_stdout(buf):
            code = main(["scan", "--host", "bad host;x", "--share", "d", "--no-save"])
        self.assertEqual(code, 1)
        self.assertIn("[GAGAL] target.input", buf.getvalue())

    def test_cli_history_and_save(self):
        from nsd.main import main
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"NSD_DATA_DIR": d}):
            with redirect_stdout(StringIO()):
                main(["scan", "--host", "localhost", "--share", "d", "--type", "folder"])
            buf = StringIO()
            with redirect_stdout(buf):
                main(["history"])
            self.assertIn("localhost", buf.getvalue())
            with redirect_stdout(StringIO()):
                main(["clear-history"])
            buf = StringIO()
            with redirect_stdout(buf):
                main(["history"])
            self.assertIn("Belum ada riwayat", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
