import copy
import json
import tempfile
import unittest
from pathlib import Path

from nsd.models import CheckResult, Layer, Role, ScanRequest, Status, TargetType, normalize_error_code
from nsd.rules.loader import load_rules
from nsd.rules.matcher import condition_met, match_rules
from nsd.rules.schema import validate_rule


def chk(cid, status, **ev):
    return CheckResult(cid, Layer.NETWORK, cid, status, "", dict(ev))


class ShippedRules(unittest.TestCase):
    def test_all_valid_and_unique(self):
        rs = load_rules()
        self.assertEqual(rs.errors, [])
        ids = [r["id"] for r in rs.rules]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 20)

    def test_shipped_rules_never_weaken_security(self):
        for r in load_rules().rules:
            for a in r["actions"]:
                self.assertIn(a["operation"], {"advise", "start_service", "enable_specific_firewall_rule",
                                               "share_printer", "set_network_profile_private"})
            if r["risk"] in ("high", "security_sensitive"):
                self.assertEqual(r["auto_policy"], "blocked")

    def test_code_only_rules_are_low_confidence_hints(self):
        req = ScanRequest(Role.CLIENT, TargetType.PRINTER, "srv", "p", "error 0x0000011b")
        f = match_rules(load_rules().rules, {}, req)
        self.assertEqual([x.rule_id for x in f], ["PRN-11B-001"])
        self.assertEqual(f[0].confidence, "rendah")


class SchemaRejects(unittest.TestCase):
    def base(self):
        return copy.deepcopy(next(r for r in load_rules().rules if r["id"] == "PRN-SPOOLER-001"))

    def test_base_valid(self):
        self.assertEqual(validate_rule(self.base()), [])

    def _expect(self, mutate, fragment):
        r = self.base(); mutate(r)
        errs = validate_rule(r)
        self.assertTrue(any(fragment in e for e in errs), errs)

    def test_rejections(self):
        self._expect(lambda r: r.pop("verification"), "field wajib")
        self._expect(lambda r: r.update(surprise=1), "tidak dikenal")
        self._expect(lambda r: r["actions"].append({"operation": "disable_firewall"}), "terlarang")
        self._expect(lambda r: r["actions"].append({"operation": "run_powershell", "script": "calc"}), "terlarang")
        self._expect(lambda r: r.update(risk="high"), "blocked")
        self._expect(lambda r: r.update(risk="security_sensitive", auto_policy="auto_if_approved"), "blocked")
        self._expect(lambda r: r.update(snapshot_keys=[]), "snapshot_keys")
        self._expect(lambda r: r.update(verification=[]), "verification")
        self._expect(lambda r: r.update(rollback={}), "rollback")
        self._expect(lambda r: r.update(risk="read_only"), "read_only")
        self._expect(lambda r: r.update(conditions=["bad token"]), "kondisi tidak valid")
        self._expect(lambda r: r.update(error_codes=["0x11B"]), "format")
        self._expect(lambda r: r.update(roles=["admin"]), "roles")
        self._expect(lambda r: r.update(id="spooler"), "id harus")
        self._expect(lambda r: r.update(conditions=[], error_codes=[]), "kondisi bukti atau kode")
        self._expect(lambda r: r["actions"].__setitem__(0, {"operation": "start_service", "service_name": "WinDefend"}), "allowlist")


class LoaderUntrusted(unittest.TestCase):
    def test_bad_files_do_not_load(self):
        good = next(r for r in load_rules().rules if r["id"] == "NET-NAME-001")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a.json").write_text("{not json", encoding="utf-8")
            (d / "b.json").write_bytes(b"\xff\xfe\x00")
            (d / "c.json").write_text(json.dumps({"rules": "nope"}), encoding="utf-8")
            evil = dict(good, id="NET-EVIL-001", actions=[{"operation": "run_shell", "cmd": "calc"}])
            (d / "d.json").write_text(json.dumps({"rules": [good, good, evil]}), encoding="utf-8")
            rs = load_rules(d)
            self.assertEqual([r["id"] for r in rs.rules], ["NET-NAME-001"])
            self.assertEqual(len(rs.errors), 5)
            self.assertTrue(any("duplikat" in e for e in rs.errors))

    def test_digest_changes_with_content(self):
        good = next(r for r in load_rules().rules if r["id"] == "NET-NAME-001")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_text(json.dumps({"rules": [good]}), encoding="utf-8")
            d1 = load_rules(Path(d)).digest
            p.write_text(json.dumps({"rules": [dict(good, title="lain")]}), encoding="utf-8")
            self.assertNotEqual(d1, load_rules(Path(d)).digest)


class MatcherTests(unittest.TestCase):
    def test_conditions(self):
        res = {"a.b": chk("a.b", Status.FAIL, category="Access_Denied")}
        self.assertTrue(condition_met("a.b:fail", res))
        self.assertTrue(condition_met("a.b:fail|warning", res))
        self.assertTrue(condition_met("a.b:fail[category=access_denied]", res))
        self.assertFalse(condition_met("a.b:pass", res))
        self.assertFalse(condition_met("a.b:fail[category=other]", res))
        self.assertFalse(condition_met("zzz:fail", res))
        self.assertFalse(condition_met("garbage", res))

    def test_error_code_normalization(self):
        self.assertEqual(normalize_error_code("Operation failed with error 0x11b"), "0x0000011B")
        self.assertEqual(normalize_error_code("0x80070035"), "0x80070035")
        self.assertEqual(normalize_error_code("tanpa kode"), "")

    def test_code_boosts_but_does_not_replace_evidence(self):
        rules = load_rules().rules
        res = {"net.dns": chk("net.dns", Status.PASS), "net.tcp445": chk("net.tcp445", Status.FAIL)}
        no_code = match_rules(rules, res, ScanRequest(Role.CLIENT, TargetType.FOLDER, "s", "d", ""))
        with_code = match_rules(rules, res, ScanRequest(Role.CLIENT, TargetType.FOLDER, "s", "d", "0x80070035"))
        self.assertEqual(no_code[0].rule_id, "NET-SMB-001"); self.assertEqual(no_code[0].confidence, "sedang")
        self.assertEqual(with_code[0].confidence, "tinggi")
        self.assertNotIn("GEN-HINT-002", [f.rule_id for f in with_code])  # petunjuk disembunyikan

    def test_code_alone_cannot_trigger_evidence_rule(self):
        rules = load_rules().rules
        res = {"net.dns": chk("net.dns", Status.PASS), "net.tcp445": chk("net.tcp445", Status.PASS)}
        f = match_rules(rules, res, ScanRequest(Role.CLIENT, TargetType.FOLDER, "s", "d", "0x80070035"))
        ids = [x.rule_id for x in f]
        self.assertNotIn("NET-NAME-001", ids); self.assertNotIn("NET-SMB-001", ids)
        self.assertEqual(ids, ["GEN-HINT-002"])

    def test_role_and_type_scoping(self):
        rules = load_rules().rules
        res = {"local.svc.server": chk("local.svc.server", Status.FAIL)}
        self.assertEqual(match_rules(rules, res, ScanRequest(Role.CLIENT, TargetType.FOLDER, "s", "d")), [])
        self.assertEqual([f.rule_id for f in match_rules(rules, res, ScanRequest(Role.SERVER, TargetType.FOLDER, "s", "d"))],
                         ["SVC-SERVER-001"])


if __name__ == "__main__":
    unittest.main()
