"""Uji pada Windows ASLI (VM). Dilewati otomatis di OS lain.

Jalankan di VM:  python -m unittest tests.integration_windows.test_real_windows -v
Tujuan: memvalidasi bahwa skrip PowerShell di windows/powershell.py benar-benar berjalan, keluarannya
JSON valid, dan tidak ada operasi yang mengubah sistem. Catat hasil di docs/test-matrix.md.
"""
import sys
import unittest

from nsd.windows.powershell import READ_OPERATIONS, RealWindowsAdapter, as_list

WIN = sys.platform == "win32"


@unittest.skipUnless(WIN, "hanya untuk Windows")
class RealReadOnlyOps(unittest.TestCase):
    def setUp(self):
        self.a = RealWindowsAdapter()

    def test_os_info(self):
        r = self.a.run("os_info")
        self.assertTrue(r.ok, r.error); self.assertIn("Build", r.data)

    def test_service_statuses(self):
        for svc in ("Spooler", "LanmanWorkstation", "LanmanServer"):
            r = self.a.run("get_service", service=svc)
            self.assertTrue(r.ok, f"{svc}: {r.error}")
            self.assertIn(r.data["Status"], {"Running", "Stopped", "StartPending", "StopPending", "Paused"})

    def test_net_profile_and_printers(self):
        for op in ("net_profile", "list_local_printers", "list_local_shares", "smb_client_config"):
            r = self.a.run(op); self.assertTrue(r.ok, f"{op}: {r.error}")
            as_list(r.data)

    def test_firewall_group_id_is_valid(self):
        """Memvalidasi ID grup '@FirewallAPI.dll,-32752'. Jika kosong, ID perlu dikoreksi."""
        r = self.a.run("firewall_sharing")
        self.assertTrue(r.ok, r.error)
        self.assertGreater(len(as_list(r.data)), 0, "Grup File and Printer Sharing tidak ditemukan; periksa ID grup.")

    def test_unc_of_missing_host_is_classified(self):
        r = self.a.run("test_unc", unc="\\\\nsd-host-tidak-ada\\data")
        self.assertTrue(r.ok or r.timed_out, r.error)
        if r.ok:
            self.assertFalse(r.data["Ok"])

    def test_every_operation_runs_or_reports_cleanly(self):
        samples = {"service": "Spooler", "host": "localhost", "unc": "\\\\localhost\\IPC$"}
        for name, spec in READ_OPERATIONS.items():
            params = {k: samples[k] for k in spec.params}
            r = self.a.run(name, **params)
            self.assertIsNotNone(r.ok, name)  # tidak boleh melempar


if __name__ == "__main__":
    unittest.main()


import os
import tempfile
from pathlib import Path

from nsd.repairs.executor import RepairExecutor, finding_for_rule
from nsd.rules.loader import load_rules
from nsd.storage.database import open_database
from nsd.storage.repositories import AuditRepository, CaseRepository, RepairRepository


@unittest.skipUnless(WIN and os.environ.get("NSD_RUN_MUTATING") == "1",
                     "MENGUBAH layanan Spooler. Hanya di VM LAB: set NSD_RUN_MUTATING=1 dan jalankan sebagai Administrator")
class RealRepairLab(unittest.TestCase):
    """Alur penuh PRN-SPOOLER-001 di Windows asli: hentikan Spooler → perbaiki → verifikasi → rollback → pulihkan."""

    def test_spooler_repair_and_rollback(self):
        a = RealWindowsAdapter(allow_mutation=True)
        if not a.is_elevated():
            self.skipTest("butuh Administrator")
        original = a.run("get_service", service="Spooler").data["Status"]
        try:
            self.assertTrue(a.apply("stop_service", service="Spooler").ok)
            with tempfile.TemporaryDirectory() as d:
                conn = open_database(Path(d) / "t.db")
                cases, repo, audit = CaseRepository(conn), RepairRepository(conn), AuditRepository(conn)
                cid = cases.create_case("client", "printer", "x\\y", "", "Win", True, "d")
                ex = RepairExecutor(a, repo, audit, True)
                f = finding_for_rule(load_rules().rules, "PRN-SPOOLER-001")
                res = ex.execute(f, cid, approved=True)
                self.assertEqual(res.outcome, "verified", res.message)
                self.assertEqual(a.run("get_service", service="Spooler").data["Status"], "Running")
                rb = ex.rollback(cid, res.action_id, approved=True)
                self.assertEqual(rb.outcome, "verified", rb.message)
                self.assertEqual(a.run("get_service", service="Spooler").data["Status"], "Stopped")
                conn.close()
        finally:   # kembalikan keadaan awal VM
            a.apply("start_service" if original == "Running" else "stop_service", service="Spooler")
