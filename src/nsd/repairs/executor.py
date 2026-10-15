"""Eksekutor perbaikan (Fase 2) — saat ini HANYA `start_service` untuk layanan di allowlist.

Urutan wajib (vision B §11): gerbang kebijakan → baca keadaan awal → SNAPSHOT tersimpan →
terapkan → VERIFIKASI ulang → catat audit. Tidak ada klaim "berhasil" tanpa verifikasi.
Rollback hanya memulihkan keadaan layanan (Running→Stopped bila awalnya Stopped) atas persetujuan.
Tipe startup tidak pernah diubah; layanan Disabled tidak "diperbaiki" (dilaporkan apa adanya).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from nsd.application.policy_service import PolicyLevel, decide
from nsd.models import Finding
from nsd.security.allowlist import ValidationError, validate_service
from nsd.storage.repositories import AuditRepository, RepairRepository
from nsd.windows.powershell import WindowsAdapter

SUPPORTED_OPERATIONS = frozenset({"start_service"})

# Hasil: refused | noop | verified | applied_unverified | failed
@dataclass
class RepairResult:
    outcome: str
    message: str
    action_id: int | None = None
    snapshot_id: int | None = None
    steps: list[str] = field(default_factory=list)
    rollback_available: bool = False

    @property
    def success(self) -> bool:
        return self.outcome in ("verified", "noop")


def finding_for_rule(rules: list[dict[str, Any]], rule_id: str) -> Finding | None:
    """Bangun Finding dari ATURAN yang sedang dimuat (sumber kebenaran), bukan dari data DB."""
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if rule is None:
        return None
    return Finding(
        rule_id=rule["id"], version=rule["version"], title=rule["title"], explanation=rule["explanation"],
        confidence="sedang", risk=rule["risk"], auto_policy=rule["auto_policy"],
        requires_admin=rule["requires_admin"], actions=list(rule["actions"]),
        verification=list(rule["verification"]), rollback=dict(rule["rollback"]),
        escalation=rule["escalation"], matched_conditions=list(rule["conditions"]), matched_error_code=False)


class RepairExecutor:
    def __init__(self, adapter: WindowsAdapter, repo: RepairRepository, audit: AuditRepository,
                 execution_enabled: bool, sleep: Callable[[float], None] = time.sleep,
                 verify_timeout: float = 15.0, poll_interval: float = 1.0) -> None:
        self.adapter, self.repo, self.audit = adapter, repo, audit
        self.enabled, self._sleep = execution_enabled, sleep
        self.verify_timeout, self.poll = verify_timeout, poll_interval

    # -- util -------------------------------------------------------------
    def _refuse(self, case_id: str, rule_id: str, reason: str) -> RepairResult:
        self.audit.log("repair_refused", case_id, self.adapter.is_elevated(), policy_decision="refused",
                       rule_id=rule_id, reason=reason)
        return RepairResult("refused", reason, steps=["Ditolak sebelum ada perubahan: " + reason])

    def _state(self, service: str) -> dict | None:
        op = self.adapter.run("get_service", service=service)
        return op.data if op.ok and isinstance(op.data, dict) else None

    # -- eksekusi ---------------------------------------------------------
    def execute(self, finding: Finding, case_id: str, approved: bool) -> RepairResult:
        rid = finding.rule_id
        if not self.enabled:
            return self._refuse(case_id, rid, "Eksekusi perbaikan belum diaktifkan di pengaturan.")
        if not approved:
            return self._refuse(case_id, rid, "Belum ada persetujuan eksplisit dari pengguna.")
        code, text = decide(finding, PolicyLevel.SAFE_AUTO, execution_available=True)
        if code != "needs_confirmation":
            return self._refuse(case_id, rid, f"Kebijakan tidak mengizinkan perubahan otomatis ({code}): {text}")
        mutating = [a for a in finding.actions if a.get("operation") != "advise"]
        if not mutating or any(a["operation"] not in SUPPORTED_OPERATIONS for a in mutating):
            return self._refuse(case_id, rid, "Aturan memuat operasi yang belum didukung eksekutor.")
        if finding.requires_admin and not self.adapter.is_elevated():
            return self._refuse(case_id, rid, "Butuh hak administrator; jalankan ulang sebagai administrator.")
        try:
            service = validate_service(str(mutating[0]["service_name"]))
        except (ValidationError, KeyError) as exc:
            return self._refuse(case_id, rid, f"Parameter aksi tidak valid: {exc}")
        if len(mutating) != 1:
            return self._refuse(case_id, rid, "Hanya satu aksi per perbaikan yang didukung saat ini.")

        steps: list[str] = []
        before = self._state(service)
        if before is None:
            return self._refuse(case_id, rid, f"Keadaan awal layanan {service} tidak terbaca; tidak ada yang diubah.")
        steps.append(f"Keadaan awal: {before.get('Status')} (startup {before.get('StartType')}).")
        if before.get("Status") == "Running":
            self.audit.log("repair_noop", case_id, True, policy_decision="needs_confirmation", rule_id=rid, service=service)
            return RepairResult("noop", f"Layanan {service} sudah berjalan; tidak ada perubahan.", steps=steps)

        # 1) SNAPSHOT dulu; bila gagal disimpan, jangan lanjut.
        try:
            snap = self.repo.add_snapshot(case_id, None, "service_state", {"service": service, **before},
                                          restore_supported=before.get("Status") == "Stopped")
        except Exception as exc:  # noqa: BLE001
            return self._refuse(case_id, rid, f"Snapshot gagal disimpan ({exc.__class__.__name__}); tidak ada yang diubah.")
        steps.append("Snapshot keadaan awal tersimpan.")
        self.audit.log("repair_started", case_id, True, policy_decision="needs_confirmation",
                       rule_id=rid, operation="start_service", service=service)

        # 2) TERAPKAN
        aid = self.repo.start_action(case_id, "start_service", {"service": service})
        self.repo.link_snapshot(snap, aid)
        res = self.adapter.apply("start_service", service=service)
        self.repo.finish_action(aid, res.ok, res.exit_code)
        if not res.ok:
            steps.append("Perintah start gagal: " + (res.error or "tanpa pesan")[:200])
            self.audit.log("repair_failed", case_id, True, rule_id=rid, service=service, error=res.error[:200])
            hint = " Layanan berstatus Disabled: mengubah tipe startup perlu keputusan administrator." \
                if before.get("StartType") == "Disabled" else ""
            return RepairResult("failed", f"Layanan {service} tidak dapat dijalankan: {res.error[:200]}.{hint}",
                                aid, snap, steps)
        steps.append("Perintah start berhasil dikirim.")

        # 3) VERIFIKASI
        deadline, state = time.monotonic() + self.verify_timeout, None
        while True:
            state = self._state(service)
            if state and state.get("Status") == "Running":
                break
            if time.monotonic() >= deadline:
                break
            self._sleep(self.poll)
        running = bool(state and state.get("Status") == "Running")
        startup_same = bool(state) and state.get("StartType") == before.get("StartType")
        self.repo.add_verification(case_id, f"service_running:{service}", "pass" if running else "fail",
                                   {"state": state, "startup_unchanged": startup_same})
        if running:
            steps.append("Verifikasi: layanan berjalan.")
            if not startup_same:
                steps.append("PERHATIAN: tipe startup berbeda dari sebelumnya; periksa manual.")
            self.audit.log("repair_verified", case_id, True, rule_id=rid, service=service)
            return RepairResult("verified",
                                f"Layanan {service} berjalan (terverifikasi). Uji ulang koneksi asli untuk memastikan masalahnya hilang.",
                                aid, snap, steps, rollback_available=before.get("Status") == "Stopped")
        steps.append("Verifikasi: layanan TIDAK berjalan setelah perintah start.")
        self.audit.log("repair_unverified", case_id, True, rule_id=rid, service=service)
        return RepairResult("applied_unverified",
                            f"Perintah dikirim tetapi layanan {service} belum terbukti berjalan. Jangan menganggap masalah selesai.",
                            aid, snap, steps, rollback_available=before.get("Status") == "Stopped")

    # -- rollback ---------------------------------------------------------
    def rollback(self, case_id: str, action_id: int, approved: bool) -> RepairResult:
        rid = "rollback"
        if not self.enabled:
            return self._refuse(case_id, rid, "Eksekusi perbaikan belum diaktifkan di pengaturan.")
        if not approved:
            return self._refuse(case_id, rid, "Belum ada persetujuan eksplisit untuk rollback.")
        if not self.adapter.is_elevated():
            return self._refuse(case_id, rid, "Butuh hak administrator.")
        act, snap = self.repo.get_action(action_id), self.repo.snapshot_for_action(action_id)
        if act is None or snap is None or act["case_id"] != case_id:
            return self._refuse(case_id, rid, "Tindakan atau snapshot tidak ditemukan untuk kasus ini.")
        if not snap["restore_supported"]:
            return self._refuse(case_id, rid, "Snapshot ini tidak mendukung pemulihan otomatis.")
        payload = json.loads(snap["payload_json"])
        try:
            service = validate_service(payload["service"])
        except (ValidationError, KeyError):
            return self._refuse(case_id, rid, "Snapshot tidak valid.")
        if payload.get("Status") != "Stopped":
            return self._refuse(case_id, rid, "Keadaan awal bukan 'Stopped'; tidak ada yang perlu dipulihkan.")
        now = self._state(service)
        if now is None:
            return self._refuse(case_id, rid, "Keadaan saat ini tidak terbaca; rollback dibatalkan.")
        if now.get("Status") == "Stopped":
            return RepairResult("noop", f"Layanan {service} sudah Stopped; tidak ada perubahan.")
        aid = self.repo.start_action(case_id, "stop_service", {"service": service, "rollback_of": action_id})
        res = self.adapter.apply("stop_service", service=service)
        self.repo.finish_action(aid, res.ok, res.exit_code)
        if not res.ok:
            self.audit.log("rollback_failed", case_id, True, service=service, error=res.error[:200])
            return RepairResult("failed", f"Rollback gagal: {res.error[:200]}", aid, steps=["Layanan dibiarkan apa adanya."])
        final = self._state(service)
        stopped = bool(final and final.get("Status") == "Stopped")
        self.repo.add_verification(case_id, f"service_stopped:{service}", "pass" if stopped else "fail", {"state": final})
        self.audit.log("rollback_verified" if stopped else "rollback_unverified", case_id, True, service=service)
        return RepairResult("verified" if stopped else "applied_unverified",
                            f"Layanan {service} dikembalikan ke Stopped." if stopped else
                            f"Rollback dikirim tetapi {service} belum terbukti Stopped.", aid)
