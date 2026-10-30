import unittest

from nsd.application.error_lookup import known_codes, lookup
from nsd.models import Role, ScanRequest, TargetType
from nsd.rules.loader import load_rules
from nsd.rules.matcher import match_rules

RULES = load_rules().rules

PRINTER_CODES = (
    "0x0000011B", "0x00000709", "0x00000040", "0x0000007C", "0x00000BCB", "0x00000002", "0x00000005",
    "0x0000000A", "0x00000006", "0x00000057", "0x0000007E", "0x0000007F", "0x00000035", "0x00000043", "0x0000003A",
)
FOLDER_CODES = (
    "0x80070035", "0x80004005", "0x80070005", "0x80070043", "0x80070032", "0x80070079", "0x80070020",
    "0x80070021", "0x80070003", "0x80070002", "0x80070006", "0x80070057", "0x80070015",
)
# Kode yang hanya punya aturan berbasis bukti (kondisi); tanpa kondisi tidak ada petunjuk hanya-kode.
EVIDENCE_ONLY = {"0x80070043"}


class ErrorCatalogCodes(unittest.TestCase):
    def test_every_listed_code_has_a_catalog_entry(self):
        known = set(known_codes(RULES))
        for code in PRINTER_CODES + FOLDER_CODES:
            self.assertIn(code, known, code)
            self.assertTrue(lookup(RULES, code).entries, code)

    def test_short_form_codes_from_the_source_list_resolve(self):
        self.assertEqual(lookup(RULES, "0x000007e").code, "0x0000007E")
        self.assertEqual(lookup(RULES, "0x000007f").code, "0x0000007F")

    def test_code_alone_gives_low_confidence_read_only_hint(self):
        for target, codes in ((TargetType.PRINTER, PRINTER_CODES), (TargetType.FOLDER, FOLDER_CODES)):
            for code in codes:
                if code in EVIDENCE_ONLY:
                    continue
                found = match_rules(RULES, {}, ScanRequest(Role.CLIENT, target, "srv", "x", f"error {code}"))
                self.assertTrue(found, f"{target} {code}")
                for f in found:
                    self.assertEqual(f.confidence, "rendah", f"{code} {f.rule_id}")
                    self.assertEqual(f.risk, "read_only", f"{code} {f.rule_id}")

    def test_new_hint_rules_never_offer_a_mutating_action(self):
        new = [r for r in RULES if r["id"].split("-")[0] in ("PRN", "FLD") and not r["conditions"]]
        self.assertGreaterEqual(len(new), 20)
        for r in new:
            self.assertEqual([a["operation"] for a in r["actions"]], ["advise"], r["id"])


if __name__ == "__main__":
    unittest.main()
