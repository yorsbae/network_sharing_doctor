"""Lokasi data, pengaturan bawaan, dan logging."""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path

APP_DIRNAME = "NetworkSharingDoctor"
DEFAULT_SETTINGS: dict = {
    "role": "client",
    "role_chosen": False,        # False sampai pengguna memilih peran di Dashboard (menampilkan ajakan memilih)
    "last_server": "",           # server terakhir yang dipakai di halaman Client
    "language": "id",
    "theme": "dark",             # system | light | dark
    "policy_level": 1,         # Fase 1: hanya 'Diagnosis saja'
    "execution_enabled": False,  # Fase 2: harus diaktifkan eksplisit oleh pengguna
    "redact_exports": True,
    "retention_days": 180,
    "retention_max_cases": 500,
}


def _exe_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()


def data_dir() -> Path:
    override = os.environ.get("NSD_DATA_DIR")
    if override:
        p = Path(override)
    elif (_exe_dir() / "portable.flag").exists():
        p = _exe_dir() / "data"
    elif sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_DIRNAME
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / APP_DIRNAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir_warnings(path: Path) -> list[str]:
    """Peringatkan bila data portabel berada di drive jaringan (bisa dibaca/ditulis pihak lain)."""
    warns: list[str] = []
    s = str(path)
    if s.startswith("\\\\"):
        warns.append("Folder data berada di jalur jaringan (UNC); riwayat dapat terbaca pengguna lain.")
    elif sys.platform == "win32":
        try:
            import ctypes

            if ctypes.windll.kernel32.GetDriveTypeW(path.drive + "\\") == 4:  # DRIVE_REMOTE
                warns.append("Folder data berada di drive jaringan; riwayat dapat terbaca pengguna lain.")
        except Exception:  # noqa: BLE001
            pass
    return warns


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname,
                   "event": record.getMessage()}
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(directory: Path) -> logging.Logger:
    log = logging.getLogger("nsd")
    if not log.handlers:
        h = logging.handlers.RotatingFileHandler(
            directory / "nsd.log", maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
        h.setFormatter(_JsonFormatter())
        log.addHandler(h)
        log.setLevel(logging.INFO)
    return log
