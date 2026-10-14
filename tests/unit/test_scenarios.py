import unittest

from nsd.application.scan_service import ScanService
from nsd.models import Role, ScanRequest, Status, TargetType
from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses, ok, svc

READ_ONLY_OPS = {"os_info", "get_service", "net_profile", "firewall_sharing", "smb_client_config",
                 "smb_server_config", "list_local_printers", "list_remote_printers", "list_local_shares",
                 "test_unc", "recent_print_errors"}


def scan(req, responses=None, net=None, elevated=True, local_names=None):
    resp = healthy_responses()
    resp.update(responses or {})
    ad = FakeAdapter(resp, elevated=elevated)
    out = ScanService(ad, net=net or FakeNet(), local_names=local_names).run(req)
    return out, ad


def R(role=Role.CLIENT, t=TargetType.FOLDER, host="SRV-KANTOR", share="DATA", err=""):
    return ScanRequest(role, t, host, share, err)


def st(out, cid):
    return next(c for c in out.checks if c.id == cid)


def rule_ids(out):
    return [f.rule_id for f in out.findings]


class Scenarios(unittest.TestCase):
    def tearDown(self):
        pass

    def assertReadOnly(self, ad):
        self.assertTrue({op for op, _ in ad.calls} <= READ_ONLY_OPS, ad.calls)

    def test_healthy_folder_client(self):
        out, ad = scan(R())
        self.assertEqual(out.count(Status.FAIL), 0)
        self.assertEqual(out.count(Status.WARNING), 0)
        self.assertEqual(out.overall, "tidak_ada_masalah_terbukti")
        self.assertEqual(out.findings, [])
        self.assertReadOnly(ad)

    def test_ping_ok_but_smb_blocked_is_diagnosed(self):
        out, _ = scan(R(err="0x80070035"), net=FakeNet(open_ports=()))
        self.assertEqual(st(out, "net.dns").status, Status.PASS)
        self.assertEqual(st(out, "net.tcp445").status, Status.FAIL)
        self.assertEqual(st(out, "smb.unc").status, Status.UNKNOWN)   # bukan FAIL
        self.assertEqual(rule_ids(out)[0], "NET-SMB-001")
        self.assertEqual(out.findings[0].confidence, "tinggi")

    def test_dns_failure_skips_dependents_as_unknown(self):
        out, ad = scan(R(err="0x80070035"), net=FakeNet(resolve_error=True))
        self.assertEqual(st(out, "net.dns").status, Status.FAIL)
        self.assertEqual(st(out, "net.tcp445").status, Status.UNKNOWN)
        self.assertIn("NET-NAME-001", rule_ids(out))
        self.assertNotIn("test_unc", [op for op, _ in ad.calls])

    def test_access_denied_distinguished_from_missing_share(self):
        denied = {"test_unc": ok({"Ok": False, "ErrorType": "UnauthorizedAccessException",
                                  "HResult": -2147024891, "Message": "Access to the path is denied."})}
        out, _ = scan(R(err="Access is denied 0x80070005"), denied)
        self.assertEqual(st(out, "smb.unc").evidence["category"], "access_denied")
        self.assertEqual(rule_ids(out), ["FLD-ACCESS-001"])
        badname = {"test_unc": ok({"Ok": False, "ErrorType": "IOException", "HResult": -2147024829,
                                   "Message": "The network name cannot be found."})}
        out2, _ = scan(R(), badname)
        self.assertEqual(st(out2, "smb.unc").evidence["category"], "bad_net_name")
        self.assertEqual(rule_ids(out2), ["FLD-NOSHARE-001"])
        logon = {"test_unc": ok({"Ok": False, "ErrorType": "IOException", "HResult": -2147023570,
                                 "Message": "The user name or password is incorrect."})}
        self.assertEqual(rule_ids(scan(R(), logon)[0]), ["FLD-LOGON-001"])

    def test_spooler_stopped_only_suggested_never_executed(self):
        def services(service):
            return svc(service, "Stopped") if service == "Spooler" else svc(service)
        out, ad = scan(R(t=TargetType.PRINTER, share="EPSON"), {"get_service": services})
        f = next(x for x in out.findings if x.rule_id == "PRN-SPOOLER-001")
        self.assertEqual(f.decision, "suggest_only")
        self.assertEqual(f.lifecycle, "disarankan")
        self.assertIn("baca-saja", f.decision_text)
        self.assertReadOnly(ad)
        self.assertNotIn("start_service", [op for op, _ in ad.calls])

    def test_printer_connect_is_not_tested_not_failed(self):
        out, _ = scan(R(t=TargetType.PRINTER, share="EPSON"))
        self.assertEqual(st(out, "printer.connect_test").status, Status.UNKNOWN)
        self.assertEqual(st(out, "printer.remote_share").status, Status.PASS)

    def test_wrong_printer_share_lists_available(self):
        out, _ = scan(R(t=TargetType.PRINTER, share="EPSN"))
        c = st(out, "printer.remote_share")
        self.assertEqual(c.status, Status.FAIL)
        self.assertIn("EPSON", c.detail)
        self.assertEqual(rule_ids(out), ["PRN-NOPRN-001"])

    def test_0x11b_is_only_a_low_confidence_hint(self):
        out, _ = scan(R(t=TargetType.PRINTER, share="EPSON", err="Operation failed with error 0x0000011b"))
        self.assertEqual(rule_ids(out), ["PRN-11B-001"])
        self.assertEqual(out.findings[0].confidence, "rendah")
        self.assertEqual(out.findings[0].matched_conditions, [])

    def test_remote_printer_errors_classified(self):
        for msg, rule in (("Access is denied", "PRN-ACCESS-001"), ("The RPC server is unavailable", "PRN-RPC-001")):
            from nsd.windows.powershell import OpResult
            out, _ = scan(R(t=TargetType.PRINTER, share="EPSON"), {"list_remote_printers": OpResult(False, error=msg)})
            self.assertEqual(rule_ids(out), [rule])

    def test_server_security_findings_are_blocked(self):
        resp = {"smb_server_config": ok({"EnableSMB1Protocol": True, "EnableSMB2Protocol": True}),
                "smb_client_config": ok({"EnableInsecureGuestLogons": True})}
        out, ad = scan(R(Role.SERVER, TargetType.FOLDER, "localhost", "DATA"), resp)
        blocked = {f.rule_id: f for f in out.findings}
        self.assertEqual(blocked["SEC-SMB1-001"].decision, "blocked")
        self.assertEqual(blocked["SEC-GUEST-001"].decision, "blocked")
        self.assertReadOnly(ad)

    def test_server_firewall_and_profile(self):
        resp = {"firewall_sharing": ok([{"Enabled": "False", "Direction": "Inbound", "Action": "Allow", "Profile": "Any"}]),
                "net_profile": ok([{"Category": "Public", "IPv4": "Internet"}])}
        out, _ = scan(R(Role.SERVER, TargetType.FOLDER, "localhost", "DATA"), resp)
        ids = rule_ids(out)
        self.assertIn("FW-SHARING-001", ids); self.assertIn("NET-PROFILE-001", ids)
        for f in out.findings:
            self.assertEqual(f.decision, "suggest_only")
            self.assertTrue(f.requires_admin)
            self.assertNotEqual(f.rollback.get("type"), "not_applicable_read_only")

    def test_server_printer_not_shared(self):
        resp = {"list_local_printers": ok([{"Name": "EPSON L3210", "Driver": "E", "Port": "USB", "Shared": False,
                                            "ShareName": "", "Status": "Normal"}])}
        out, _ = scan(R(Role.SERVER, TargetType.PRINTER, "localhost", "EPSON L3210"), resp)
        self.assertEqual(st(out, "local.printer_share").evidence["category"], "not_shared")
        self.assertIn("PRN-SHARE-001", rule_ids(out))

    def test_server_missing_folder_share(self):
        out, _ = scan(R(Role.SERVER, TargetType.FOLDER, "localhost", "TIDAKADA"))
        self.assertIn("FLD-SERVERSHARE-001", rule_ids(out))

    def test_not_windows_everything_windows_specific_is_unknown(self):
        ad = FakeAdapter({}, elevated=False)
        out = ScanService(ad, net=FakeNet()).run(R(t=TargetType.BOTH))
        for cid in ("local.svc.workstation", "local.profile", "local.smb_client", "local.os"):
            self.assertEqual(st(out, cid).status, Status.UNKNOWN, cid)
        self.assertEqual(out.count(Status.PASS) > 0, True)

    def test_invalid_input_stops_before_any_probe(self):
        net = FakeNet()
        out, ad = scan(R(host="srv;calc"), net=net)
        self.assertEqual(st(out, "target.input").status, Status.FAIL)
        self.assertEqual(net.connects, [])
        self.assertNotIn("test_unc", [op for op, _ in ad.calls])
        self.assertNotIn("list_remote_printers", [op for op, _ in ad.calls])

    def test_literal_ip_marks_name_resolution_untested_in_detail(self):
        out, _ = scan(R(host="192.168.1.10"))
        c = st(out, "net.dns")
        self.assertTrue(c.evidence["literal_ip"])
        self.assertIn("TIDAK teruji", c.detail)

    def test_broken_check_does_not_abort_scan(self):
        def boom(**_): raise RuntimeError("kaboom")
        out, _ = scan(R(), {"net_profile": boom})
        self.assertTrue(any(c.id.startswith("internal.") and c.status is Status.UNKNOWN for c in out.checks))
        self.assertEqual(st(out, "smb.unc").status, Status.PASS)


if __name__ == "__main__":
    unittest.main()
