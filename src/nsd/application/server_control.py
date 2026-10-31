"""Kendali "server" NSD: jalankan / hentikan proses `nsd serve` di latar belakang.

`nsd serve` = pemantau aktivitas (siapa menyambung / mencetak, ditulis ke activity.jsonl) + monitor kesehatan
(status.json). Keduanya BACA-SAJA. Windows sendiri tetap yang melayani client; proses ini hanya mengamati.
Berhenti lewat berkas penanda `server.stop` (lintas-platform, tanpa membunuh proses).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from nsd.application.activity_service import ActivityWatcher
from nsd.application.monitor_service import MAX_INTERVAL, MIN_INTERVAL, MonitorService, SingleInstance
from nsd.security.allowlist import validate_host, validate_share

LOCK, STOP, STATUS = "server.lock", "server.stop", "server_status.json"
MIN_POLL, MAX_POLL = 1, 60
_DETACHED = 0x00000008 | 0x00000200 | 0x08000000   # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW


def is_running(data_dir: Path) -> bool:
    probe = SingleInstance(Path(data_dir) / LOCK)
    if probe.acquire():
        probe.release()
        return False
    return True


def read_status(data_dir: Path) -> dict | None:
    try:
        return json.loads((Path(data_dir) / STATUS).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_serve_argv(*, frozen: bool, exe: str, host: str = "localhost", share: str = "", target_type: str = "printer",
                     interval: int = 300, poll: int = 3) -> list[str]:
    if target_type not in ("printer", "folder", "both"):
        raise ValueError("Jenis target tidak valid.")
    if not MIN_INTERVAL <= int(interval) <= MAX_INTERVAL:
        raise ValueError(f"Interval harus {MIN_INTERVAL}–{MAX_INTERVAL} detik.")
    if not MIN_POLL <= int(poll) <= MAX_POLL:
        raise ValueError(f"Poll harus {MIN_POLL}–{MAX_POLL} detik.")
    argv = ([exe] if frozen else [exe, "-m", "nsd"]) + [
        "serve", "--role", "server", "--type", target_type, "--host", validate_host(host),
        "--interval", str(int(interval)), "--poll", str(int(poll))]
    if share:
        argv += ["--share", validate_share(share)]
    return argv


def start(data_dir: Path, *, host: str = "localhost", share: str = "", target_type: str = "printer", interval: int = 300,
          poll: int = 3, frozen: bool | None = None, exe: str | None = None, platform: str | None = None,
          spawn: Callable[..., object] = subprocess.Popen) -> str:
    data_dir = Path(data_dir)
    if is_running(data_dir):
        return "Server sudah berjalan."
    try:
        (data_dir / STOP).unlink()
    except OSError:
        pass
    argv = build_serve_argv(frozen=frozen if frozen is not None else bool(getattr(sys, "frozen", False)),
                            exe=exe or sys.executable, host=host, share=share, target_type=target_type,
                            interval=interval, poll=poll)
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                "shell": False, "close_fds": True}
    if (platform or sys.platform) == "win32":
        kw["creationflags"] = _DETACHED
    else:
        kw["start_new_session"] = True
    env = dict(os.environ, NSD_DATA_DIR=str(data_dir))      # proses anak memakai folder data yang sama
    spawn(argv, env=env, **kw)
    return "Server dijalankan di latar belakang."


def stop(data_dir: Path, wait: float = 0.0) -> str:
    data_dir = Path(data_dir)
    if not is_running(data_dir):
        return "Server tidak sedang berjalan."
    (data_dir / STOP).write_text(str(time.time()), encoding="utf-8")
    end = time.monotonic() + wait
    while wait and time.monotonic() < end and is_running(data_dir):
        time.sleep(0.1)
    return "Server dihentikan." if not is_running(data_dir) else "Permintaan berhenti dikirim; server berhenti sebentar lagi."


def _write_status(data_dir: Path, **doc) -> None:
    tmp = data_dir / (STATUS + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, data_dir / STATUS)


def run_serve(data_dir: Path, watcher: ActivityWatcher, monitor: MonitorService | None, *, poll: int = 3,
              stop_event: threading.Event | None = None, max_ticks: int | None = None) -> int:
    """Loop utama proses server. Mengembalikan 3 bila server lain sudah berjalan."""
    data_dir = Path(data_dir)
    lock = SingleInstance(data_dir / LOCK)
    if not lock.acquire():
        return 3
    stop_ev = stop_event or threading.Event()
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        try:
            (data_dir / STOP).unlink()
        except OSError:
            pass
        watcher.emit("server_start")
        if monitor is not None:     # monitor di thread sendiri agar scan lambat tidak menunda log aktivitas
            def _mon() -> None:
                try:
                    monitor.run_forever(stop_ev)
                except Exception:  # noqa: BLE001
                    pass
            threading.Thread(target=_mon, name="nsd-monitor", daemon=True).start()
        ticks = 0
        while not stop_ev.is_set():
            try:
                watcher.tick()
            except Exception as exc:  # noqa: BLE001 - satu putaran gagal tidak mematikan server
                watcher.emit("warn", message=f"Putaran gagal: {exc.__class__.__name__}")
            ticks += 1
            _write_status(data_dir, running=True, pid=os.getpid(), started_at=started, poll_seconds=poll, ticks=ticks,
                          updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"), read_only=True)
            if (data_dir / STOP).exists() or (max_ticks is not None and ticks >= max_ticks):
                break
            stop_ev.wait(poll)
        stop_ev.set()
        watcher.emit("server_stop")
        _write_status(data_dir, running=False, pid=os.getpid(), started_at=started, poll_seconds=poll, ticks=ticks,
                      updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"), read_only=True)
        try:
            (data_dir / STOP).unlink()
        except OSError:
            pass
        return 0
    finally:
        lock.release()
