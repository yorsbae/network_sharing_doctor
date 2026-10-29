"""Laporan teks/JSON. Disamarkan secara default; menyatakan dengan jelas bahwa tidak ada perubahan."""
from __future__ import annotations

import json
from typing import Any

from nsd import __version__
from nsd.application.scan_service import ScanOutcome
from nsd.models import Status
from nsd.security.redaction import Redactor

_OVERALL = {
    "masalah_ditemukan": "Masalah ditemukan",
    "perlu_perhatian": "Ada hal yang perlu perhatian",
    "tidak_dapat_diperiksa": "Tidak dapat diperiksa (hampir semua pemeriksaan tidak tersedia)",
    "tidak_ada_masalah_terbukti": "Tidak ada masalah yang terbukti pada pemeriksaan yang dijalankan",
}
_ORDER = [(Status.FAIL, "Masalah ditemukan"), (Status.WARNING, "Peringatan"),
          (Status.PASS, "Lulus"), (Status.UNKNOWN, "Belum diperiksa")]


def make_redactor(o: ScanOutcome) -> Redactor:
    r = Redactor()
    r.add("HOST", o.request.host)
    r.add("SHARE", o.request.share)
    for kind, value in o.sensitive:
        r.add(kind, value)
    return r


def build_text(o: ScanOutcome, redact: bool = True) -> str:
    L: list[str] = []
    a = L.append
    a(f"LAPORAN DIAGNOSIS: Network Sharing Doctor v{__version__}")
    a(f"ID kasus   : {o.case_id}")
    a(f"Waktu (UTC): {o.started}")
    osi = o.os_info or {}
    a(f"Windows    : {osi.get('Caption', 'tidak terbaca')} (build {osi.get('Build', '?')})")
    a(f"Peran PC   : {o.request.role.value}   Hak admin: {'ya' if o.elevated else 'tidak'}")
    a(f"Target     : jenis={o.request.target_type.value} host={o.request.host} share={o.request.share or '-'}")
    a(f"Kode error : {o.request.error_code or '-'}   Teks: {o.request.error_text[:200] or '-'}")
    a("")
    a(f"Ringkasan  : {_OVERALL[o.overall]}")
    a("             " + ", ".join(f"{s.label_id}={o.count(s)}" for s, _ in _ORDER))
    a("Catatan     : Fase 1 bersifat BACA-SAJA. Tidak ada perubahan yang dilakukan pada sistem ini.")
    a("")
    for status, heading in _ORDER:
        rows = [c for c in o.checks if c.status is status]
        if not rows:
            continue
        a(f"== {heading} ({len(rows)}) ==")
        for c in rows:
            a(f"{status.tag} {c.id}: {c.title}  [{c.layer.value}]")
            a(f"    {c.detail}")
            ev = {k: v for k, v in c.evidence.items() if k not in ("events",)}
            if ev and status in (Status.FAIL, Status.WARNING):
                a("    bukti: " + json.dumps(ev, ensure_ascii=False, default=str)[:400])
        a("")
    a("== Kemungkinan penyebab dan langkah yang disarankan ==")
    if not o.findings:
        a("Tidak ada aturan yang cocok dengan bukti. Itu bukan bukti bahwa tidak ada masalah;")
        a("lihat pemeriksaan 'Belum diperiksa' dan jalankan ulang dengan hak/lingkungan yang sesuai.")
    for i, f in enumerate(o.findings, 1):
        a(f"{i}. {f.title}  (keyakinan: {f.confidence}; risiko: {f.risk}; aturan {f.rule_id} v{f.version})")
        a(f"   {f.explanation}")
        if f.matched_conditions:
            a("   Bukti: " + "; ".join(f.matched_conditions))
        if f.matched_error_code:
            a("   Kode error yang Anda masukkan sesuai dengan aturan ini.")
        for act in f.actions:
            if act["operation"] == "advise":
                a(f"   Saran: {act['text']}")
            else:
                params = {k: v for k, v in act.items() if k != "operation"}
                a(f"   Tindakan yang DISARANKAN (belum diterapkan): {act['operation']} {params}")
        a(f"   Status: {f.lifecycle}. {f.decision_text}")
        if any(x["operation"] != "advise" for x in f.actions):
            a(f"   Butuh admin: {'ya' if f.requires_admin else 'tidak'}; rollback: {f.rollback.get('type')}")
            a("   Verifikasi setelah perbaikan: " + ", ".join(f.verification))
        a(f"   Jika belum berhasil: {f.escalation}")
    if o.rule_errors:
        a("")
        a(f"Peringatan: {len(o.rule_errors)} aturan ditolak karena tidak valid dan tidak dipakai.")
    text = "\n".join(L) + "\n"
    return make_redactor(o).redact(text) if redact else text


def build_json(o: ScanOutcome, redact: bool = True) -> str:
    doc: dict[str, Any] = {
        "app_version": __version__, "case_id": o.case_id, "started_utc": o.started,
        "request": {"role": o.request.role.value, "target_type": o.request.target_type.value,
                    "host": o.request.host, "share": o.request.share, "error_code": o.request.error_code},
        "elevated": o.elevated, "overall": o.overall, "read_only": True,
        "rules_digest": o.rules_digest,
        "checks": [c.to_dict() for c in o.checks], "findings": [f.to_dict() for f in o.findings],
    }
    if redact:
        doc = make_redactor(o).redact_obj(doc)
    return json.dumps(doc, ensure_ascii=False, indent=2, default=str)
