"""Alur satu klik: `NSD.exe` / `NSD-Start.bat` -> pasang autostart (sekali) -> nyalakan monitor -> buka GUI.

Pembagian peran (tetap BACA-SAJA, tidak ada perbaikan otomatis):
* sisi server : proses `monitor` di latar belakang, tanpa jendela, satu instans per folder data.
* sisi klien  : GUI PySide6, satu instans per folder data (klik ganda tidak membuka dua jendela).
* autostart   : Task Scheduler mode logon-user (hak terbatas), dipasang otomatis dan idempoten
                hanya untuk build terpaket (NSD.exe); butuh opt-out `--no-autostart`.
Seluruh langkah dikembalikan sebagai daftar pesan agar mudah diuji; kegagalan satu langkah
tidak menghentikan langkah lain.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from nsd.application import autostart
from nsd.application.monitor_service import MAX_INTERVAL, MIN_INTERVAL, SingleInstance
from nsd.security.allowlist import validate_host, validate_share

_DETACHED = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW


@dataclass
class LaunchReport:
    steps: list[str] = field(default_factory=list)
    gui_started: bool = False
    exit_code: int = 0

    def add(self, msg: str) -> None:
        self.steps.append(msg)


def lock_held(lock_path: Path) -> bool:
    """True bila proses lain sedang memegang kunci (tanpa mengambilnya)."""
    probe = SingleInstance(lock_path)
    if probe.acquire():
        probe.release()
        return False
    return True


def build_monitor_argv(*, frozen: bool, exe: str, host: str, share: str, target_type: str, interval: int) -> list[str]:
    if target_type not in ("printer", "folder", "both"):
        raise ValueError("Jenis target tidak valid.")
    if not MIN_INTERVAL <= int(interval) <= MAX_INTERVAL:
        raise ValueError(f"Interval harus {MIN_INTERVAL}–{MAX_INTERVAL} detik.")
    base = [exe] if frozen else [exe, "-m", "nsd"]
    argv = base + ["monitor", "--role", "server", "--type", target_type, "--host", validate_host(host),
                   "--interval", str(int(interval))]
    if share:
        argv += ["--share", validate_share(share)]
    return argv


def start_monitor(data_dir: Path, *, host: str, share: str, target_type: str, interval: int,
                  frozen: bool | None = None, exe: str | None = None, platform: str | None = None,
                  spawn: Callable[..., object] = subprocess.Popen) -> str:
    if lock_held(data_dir / "monitor.lock"):
        return "Monitor sudah berjalan (dipakai ulang)."
    is_frozen = frozen if frozen is not None else bool(getattr(sys, "frozen", False))
    argv = build_monitor_argv(frozen=is_frozen, exe=exe or sys.executable, host=host, share=share,
                              target_type=target_type, interval=interval)
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                "shell": False, "close_fds": True}
    if (platform or sys.platform) == "win32":
        kw["creationflags"] = _DETACHED
    else:
        kw["start_new_session"] = True
    spawn(argv, **kw)
    return "Monitor dinyalakan di latar belakang."


def ensure_autostart(*, frozen: bool | None = None, platform: str | None = None, host: str, share: str,
                     target_type: str, interval: int) -> str:
    if (platform or sys.platform) != "win32":
        return "Autostart dilewati (hanya Windows)."
    if not (frozen if frozen is not None else getattr(sys, "frozen", False)):
        return "Autostart dilewati (hanya build terpaket NSD.exe)."
    if autostart.status().ok:
        return "Autostart sudah terpasang."
    res = autostart.install("logon-user", host=host, share=share, target_type=target_type, interval=interval)
    return ("Autostart dipasang: monitor jalan otomatis saat Anda login." if res.ok
            else "Autostart gagal dipasang: " + res.message)


def launch(data_dir: Path, *, host: str = "localhost", share: str = "", target_type: str = "both",
           interval: int = 300, with_gui: bool = True, with_monitor: bool = True, with_autostart: bool = True,
           run_gui: Callable[[], int] | None = None, **kw) -> LaunchReport:
    rep = LaunchReport()
    if with_autostart:
        try:
            rep.add(ensure_autostart(host=host, share=share, target_type=target_type, interval=interval,
                                     **{k: v for k, v in kw.items() if k in ("frozen", "platform")}))
        except Exception as exc:  # noqa: BLE001 - satu langkah gagal tidak menghentikan yang lain
            rep.add(f"Autostart gagal: {exc.__class__.__name__}")
    if with_monitor:
        try:
            rep.add(start_monitor(data_dir, host=host, share=share, target_type=target_type, interval=interval, **kw))
        except ValueError as exc:
            rep.add(f"Monitor tidak dinyalakan: {exc}")
            rep.exit_code = 2
        except OSError as exc:
            rep.add(f"Monitor gagal dinyalakan: {exc.__class__.__name__}")
            rep.exit_code = 1
    if with_gui:
        gui_lock = SingleInstance(data_dir / "gui.lock")
        if not gui_lock.acquire():
            rep.add("Jendela NSD sudah terbuka.")
            return rep
        try:
            if run_gui is None:
                from nsd.ui.main_window import run_gui as _run
                run_gui = _run
            rep.gui_started = True
            rep.exit_code = run_gui() or rep.exit_code
        finally:
            gui_lock.release()
    return rep
