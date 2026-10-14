"""Gerbang kebijakan. Fase 1: eksekusi perubahan memang belum ada, apa pun levelnya."""
from __future__ import annotations

from enum import IntEnum

from nsd.models import Finding


class PolicyLevel(IntEnum):
    DIAGNOSE_ONLY = 1
    SAFE_AUTO = 2
    ADVANCED_APPROVED = 3


EXECUTION_AVAILABLE = False  # diubah hanya ketika executor + snapshot + verifikasi (Fase 2) teruji


def decide(finding: Finding, level: PolicyLevel) -> tuple[str, str]:
    """Kembalikan (kode, teks Indonesia) keputusan untuk satu temuan."""
    mutating = any(a.get("operation") != "advise" for a in finding.actions)
    if finding.auto_policy == "blocked" or finding.risk in ("high", "security_sensitive"):
        return "blocked", "Diblokir oleh kebijakan keselamatan; hanya penjelasan dan langkah manual."
    if not mutating or finding.auto_policy == "always_read_only":
        return "read_only", "Hanya saran/penjelasan; tidak ada perubahan sistem."
    if not EXECUTION_AVAILABLE:
        return "suggest_only", "Disarankan saja. Fase 1 bersifat baca-saja: tidak ada perubahan yang diterapkan."
    if level is PolicyLevel.DIAGNOSE_ONLY:
        return "suggest_only", "Level kebijakan 'Diagnosis saja': perbaikan tidak dijalankan."
    if level is PolicyLevel.SAFE_AUTO and finding.risk != "low":
        return "suggest_only", "Risiko di atas 'rendah' tidak diperbolehkan pada level ini."
    return "needs_confirmation", "Perlu persetujuan eksplisit sebelum diterapkan."


def apply_policy(findings: list[Finding], level: PolicyLevel) -> None:
    for f in findings:
        f.decision, f.decision_text = decide(f, level)
        f.lifecycle = "disarankan" if f.decision in ("suggest_only", "needs_confirmation") else "terdeteksi"
