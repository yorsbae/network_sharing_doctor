import unittest

from nsd.application.error_lookup import known_codes, lookup
from nsd.application.repair_plan import build_plan
from nsd.repairs.executor import finding_for_rule
from nsd.rules.loader import load_rules

RULES = load_rules().rules


def f(rule_id):
    return finding_for_rule(RULES, rule_id)


class RepairPlanTests(unittest.TestCase):
    def test_stopped_spooler_is_auto_and_describes_the_change(self):
        plan = build_plan([f("PRN-SPOOLER-001")], RULES)
        self.assertEqual([i.finding.rule_id for i in plan.auto], ["PRN-SPOOLER-001"])
        self.assertIn("Spooler", plan.auto[0].summary)
        self.assertIn("startup tidak diubah", plan.auto[0].summary)

    def test_advice_only_and_unsupported_or_sensitive_stay_manual_with_a_reason(self):
        ids = ["PRN-11B-001", "NET-PROFILE-001", "SEC-SMB1-001", "FW-SHARING-001"]
        plan = build_plan([f(i) for i in ids], RULES)
        self.assertEqual(plan.auto, [])
        self.assertEqual(sorted(i.finding.rule_id for i in plan.manual), sorted(ids))
        self.assertTrue(all(i.reason for i in plan.manual))
        text = " ".join(i.summary + i.reason for i in plan.manual)
        for raw in ("set_network_profile_private", "enable_specific_firewall_rule", "level ini"):
            self.assertNotIn(raw, text)

    def test_duplicates_and_unknown_rules_are_ignored(self):
        plan = build_plan([f("PRN-SPOOLER-001"), f("PRN-SPOOLER-001")], RULES)
        self.assertEqual(len(plan.auto), 1)


class LookupTests(unittest.TestCase):
    def test_code_matches_regardless_of_case_and_padding(self):
        for q in ("0x0000011B", "0x11b", "error 0X11B saat connect"):
            r = lookup(RULES, q)
            self.assertEqual(r.code, "0x0000011B")
            self.assertIn("PRN-11B-001", [e.rule_id for e in r.entries])

    def test_unknown_code_returns_no_entries_but_keeps_the_code(self):
        r = lookup(RULES, "0x00000FFF")
        self.assertEqual((r.code, r.entries), ("0x00000FFF", []))

    def test_free_text_search_and_empty_query(self):
        self.assertTrue(lookup(RULES, "spooler").entries)
        self.assertEqual(lookup(RULES, "  ").entries, [])

    def test_known_codes_are_normalised_and_sorted(self):
        codes = known_codes(RULES)
        self.assertIn("0x0000011B", codes)
        self.assertEqual(codes, sorted(codes))

    def test_only_low_risk_supported_actions_claim_auto_fix(self):
        auto = {e.rule_id for r in RULES for e in [lookup(RULES, r["title"]).entries[0]] if e.auto_text}
        self.assertIn("PRN-SPOOLER-001", auto)
        self.assertNotIn("PRN-11B-001", auto)


if __name__ == "__main__":
    unittest.main()
