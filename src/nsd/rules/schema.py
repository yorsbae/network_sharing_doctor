"""Validasi skema aturan. Aturan yang tidak valid TIDAK dimuat."""
from __future__ import annotations

import re
from typing import Any

from nsd.security.allowlist import ALLOWED_OPERATIONS, validate_action

RISKS = ("read_only", "low", "medium", "high", "security_sensitive")
AUTO_POLICIES = ("always_read_only", "auto_if_approved", "requires_confirmation", "blocked")
CONFIDENCE_RANK = {"tinggi": 3, "sedang": 2, "rendah": 1}

REQUIRED = (
    "id", "version", "title", "description", "explanation", "symptoms", "error_codes",
    "conditions", "required_evidence", "os_constraints", "roles", "target_types",
    "risk", "requires_admin", "auto_policy", "actions", "snapshot_keys",
    "verification", "rollback", "failure_message", "escalation", "references",
)
_COND = re.compile(
    r"^[a-z0-9_.]+:(pass|fail|warning|unknown)(\|(pass|fail|warning|unknown))*(\[[a-z0-9_]+=[^\]]+\])?$"
)
_CODE = re.compile(r"^0x[0-9A-F]{8}$")
_ID = re.compile(r"^[A-Z]{2,5}-[A-Z0-9]+-\d{3}$")


def validate_rule(rule: Any) -> list[str]:
    if not isinstance(rule, dict):
        return ["aturan harus berupa objek JSON"]
    errs: list[str] = []
    for key in REQUIRED:
        if key not in rule:
            errs.append(f"field wajib hilang: {key}")
    if errs:
        return errs
    extra = set(rule) - set(REQUIRED)
    if extra:
        errs.append(f"field tidak dikenal: {sorted(extra)}")
    if not isinstance(rule["id"], str) or not _ID.match(rule["id"]):
        errs.append("id harus berformat mis. PRN-SPOOLER-001")
    if not isinstance(rule["version"], int) or rule["version"] < 1:
        errs.append("version harus bilangan bulat >= 1")
    if rule["risk"] not in RISKS:
        errs.append(f"risk tidak valid: {rule['risk']!r}")
    if rule["auto_policy"] not in AUTO_POLICIES:
        errs.append(f"auto_policy tidak valid: {rule['auto_policy']!r}")
    if not isinstance(rule["requires_admin"], bool):
        errs.append("requires_admin harus boolean")
    for key in ("roles", "target_types"):
        allowed = {"roles": {"client", "server"}, "target_types": {"printer", "folder"}}[key]
        v = rule[key]
        if not isinstance(v, list) or not v or not set(v) <= allowed:
            errs.append(f"{key} harus subset tak kosong dari {sorted(allowed)}")
    for key in ("symptoms", "conditions", "required_evidence", "os_constraints",
                "snapshot_keys", "verification", "references", "error_codes", "actions"):
        if not isinstance(rule[key], list):
            errs.append(f"{key} harus berupa list")
    if errs:
        return errs
    for c in rule["conditions"]:
        if not isinstance(c, str) or not _COND.match(c):
            errs.append(f"kondisi tidak valid: {c!r}")
    for code in rule["error_codes"]:
        if not isinstance(code, str) or not _CODE.match(code):
            errs.append(f"kode error harus format 0x0000011B: {code!r}")
    if not rule["conditions"] and not rule["error_codes"]:
        errs.append("aturan harus punya kondisi bukti atau kode error")
    mutating = False
    for a in rule["actions"]:
        if not isinstance(a, dict):
            errs.append("aksi harus objek")
            continue
        errs.extend(validate_action(a))
        spec = ALLOWED_OPERATIONS.get(a.get("operation"))
        mutating = mutating or bool(spec and spec.mutating)
    # Konsistensi keselamatan (spesifikasi §3 dan §11)
    if rule["risk"] in ("high", "security_sensitive") and rule["auto_policy"] != "blocked":
        errs.append("risk high/security_sensitive wajib auto_policy 'blocked' (default terblokir)")
    if mutating:
        if rule["auto_policy"] == "always_read_only" or rule["risk"] == "read_only":
            errs.append("aturan dengan aksi pengubah tidak boleh read_only")
        if not rule["snapshot_keys"]:
            errs.append("aksi pengubah wajib punya snapshot_keys")
        if not rule["verification"]:
            errs.append("aksi pengubah wajib punya verification")
        rb = rule["rollback"]
        if not isinstance(rb, dict) or "type" not in rb:
            errs.append("aksi pengubah wajib mendeklarasikan rollback.type (boleh 'not_supported')")
    elif rule["risk"] != "read_only" and rule["auto_policy"] not in ("blocked", "always_read_only"):
        errs.append("aturan tanpa aksi pengubah sebaiknya read_only atau blocked")
    return errs
