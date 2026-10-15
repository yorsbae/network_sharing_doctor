import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from nsd.application import autostart as au
from nsd.application.monitor_service import MonitorService, SingleInstance, signature
from nsd.application.scan_service import ScanService
from nsd.models import Role, ScanRequest, TargetType
from nsd.security.allowlist import ValidationError
from nsd.storage.database import open_database
from nsd.storage.repositories import AuditRepository, CaseRepository
from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses


class NoMutationAdapter(FakeAdapter):
    def apply(self, *a, **k):
        raise AssertionError("monitor tidak boleh memanggil apply()")


class MonitorBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        self.conn = open_database(self.dir / "t.db")
        self.cases, self.audit = CaseRepository(self.conn), AuditRepository(self.conn)
        self.net = FakeNet()
        self.svc = ScanService(NoMutationAdapter(healthy_responses(), elevated=True), self.cases, self.audit, net=self.net)
        self.req = ScanRequest(Role.SERVER, TargetType.FOLDER, "localhost", "DATA")
        self.mon = MonitorService(self.svc, self.req, self.dir, self.audit, interval=30, confirm_ticks=2)

    def tearDown(self):
        self.conn.close(); self.tmp.cleanup()

    def events(self):
        return [e["event_type"] for e in self.audit.list()]

    def status(self):
        return json.loads((self.dir / "status.json").read_text(encoding="utf-8"))


class MonitorTests(MonitorBase):
    def test_baseline_saves_once_and_steady_state_saves_nothing(self):
        self.mon.tick()
        for _ in range(5): self.mon.tick()
        self.assertEqual(len(self.cases.list_cases()), 1)
        self.assertEqual(self.events().count("monitor_baseline"), 1)
        s = self.status()
        self.assertTrue(s["read_only"]); self.assertEqual(s["state"]["overall"], "tidak_ada_masalah_terbukti")
        self.assertEqual(s["ticks"], 6)
        self.assertNotIn("evidence", json.dumps(s))

    def test_single_blip_is_debounced(self):
        self.mon.tick()
        self.net.open_ports = set(); self.mon.tick()          # satu putaran gagal
        self.assertTrue(self.status()["state"]["pending_change"])
        self.net.open_ports = {445, 135}; self.mon.tick()     # pulih sebelum terkonfirmasi
        self.assertFalse(self.status()["state"]["pending_change"])
        self.assertEqual(len(self.cases.list_cases()), 1)
        self.assertNotIn("monitor_state_changed", self.events())

    def test_confirmed_failure_then_recovery(self):
        self.mon.tick()
        self.net.open_ports = set()
        self.mon.tick(); self.mon.tick()
        self.assertEqual(self.mon.state.overall, "masalah_ditemukan")
        self.assertEqual(len(self.cases.list_cases()), 2)      # bukti tersimpan saat berubah
        s = self.status()
        self.assertTrue(any(p["id"] == "net.tcp445" for p in s["problems"]))
        self.assertTrue(s["findings"])
        for _ in range(3): self.mon.tick()                     # tetap gagal: tidak menyimpan lagi
        self.assertEqual(len(self.cases.list_cases()), 2)
        self.net.open_ports = {445, 135}
        self.mon.tick(); self.mon.tick()
        self.assertEqual(self.mon.state.overall, "tidak_ada_masalah_terbukti")
        self.assertIn("monitor_recovered", self.events())
        ev = [e for e in self.audit.list() if e["event_type"] == "monitor_state_changed"][0]
        self.assertIn("net.tcp445:fail", ev["detail_json"])

    def test_interval_bounds(self):
        for bad in (0, 29, 86401):
            with self.assertRaises(ValueError):
                MonitorService(self.svc, self.req, self.dir, interval=bad)

    def test_loop_survives_errors_and_stops(self):
        stop = threading.Event()
        calls = {"n": 0}
        real = self.svc.run
        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1: raise RuntimeError("boom")
            return real(*a, **k)
        self.svc.run = flaky
        with mock.patch.object(stop, "wait", return_value=False):
            self.mon.run_forever(stop, max_ticks=3)
        self.assertGreaterEqual(self.mon.ticks, 2)
        ev = self.events()
        self.assertIn("monitor_started", ev); self.assertIn("monitor_error", ev); self.assertIn("monitor_stopped", ev)
        stop.set(); self.mon.run_forever(stop)                 # sudah di-stop: langsung keluar

    def test_signature_ignores_passing_checks(self):
        out = self.svc.run(self.req, persist=False)
        self.assertEqual(signature(out), ())
        self.assertEqual(out.case_id, "-")                     # persist=False tidak menyimpan
        self.assertEqual(self.cases.list_cases(), [])


