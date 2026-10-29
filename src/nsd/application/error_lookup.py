"""Pencarian kode error di katalog aturan (satu sumber kebenaran: berkas rules/*.json)."""
from __future__ import annotations

from dataclasses import dataclass, field

from nsd.models import normalize_error_code
from nsd.repairs.executor import SUPPORTED_OPERATIONS


@dataclass
class Entry:
    rule_id: str
    title: str
    explanation: str
    codes: list[str]
    steps: list[str]
    escalation: str
    auto_text: str = ""            # kosong = tidak ada perbaikan otomatis
    matched_code: bool = False


@dataclass
class Result:
    query: str
    code: str = ""                 # kode ternormalisasi bila kueri memuat kode
    entries: list[Entry] = field(default_factory=list)


def _entry(rule: dict, matched: bool) -> Entry:
    steps = [a["text"] for a in rule.get("actions", []) if a.get("operation") == "advise" and a.get("text")]
    autos = [a for a in rule.get("actions", []) if a.get("operation") in SUPPORTED_OPERATIONS]
    auto = ""
    if autos and rule.get("risk") == "low":
        auto = "Dapat dijalankan otomatis: menyalakan layanan " + ", ".join(str(a.get("service_name")) for a in autos) + "."
    return Entry(rule["id"], rule["title"], rule.get("explanation", ""), [normalize_error_code(c) or c for c in rule.get("error_codes", [])],
                 steps, rule.get("escalation", ""), auto, matched)


def known_codes(rules: list[dict]) -> list[str]:
    return sorted({normalize_error_code(c) or c for r in rules for c in r.get("error_codes", [])})


def lookup(rules: list[dict], query: str) -> Result:
    q = (query or "").strip()
    res = Result(q, normalize_error_code(q))
    if not q:
        return res
    if res.code:
        res.entries = [_entry(r, True) for r in rules if res.code in {normalize_error_code(c) for c in r.get("error_codes", [])}]
        return res
    low = q.lower()
    for r in rules:
        hay = " ".join([r["title"], r.get("explanation", ""), " ".join(r.get("symptoms", []))]).lower()
        if low in hay:
            res.entries.append(_entry(r, False))
    return res
