"""Cocokkan bukti dengan aturan. Kode error hanya menaikkan keyakinan, bukan penyebab final."""
from __future__ import annotations

import re
from typing import Any

from nsd.models import CheckResult, Finding, ScanRequest
from nsd.rules.schema import CONFIDENCE_RANK

_RISK_RANK = {"read_only": 0, "low": 1, "medium": 2, "high": 3, "security_sensitive": 4}
_TOKEN = re.compile(r"^(?P<id>[a-z0-9_.]+):(?P<st>[a-z|]+)(?:\[(?P<k>[a-z0-9_]+)=(?P<v>[^\]]+)\])?$")


def condition_met(token: str, results: dict[str, CheckResult]) -> bool:
    m = _TOKEN.match(token)
    if not m:
        return False
    r = results.get(m["id"])
    if r is None or r.status.value not in m["st"].split("|"):
        return False
    if m["k"]:
        return str(r.evidence.get(m["k"], "")).lower() == m["v"].lower()
    return True


def _applies(rule: dict[str, Any], req: ScanRequest) -> bool:
    if req.role.value not in rule["roles"]:
        return False
    return any(req.target_type.includes(t) for t in rule["target_types"])


def match_rules(rules: list[dict[str, Any]], results: dict[str, CheckResult], req: ScanRequest) -> list[Finding]:
    code = req.error_code
    findings: list[Finding] = []
    for rule in rules:
        if not _applies(rule, req):
            continue
        code_hit = bool(code) and code in rule["error_codes"]
        if rule["conditions"]:
            if not all(condition_met(c, results) for c in rule["conditions"]):
                continue
            confidence = "tinggi" if code_hit else "sedang"
        else:
            if not code_hit:
                continue
            confidence = "rendah"
        findings.append(Finding(
            rule_id=rule["id"], version=rule["version"], title=rule["title"],
            explanation=rule["explanation"], confidence=confidence, risk=rule["risk"],
            auto_policy=rule["auto_policy"], requires_admin=rule["requires_admin"],
            actions=list(rule["actions"]), verification=list(rule["verification"]),
            rollback=dict(rule["rollback"]), escalation=rule["escalation"],
            matched_conditions=list(rule["conditions"]), matched_error_code=code_hit,
        ))
    # Petunjuk berbasis kode saja disembunyikan bila ada temuan berbasis bukti untuk kode yang sama.
    if code:
        strong = any(f.confidence != "rendah" and f.matched_error_code for f in findings)
        if strong:
            findings = [f for f in findings if f.confidence != "rendah"]
    findings.sort(key=lambda f: (-CONFIDENCE_RANK[f.confidence], -_RISK_RANK[f.risk], f.rule_id))
    return findings
