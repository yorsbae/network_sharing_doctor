import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nsd.application import launcher as L
from nsd.application.monitor_service import SingleInstance


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_argv_frozen_vs_source(self):
        kw = dict(host="localhost", share="DATA", target_type="both", interval=60)
        a = L.build_monitor_argv(frozen=True, exe="NSD.exe", **kw)
        self.assertEqual(a[:2], ["NSD.exe", "monitor"])
        b = L.build_monitor_argv(frozen=False, exe="py", **kw)
        self.assertEqual(b[:4], ["py", "-m", "nsd", "monitor"])
        self.assertIn("--share", b)

    def test_argv_rejects_bad_input(self):
        with self.assertRaises(Exception):
            L.build_monitor_argv(frozen=True, exe="x", host="a;calc", share="", target_type="both", interval=60)
        with self.assertRaises(ValueError):
            L.build_monitor_argv(frozen=True, exe="x", host="localhost", share="", target_type="both", interval=5)

    def test_monitor_spawned_detached_without_shell(self):
        spawn = mock.Mock()
        msg = L.start_monitor(self.dir, host="localhost", share="", target_type="both", interval=60,
                              frozen=True, exe="NSD.exe", platform="win32", spawn=spawn)
        self.assertIn("dinyalakan", msg)
        kw = spawn.call_args.kwargs
        self.assertIs(kw["shell"], False); self.assertEqual(kw["creationflags"], L._DETACHED)

    def test_monitor_not_spawned_twice(self):
        lock = SingleInstance(self.dir / "monitor.lock"); self.assertTrue(lock.acquire())
        spawn = mock.Mock()
        try:
            msg = L.start_monitor(self.dir, host="localhost", share="", target_type="both", interval=60, spawn=spawn)
        finally:
            lock.release()
        spawn.assert_not_called(); self.assertIn("sudah berjalan", msg)

    def test_autostart_skipped_when_not_frozen_or_not_windows(self):
        kw = dict(host="localhost", share="", target_type="both", interval=60)
        self.assertIn("dilewati", L.ensure_autostart(frozen=True, platform="linux", **kw))
        self.assertIn("dilewati", L.ensure_autostart(frozen=False, platform="win32", **kw))

    def test_autostart_idempotent_and_installs_logon_mode(self):
        kw = dict(frozen=True, platform="win32", host="localhost", share="", target_type="both", interval=60)
        with mock.patch.object(L.autostart, "status", return_value=L.autostart.Outcome(True, "ok")), \
             mock.patch.object(L.autostart, "install") as inst:
            self.assertIn("sudah terpasang", L.ensure_autostart(**kw)); inst.assert_not_called()
        with mock.patch.object(L.autostart, "status", return_value=L.autostart.Outcome(False, "no")), \
             mock.patch.object(L.autostart, "install", return_value=L.autostart.Outcome(True, "ok")) as inst:
            self.assertIn("dipasang", L.ensure_autostart(**kw))
            self.assertEqual(inst.call_args.args[0], "logon-user")

    def test_launch_runs_gui_once_and_second_instance_is_refused(self):
        spawn, gui = mock.Mock(), mock.Mock(return_value=0)
        rep = L.launch(self.dir, with_autostart=False, run_gui=gui, spawn=spawn, frozen=True, exe="NSD.exe", platform="linux")
        self.assertTrue(rep.gui_started); gui.assert_called_once(); spawn.assert_called_once()
        held = SingleInstance(self.dir / "gui.lock"); self.assertTrue(held.acquire())
        try:
            gui2 = mock.Mock()
            rep2 = L.launch(self.dir, with_autostart=False, with_monitor=False, run_gui=gui2)
        finally:
            held.release()
        gui2.assert_not_called(); self.assertFalse(rep2.gui_started)

    def test_headless_has_no_gui_and_bad_interval_does_not_crash(self):
        gui = mock.Mock()
        rep = L.launch(self.dir, with_gui=False, with_autostart=False, interval=1, run_gui=gui, spawn=mock.Mock())
        gui.assert_not_called(); self.assertEqual(rep.exit_code, 2)


if __name__ == "__main__":
    unittest.main()
