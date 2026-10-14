import unittest
from unittest import mock

from nsd.security.allowlist import (ValidationError, build_unc, validate_action, validate_host,
                                    validate_service, validate_share, validate_unc)
from nsd.security.redaction import Redactor, redact_secrets
from nsd.windows.powershell import RealWindowsAdapter, READ_OPERATIONS


class ValidationTests(unittest.TestCase):
    def test_hosts_ok(self):
        for h in ("SERVER01", "srv-kantor.local", "192.168.1.10", "fe80::1", "a.b.c"):
            self.assertEqual(validate_host(h), h)

    def test_hosts_rejected(self):
        for h in ("", "srv;calc", "srv name", "$(whoami)", "srv`id`", "a|b", "srv\\x", "-bad-.com",
                  "x" * 300, "fe80::1%eth0", "srv&dir", "'; Remove-Item *"):
            with self.assertRaises(ValidationError, msg=h):
                validate_host(h)

    def test_shares(self):
        self.assertEqual(validate_share("Keuangan 2026"), "Keuangan 2026")
        self.assertEqual(validate_share("C$"), "C$")
        for s in ("", "a/b", "a\\b", "a:b", 'a"b', "a|b", "a*", "a\nb", "x" * 81, "dot.", "a;b", "a'b", "a`b", "a$b", "a&b", "a%b"):
            with self.assertRaises(ValidationError, msg=repr(s)):
                validate_share(s)

    def test_unc(self):
        self.assertEqual(build_unc("srv", "data"), "\\\\srv\\data")
        self.assertEqual(validate_unc("\\\\srv\\data"), "\\\\srv\\data")
        for u in ("srv\\data", "\\\\srv", "\\\\srv\\data\\sub", "\\\\srv;x\\data"):
            with self.assertRaises(ValidationError, msg=u):
                validate_unc(u)

    def test_services(self):
        self.assertEqual(validate_service("Spooler"), "Spooler")
        for s in ("spooler2", "WinDefend", "Spooler; calc", ""):
            with self.assertRaises(ValidationError):
                validate_service(s)

    def test_action_validation(self):
        self.assertEqual(validate_action({"operation": "start_service", "service_name": "Spooler"}), [])
        self.assertTrue(validate_action({"operation": "start_service", "service_name": "WinDefend"}))
        self.assertTrue(validate_action({"operation": "disable_firewall"}))
        self.assertIn("terlarang", validate_action({"operation": "enable_smb1"})[0])
        self.assertTrue(validate_action({"operation": "run_powershell", "script": "calc"}))
        self.assertTrue(validate_action({"operation": "start_service", "service_name": "Spooler", "extra": "x"}))
        self.assertTrue(validate_action({"operation": "start_service"}))


class RedactionTests(unittest.TestCase):
    def test_hostnames_ips_unc(self):
        r = Redactor(include_local_identity=False)
        r.add("HOST", "SRV-KANTOR"); r.add("SHARE", "Keuangan")
        out = r.redact(r"Gagal \\srv-kantor\KEUANGAN di 192.168.1.10 dan 192.168.1.10, juga 10.0.0.5")
        self.assertNotIn("SRV-KANTOR".lower(), out.lower())
        self.assertNotIn("keuangan".lower(), out.lower())
        self.assertNotIn("192.168", out)
        self.assertIn("IP-1", out); self.assertIn("IP-2", out)
        self.assertEqual(out.count("IP-1"), 2)  # token stabil

    def test_no_partial_word_replacement(self):
        r = Redactor(include_local_identity=False)
        r.add("HOST", "PC1")
        self.assertIn("PC10", r.redact("PC10 dan PC1"))

    def test_secrets(self):
        out = redact_secrets("net use /user:a password=Rahasia123 token: abc.def")
        self.assertNotIn("Rahasia123", out); self.assertNotIn("abc.def", out)


class AdapterSecurityTests(unittest.TestCase):
    def _proc(self, out=b"{}", err=b"", code=0):
        m = mock.Mock(); m.stdout, m.stderr, m.returncode = out, err, code
        return m

    def test_not_windows_and_unknown_ops(self):
        a = RealWindowsAdapter(platform="linux")
        self.assertTrue(a.run("os_info").unsupported)
        self.assertTrue(RealWindowsAdapter(platform="win32").run("Remove-Item").unsupported)
        self.assertTrue(RealWindowsAdapter(platform="win32").run("start_service", service="Spooler").unsupported)

    def test_params_via_env_not_script(self):
        a = RealWindowsAdapter(platform="win32")
        with mock.patch("nsd.windows.powershell.subprocess.run", return_value=self._proc(b'{"Ok":true}')) as run:
            res = a.run("test_unc", unc="\\\\srv-rahasia\\data")
        self.assertTrue(res.ok)
        args, kwargs = run.call_args
        self.assertIsInstance(args[0], list)
        self.assertIs(kwargs["shell"], False)
        self.assertNotIn("srv-rahasia", " ".join(args[0]))
        self.assertEqual(kwargs["env"]["NSD_P_UNC"], "\\\\srv-rahasia\\data")
        self.assertIn("timeout", kwargs)

    def test_injection_rejected_before_execution(self):
        a = RealWindowsAdapter(platform="win32")
        with mock.patch("nsd.windows.powershell.subprocess.run") as run:
            with self.assertRaises(ValidationError):
                a.run("list_remote_printers", host="a; Remove-Item C:\\ -Recurse")
            with self.assertRaises(ValidationError):
                a.run("get_service", service="Spooler; calc")
            with self.assertRaises(ValidationError):
                a.run("test_unc", unc="\\\\a\\b' ; calc ; '")
            with self.assertRaises(ValidationError):
                a.run("os_info", surprise="x")
            run.assert_not_called()

    def test_error_paths(self):
        a = RealWindowsAdapter(platform="win32")
        import subprocess
        with mock.patch("nsd.windows.powershell.subprocess.run", side_effect=subprocess.TimeoutExpired("p", 1)):
            self.assertTrue(a.run("os_info").timed_out)
        with mock.patch("nsd.windows.powershell.subprocess.run", return_value=self._proc(b"not json")):
            self.assertFalse(a.run("os_info").ok)
        with mock.patch("nsd.windows.powershell.subprocess.run", return_value=self._proc(b"", b"boom", 1)):
            r = a.run("os_info"); self.assertFalse(r.ok); self.assertEqual(r.exit_code, 1)
        with mock.patch("nsd.windows.powershell.subprocess.run", return_value=self._proc(b"")):
            r = a.run("os_info"); self.assertTrue(r.ok); self.assertIsNone(r.data)

    def test_all_read_ops_have_no_mutating_cmdlets(self):
        for name, spec in READ_OPERATIONS.items():
            for bad in ("Set-", "Remove-", "Start-", "Stop-", "Restart-", "New-", "Enable-", "Disable-",
                        "Add-", "Invoke-", "net use"):
                self.assertNotIn(bad, spec.script, f"{name} memuat {bad}")


if __name__ == "__main__":
    unittest.main()
