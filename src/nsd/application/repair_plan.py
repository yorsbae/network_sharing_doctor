"""Rencana perbaikan dari hasil scan: mana yang boleh otomatis, mana yang harus manual (dan alasannya).

Satu-satunya sumber kebenaran adalah ATURAN yang sedang dimuat + gerbang kebijakan + daftar operasi yang
didukung eksekutor. UI tidak memutuskan sendiri apa yang aman.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nsd.application.policy_service import PolicyLevel, decide
from nsd.models import Finding
from nsd.repairs.executor import SUPPORTED_OPERATIONS, finding_for_rule


@dataclass
class PlanItem:
    finding: Finding           # dibangun dari aturan yang sedang dimuat (bukan dari DB)
    summary: str               # kalimat tentang apa yang akan diubah / dilakukan manual
    reason: str = ""           # untuk item manual: kenapa tidak otomatis


@dataclass
class RepairPlan:
    auto: list[PlanItem] = field(default_factory=list)
    manual: list[PlanItem] = field(default_factory=list)


_OP_TEXT = {
    "set_network_profile_private": "Mengubah profil jaringan dari Publik menjadi Pribadi.",
    "enable_specific_firewall_rule": "Mengaktifkan aturan firewall File and Printer Sharing.",
    "share_printer": "Membagikan printer ini ke jaringan.",
}


def _describe(f: Finding) -> str:
    parts = []
    for a in f.actions:
        if a["operation"] == "advise":
            parts.append(a.get("text", ""))
        elif a["operation"] == "start_service":
            parts.append(f"Menyalakan layanan {a.get('service_name')}. Tipe startup tidak diubah.")
        else:
            parts.append(_OP_TEXT.get(a["operation"], "Mengubah pengaturan sistem."))
    return " ".join(p for p in parts if p)


def build_plan(findings: list[Finding], rules: list[dict]) -> RepairPlan:
    plan, seen = RepairPlan(), set()
    for scanned in findings:
        if scanned.rule_id in seen:
            continue
        seen.add(scanned.rule_id)
        base = finding_for_rule(rules, scanned.rule_id)
        if base is None or not base.actions:
            continue
        mutating = [a for a in base.actions if a["operation"] != "advise"]
        code, text = decide(base, PolicyLevel.SAFE_AUTO, execution_available=True)
        if mutating and code == "needs_confirmation" and all(a["operation"] in SUPPORTED_OPERATIONS for a in mutating):
            plan.auto.append(PlanItem(base, _describe(base)))
        elif mutating and code == "needs_confirmation":
            plan.manual.append(PlanItem(base, _describe(base), "Perbaikan otomatis untuk langkah ini belum tersedia."))
        elif mutating:
            reason = ("Diblokir demi keamanan; hanya panduan manual." if base.risk in ("high", "security_sensitive")
                      else "Risikonya di atas rendah, jadi belum dijalankan otomatis. Lakukan manual atau minta teknisi.")
            plan.manual.append(PlanItem(base, _describe(base), reason))
        else:
            plan.manual.append(PlanItem(base, _describe(base), "Hanya panduan; tidak ada yang diubah otomatis."))
    return plan
