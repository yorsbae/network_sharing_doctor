"""Teks tampilan yang dipakai lebih dari satu halaman."""
from __future__ import annotations

ROLE_LABELS = {
    "client": "Client (komputer yang mengakses)",
    "server": "Server (komputer yang membagikan)",
}


def fmt_time(iso_utc: str) -> str:
    """'2026-10-29T08:45:00Z' (UTC) -> waktu lokal '29/10/2026 15:45'."""
    from datetime import datetime

    try:
        return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except (ValueError, AttributeError):
        return iso_utc or "-"


# Status hasil kasus (kolom cases.status) -> (teks, nada)
CASE_TONES = {
    "tidak_ada_masalah_terbukti": ("Tidak ada masalah", "ok"),
    "perlu_perhatian": ("Perlu perhatian", "warn"),
    "masalah_ditemukan": ("Masalah ditemukan", "fail"),
    "running": ("Berjalan", "unknown"),
    "tidak_dapat_diperiksa": ("Belum diperiksa", "unknown"),
}


def case_tone(status: str) -> tuple[str, str]:
    if status in CASE_TONES:
        return CASE_TONES[status]
    low = status.lower()
    tone = "fail" if "masalah" in low and "tidak" not in low else "warn" if "perhatian" in low else "unknown"
    return status.replace("_", " ").capitalize(), tone
