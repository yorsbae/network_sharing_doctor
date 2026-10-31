"""Log aktivitas server (koneksi + cetak), kendali server, dan autostart `serve`. Adapter palsu; BUKAN bukti di Windows asli."""
import tempfile
import threading
import unittest
from pathlib import Path

from nsd.application import autostart, server_control
from nsd.application.activity_service import ActivityWatcher, describe, read_events
from nsd.application.monitor_service import SingleInstance
from nsd.windows.powershell import OpResult
from tests.fixtures.fakes import FakeAdapter, ok

JOB = {"Id": 7, "Document": "faktur.pdf", "Printer": "EPSON", "Status": "Normal", "Pages": 2, "Owner": "budi", "Client": "PC-KASIR"}


class Dyn(FakeAdapter):
    """Adapter yang isinya bisa diganti antar putaran."""
    def __init__(self):
        super().__init__()
        self.sessions, self.jobs, self.admin = [], [], True

    def run(self, operation, **params):
        self.calls.append((operation, params))
        if operation == "list_smb_sessions":
            return ok(self.sessions) if self.admin else OpResult(False, error="Access denied")
        if operation == "list_smb_connections":
            return ok(self.sessions)
        if operation == "list_print_jobs":
            return ok(self.jobs)
        return OpResult(False, error="x", unsupported=True)


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.ad = Dyn()
        self.w = ActivityWatcher(self.ad, self.d)

    def kinds(self):
        return [e["kind"] for e in read_events(self.d)]

    def test_connect_disconnect(self):
        self.w.tick()                                           # baseline kosong
        self.ad.sessions = [{"Client": "PC-KASIR", "User": "budi", "Opens": 1}]
        self.w.tick()
        self.w.tick()                                           # tidak berubah: tidak ada peristiwa baru
        self.ad.sessions = []
        self.w.tick()
        self.assertEqual(self.kinds(), ["connect", "disconnect"])
        self.assertIn("PC-KASIR", describe(read_events(self.d)[0]))

    def test_loopback_ignored(self):
        self.ad.sessions = [{"Client": "127.0.0.1"}, {"Client": "::1"}]
        self.w.tick()
        self.assertEqual(self.kinds(), [])

    def test_print_job_lifecycle(self):
        self.w.tick()
        self.ad.jobs = [dict(JOB)]
        self.w.tick()
        self.ad.jobs = [dict(JOB, Status="Printing")]
        self.w.tick()
        self.ad.jobs = []
        self.w.tick()
        self.assertEqual(self.kinds(), ["job_new", "job_progress", "job_done"])
        self.assertIn("faktur.pdf", describe(read_events(self.d)[0]))

    def test_job_error_status(self):
        self.ad.jobs = [dict(JOB)]
        self.w.tick()
        self.ad.jobs = [dict(JOB, Status="Error, PaperOut")]
        self.w.tick()
        self.assertEqual(self.kinds()[-1], "job_error")

    def test_without_admin_falls_back_and_warns_once(self):
        self.ad.admin = False
        self.ad.sessions = [{"Client": "192.168.1.20"}]
        self.w.tick()
        self.w.tick()
        self.assertEqual(self.kinds().count("warn"), 1)
        self.assertIn("connect", self.kinds())

    def test_read_failure_does_not_crash(self):
        class Bad(FakeAdapter):
            pass
        w = ActivityWatcher(Bad(), self.d)
        w.tick()
        self.assertTrue(all(k == "warn" for k in self.kinds()))

    def test_corrupt_log_lines_skipped_and_rotation(self):
        (self.d / "activity.jsonl").write_text('bukan json\n{"ts":"2026-01-01 00:00:00","kind":"connect","client":"A"}\n', encoding="utf-8")
        self.assertEqual(len(read_events(self.d)), 1)
        import nsd.application.activity_service as a
        old, a.MAX_LOG_BYTES = a.MAX_LOG_BYTES, 10
        self.addCleanup(setattr, a, "MAX_LOG_BYTES", old)
        self.w.emit("warn", message="x")
        self.assertTrue((self.d / "activity.jsonl.1").exists())


class ServerControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def test_argv_frozen_and_script(self):
        a = server_control.build_serve_argv(frozen=True, exe="NSD.exe", share="EPSON")
        self.assertEqual(a[:2], ["NSD.exe", "serve"])
        self.assertIn("EPSON", a)
        self.assertEqual(server_control.build_serve_argv(frozen=False, exe="py")[:3], ["py", "-m", "nsd"])

    def test_argv_rejects_bad_input(self):
        for kw in ({"host": "a;b"}, {"interval": 1}, {"poll": 0}, {"target_type": "x"}, {"share": "a;b"}):
            with self.assertRaises(ValueError):
                server_control.build_serve_argv(frozen=True, exe="x", **kw)

    def test_start_spawns_once_without_shell(self):
        calls = []
        msg = server_control.start(self.d, frozen=True, exe="NSD.exe", platform="linux", spawn=lambda *a, **k: calls.append((a, k)))
        self.assertIn("dijalankan", msg)
        (argv,), kw = calls[0]
        self.assertFalse(kw["shell"])
        self.assertEqual(kw["env"]["NSD_DATA_DIR"], str(self.d))
        lock = SingleInstance(self.d / "server.lock")
        self.assertTrue(lock.acquire())
        self.assertEqual(server_control.start(self.d, frozen=True, exe="x", spawn=lambda *a, **k: calls.append(1)), "Server sudah berjalan.")
        self.assertEqual(len(calls), 1)
        lock.release()

    def test_run_serve_logs_start_stop_and_status(self):
        w = ActivityWatcher(Dyn(), self.d)
        self.assertEqual(server_control.run_serve(self.d, w, None, poll=1, max_ticks=2, stop_event=threading.Event()), 0)
        kinds = [e["kind"] for e in read_events(self.d)]
        self.assertEqual((kinds[0], kinds[-1]), ("server_start", "server_stop"))
        self.assertFalse(server_control.read_status(self.d)["running"])
        self.assertFalse(server_control.is_running(self.d))

    def test_stop_file_ends_loop(self):
        w = ActivityWatcher(Dyn(), self.d)
        ev = threading.Event()
        t = threading.Thread(target=server_control.run_serve, args=(self.d, w, None), kwargs={"poll": 1, "stop_event": ev})
        t.start()
        for _ in range(50):
            if server_control.is_running(self.d):
                break
            threading.Event().wait(0.05)
        self.assertTrue(server_control.is_running(self.d))
        server_control.stop(self.d)
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertFalse(server_control.is_running(self.d))

    def test_second_server_refused(self):
        lock = SingleInstance(self.d / "server.lock")
        self.assertTrue(lock.acquire())
        self.addCleanup(lock.release)
        self.assertEqual(server_control.run_serve(self.d, ActivityWatcher(Dyn(), self.d), None, max_ticks=1), 3)


class AutostartServeTests(unittest.TestCase):
    def test_task_serve_in_command(self):
        cmd = autostart.build_task_command("C:\\NSD.exe", host="localhost", share="", target_type="printer", interval=300,
                                           data_dir=None, task="serve")
        self.assertIn('"C:\\NSD.exe" serve --role server', cmd)

    def test_default_task_unchanged_and_bad_rejected(self):
        self.assertIn(" monitor ", autostart.build_task_command("x", host="localhost", share="", target_type="both", interval=300, data_dir=None))
        with self.assertRaises(Exception):
            autostart.build_task_command("x", host="localhost", share="", target_type="both", interval=300, data_dir=None, task="rm")


if __name__ == "__main__":
    unittest.main()
