"""Penyiapan server otomatis: rencana, penerapan, verifikasi jujur. Adapter palsu; BUKAN bukti di Windows asli."""
import unittest

from nsd.application import server_prepare as sp
from nsd.application.server_setup import check_readiness
from nsd.security.allowlist import ValidationError, validate_printer_name, validate_share_plain
from nsd.windows.powershell import MUTATING_OPERATIONS, OpResult
from tests.fixtures.fakes import FakeAdapter, healthy_responses, ok, svc

PRINTERS = [
    {"Name": "EPSON L3210", "Driver": "E", "Port": "USB001", "Shared": False, "ShareName": "", "Status": "Normal"},
    {"Name": "Microsoft Print to PDF", "Driver": "P", "Port": "PORTPROMPT:", "Shared": False, "ShareName": "", "Status": "Normal"},
]


class Machine(FakeAdapter):
    """Windows palsu berstatus: apply mengubah keadaan, run membacanya. `broken` = operasi yang tidak berefek."""
    def __init__(self, broken=(), elevated=True):
        super().__init__(elevated=elevated)
        self.spooler, self.profile, self.fw = "Stopped", "Public", False
        self.printers = [dict(p) for p in PRINTERS]
        self.broken, self.applied = set(broken), []

    def run(self, op, **p):
        self.calls.append((op, p))
        if op == "os_info": return ok({"ComputerName": "PC-KASIR"})
        if op == "get_service": return svc(p["service"], self.spooler if p["service"] == "Spooler" else "Running")
        if op == "net_profile": return ok([{"Category": self.profile, "IPv4": "Internet"}])
        if op == "firewall_sharing":
            return ok([{"Enabled": str(self.fw), "Direction": "Inbound", "Action": "Allow", "Profile": "Private"}])
        if op == "list_local_printers": return ok(self.printers)
        return OpResult(False, error="x", unsupported=True)

    def apply(self, op, **p):
        self.applied.append((op, p))
        if not self.elevated:
            return OpResult(False, error="Butuh hak administrator.", unsupported=True)
        if op in self.broken:
            return OpResult(True, data={})                      # perintah "berhasil" tetapi tidak berefek
        if op == "start_service": self.spooler = "Running"
        elif op == "set_network_private": self.profile = "Private"
        elif op == "enable_sharing_firewall": self.fw = True
        elif op == "share_printer":
            for x in self.printers:
                if x["Name"] == p["printer"]:
                    x["Shared"], x["ShareName"] = True, p["share"]
        return OpResult(True, data={})


class PrepareTests(unittest.TestCase):
    def test_plan_covers_every_fixable_step_in_order(self):
        m = Machine()
        acts = sp.plan(check_readiness(m, addresses=lambda: []))
        self.assertEqual([a.key for a in acts], ["spooler", "profile", "firewall", "share:EPSON L3210",
                                                 "share:Microsoft Print to PDF"])
        self.assertEqual([a.default_on for a in acts][-2:], [True, False])      # printer virtual tidak dicentang bawaan
        self.assertEqual(acts[-2].params["share"], "EPSONL3210")

    def test_plan_empty_when_ready(self):
        self.assertEqual(sp.plan(check_readiness(FakeAdapter(healthy_responses()), addresses=lambda: [])), [])

    def test_apply_all_verified_and_ready_afterwards(self):
        m = Machine()
        acts = sp.plan(check_readiness(m, addresses=lambda: []))
        res = sp.apply(m, acts, sleep=lambda s: None)
        self.assertTrue(all(r.outcome == "verified" for r in res), [(r.action.key, r.outcome, r.message) for r in res])
        self.assertEqual(check_readiness(m, addresses=lambda: []).verdict[1], "ok")

    def test_command_without_effect_is_not_reported_as_success(self):
        m = Machine(broken={"enable_sharing_firewall"})
        res = sp.apply(m, [a for a in sp.plan(check_readiness(m, addresses=lambda: [])) if a.key == "firewall"],
                       sleep=lambda s: None, retries=2)
        self.assertEqual(res[0].outcome, "unverified")

    def test_not_admin_is_refused_without_side_effects(self):
        m = Machine(elevated=False)
        res = sp.apply(m, sp.plan(check_readiness(m, addresses=lambda: []))[:2], sleep=lambda s: None)
        self.assertEqual({r.outcome for r in res}, {"refused"})
        self.assertEqual((m.spooler, m.profile), ("Stopped", "Public"))

    def test_one_failure_does_not_stop_others(self):
        m = Machine()
        acts = sp.plan(check_readiness(m, addresses=lambda: []))
        m.apply_orig = m.apply
        m.apply = lambda op, **p: OpResult(False, error="gagal") if op == "start_service" else m.apply_orig(op, **p)
        res = sp.apply(m, acts, sleep=lambda s: None)
        self.assertEqual(res[0].outcome, "failed")
        self.assertEqual(res[1].outcome, "verified")

    def test_share_names_unique_and_valid(self):
        self.assertEqual(sp.suggest_share_name("EPSON L3210", {"epsonl3210"}), "EPSONL32102")
        self.assertEqual(sp.suggest_share_name("???", set()), "Printer")


class AllowlistTests(unittest.TestCase):
    def test_validators(self):
        self.assertEqual(validate_printer_name("EPSON L3210 (Copy 1)"), "EPSON L3210 (Copy 1)")
        for bad in ("", "a\nb", "x" * 201):
            with self.assertRaises(ValidationError):
                validate_printer_name(bad)
        for bad in ("a b", "a;b", "", "a\\b"):
            with self.assertRaises(ValidationError):
                validate_share_plain(bad)

    def test_new_ops_use_env_params_not_string_interpolation(self):
        spec = MUTATING_OPERATIONS["share_printer"]
        self.assertIn("$env:NSD_P_PRINTER", spec.script)
        self.assertNotIn("{printer}", spec.script)       # tidak ada sisa format string
        self.assertNotIn("{share}", spec.script)
        for name in ("set_network_private", "enable_sharing_firewall"):
            self.assertEqual(MUTATING_OPERATIONS[name].params, {})


if __name__ == "__main__":
    unittest.main()