class SingleInstanceTests(unittest.TestCase):
    def test_second_instance_refused_until_release(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = SingleInstance(Path(d) / "m.lock"), SingleInstance(Path(d) / "m.lock")
            self.assertTrue(a.acquire()); self.assertFalse(b.acquire())
            a.release(); self.assertTrue(b.acquire()); b.release()


ENV = {"ProgramFiles": r"C:\Program Files", "ProgramFiles(x86)": r"C:\Program Files (x86)",
       "SystemRoot": r"C:\Windows", "ProgramData": r"C:\ProgramData"}


class PathSafety(unittest.TestCase):
    def test_protected_paths(self):
        for p in (r"C:\Program Files\NSD\NSD.exe", r"c:\program files (x86)\NSD\NSD.exe", r"C:\Windows\System32\x.exe"):
            self.assertTrue(au.is_protected_path(p, ENV), p)

    def test_unprotected_and_tricks(self):
        for p in (r"C:\Users\kasir\Downloads\NSD.exe", r"D:\NSD\NSD.exe", r"C:\Program Files Evil\NSD.exe",
                  r"C:\Program Files\..\Users\kasir\NSD.exe", r"C:\Program FilesX\a.exe"):
            self.assertFalse(au.is_protected_path(p, ENV), p)


class CommandBuilding(unittest.TestCase):
    def test_command_and_validation(self):
        cmd = au.build_task_command(r"C:\Program Files\NSD\NSD.exe", host="localhost", share="Data Kantor",
                                    target_type="both", interval=300, data_dir=r"C:\ProgramData\NetworkSharingDoctor")
        self.assertTrue(cmd.startswith('"C:\\Program Files\\NSD\\NSD.exe" monitor --role server'))
        self.assertIn('--share "Data Kantor"', cmd); self.assertIn("--data-dir", cmd)
        for kw in ({"host": "a;b"}, {"share": 'x"y'}, {"interval": 5}, {"target_type": "evil"}):
            args = dict(host="localhost", share="d", target_type="both", interval=300, data_dir=None); args.update(kw)
            with self.assertRaises((ValidationError, ValueError)):
                au.build_task_command("C:\\a.exe", **args)
        with self.assertRaises(ValidationError):
            au.build_task_command('C:\\a".exe', host="h", share="", target_type="both", interval=300, data_dir=None)

    def test_modes(self):
        sysargs = au.build_create_args("boot-system", "cmd", ENV)
        self.assertIn("ONSTART", sysargs); self.assertIn("SYSTEM", sysargs)
        usr = au.build_create_args("logon-user", "cmd", ENV)
        self.assertIn("ONLOGON", usr); self.assertIn("LIMITED", usr); self.assertNotIn("SYSTEM", usr)
        with self.assertRaises(ValidationError):
            au.build_create_args("root", "cmd", ENV)


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on
    def __call__(self, args, **kw):
        self.calls.append((args, kw))
        r = mock.Mock(returncode=1 if self.fail_on and self.fail_on in args[0].lower() else 0, stdout="Status: Ready", stderr="gagal")
        return r


class InstallTests(unittest.TestCase):
    kw = dict(host="localhost", share="DATA", target_type="folder", interval=300, platform="win32", env=ENV)

    def test_refusals(self):
        r = FakeRunner()
        self.assertIn("Windows", au.install("logon-user", **{**self.kw, "platform": "linux"}, runner=r).message)
        self.assertIn("terpaket", au.install("logon-user", **self.kw, frozen=False, runner=r).message)
        self.assertIn("administrator", au.install("boot-system", **self.kw, frozen=True, elevated=False, exe=r"C:\Program Files\N\N.exe", runner=r).message)
        res = au.install("boot-system", **self.kw, frozen=True, elevated=True, exe=r"C:\Users\kasir\Downloads\NSD.exe", runner=r)
        self.assertFalse(res.ok); self.assertIn("eskalasi", res.message)
        self.assertFalse(au.install("boot-system", **{**self.kw, "host": "a;b"}, frozen=True, elevated=True, exe=r"C:\Program Files\N\N.exe", runner=r).ok)
        self.assertFalse(au.install("nope", **self.kw, frozen=True, runner=r).ok)
        self.assertEqual(r.calls, [])                          # tidak ada perintah dijalankan

    def test_logon_user_success_no_shell(self):
        r = FakeRunner()
        res = au.install("logon-user", **self.kw, frozen=True, exe=r"C:\Users\kasir\NSD\NSD.exe", runner=r)
        self.assertTrue(res.ok, res.message)
        self.assertEqual(len(r.calls), 1)                      # logon-user: tanpa icacls
        args, kw = r.calls[0]
        self.assertIsInstance(args, list); self.assertIs(kw["shell"], False)
        self.assertEqual(args[args.index("/TN") + 1], au.TASK_NAME)
        self.assertIn("ONLOGON", args)

    def test_boot_system_locks_acl_before_task(self):
        r = FakeRunner()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(au, "system_data_dir", return_value=d):
            res = au.install("boot-system", **self.kw, frozen=True, elevated=True, exe=r"C:\Program Files\NSD\NSD.exe", runner=r)
        self.assertTrue(res.ok, res.message)
        self.assertEqual(len(r.calls), 2)
        self.assertIn("icacls", r.calls[0][0][0].lower()); self.assertIn("/inheritance:r", r.calls[0][0])
        self.assertTrue(any("S-1-5-32-545" in a and "RX" in a for a in r.calls[0][0]))   # Users hanya baca
        self.assertIn("schtasks", r.calls[1][0][0].lower())

    def test_acl_failure_prevents_task_creation(self):
        r = FakeRunner(fail_on="icacls")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(au, "system_data_dir", return_value=d):
            res = au.install("boot-system", **self.kw, frozen=True, elevated=True, exe=r"C:\Program Files\NSD\NSD.exe", runner=r)
        self.assertFalse(res.ok); self.assertEqual(len(r.calls), 1)

    def test_uninstall_and_status(self):
        r = FakeRunner()
        self.assertTrue(au.uninstall(platform="win32", env=ENV, runner=r).ok)
        self.assertIn("/Delete", r.calls[0][0])
        self.assertIn("Ready", au.status(platform="win32", env=ENV, runner=r).message)
        self.assertFalse(au.status(platform="win32", env=ENV, runner=FakeRunner(fail_on="schtasks")).ok)


class CliMonitor(unittest.TestCase):
    def test_once_status_and_lock(self):
        from nsd.main import main
        with tempfile.TemporaryDirectory() as d:
            def run(*argv):
                buf = StringIO()
                with redirect_stdout(buf):
                    code = main(list(argv))
                return code, buf.getvalue()
            self.assertIn("Belum ada status", run("monitor", "--status", "--data-dir", d)[1])
            code, out = run("monitor", "--once", "--host", "localhost", "--type", "folder", "--share", "d", "--data-dir", d)
            self.assertIn(code, (0, 1)); self.assertIn("overall", out)
            self.assertTrue((Path(d) / "status.json").exists())
            self.assertIn('"read_only": true', run("monitor", "--status", "--data-dir", d)[1])
            lock = SingleInstance(Path(d) / "monitor.lock"); self.assertTrue(lock.acquire())
            self.assertEqual(run("monitor", "--once", "--data-dir", d)[0], 3)
            lock.release()
            self.assertEqual(run("monitor", "--interval", "5", "--data-dir", d)[0], 2)
            self.assertEqual(run("autostart", "status")[0], 1)       # Linux: tidak tersedia


if __name__ == "__main__":
    unittest.main()
