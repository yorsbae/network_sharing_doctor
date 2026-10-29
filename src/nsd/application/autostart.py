"""Autostart monitor lewat Windows Task Scheduler (schtasks), bukan Windows Service.

Dua mode:
* logon-user  (default, aman): jalan saat logon sebagai pengguna yang memasang, hak terbatas.
* boot-system (headless)     : jalan saat boot sebagai SYSTEM. BERISIKO bila file yang dijalankan atau
  folder datanya bisa ditulis pengguna biasa (eskalasi hak akses). Karena itu dipaksa: build
  terpaket di Program Files, folder data di ProgramData dengan ACL dikunci (icacls berbasis SID).
Argumen selalu daftar (tanpa shell); nilai divalidasi. Belum diuji di Windows asli.
"""
from __future__ import annotations

import ntpath
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

from nsd.security.allowlist import ValidationError, validate_host, validate_share

TASK_NAME = "NetworkSharingDoctorMonitor"
MODES = ("logon-user", "boot-system")
_SID_SYSTEM, _SID_ADMINS, _SID_USERS = "*S-1-5-18", "*S-1-5-32-544", "*S-1-5-32-545"


@dataclass
class Outcome:
    ok: bool
    message: str


def _norm(p: str) -> str:
    return ntpath.normcase(ntpath.normpath(p))


def is_protected_path(path: str, env: dict[str, str] | None = None) -> bool:
    """True bila path berada di bawah Program Files / Windows (hanya admin yang bisa menulis secara default)."""
    env = env if env is not None else dict(os.environ)
    roots = [env.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "SystemRoot")]
    p = _norm(path)
    for r in filter(None, roots):
        root = _norm(r)
        if p == root or p.startswith(root.rstrip("\\") + "\\"):
            return True
    return False


def _q(value: str) -> str:
    if '"' in value or "\n" in value or "\r" in value:
        raise ValidationError("Nilai mengandung karakter terlarang untuk perintah terjadwal.")
    return f'"{value}"'


def build_task_command(exe: str, *, host: str, share: str, target_type: str, interval: int, data_dir: str | None) -> str:
    if target_type not in ("printer", "folder", "both"):
        raise ValidationError("Jenis target tidak valid.")
    if not 30 <= int(interval) <= 86400:
        raise ValidationError("Interval harus 30–86400 detik.")
    parts = [_q(exe), "monitor", "--role", "server", "--type", target_type, "--host", validate_host(host),
             "--interval", str(int(interval))]
    if share:
        parts += ["--share", _q(validate_share(share))]
    if data_dir:
        parts += ["--data-dir", _q(data_dir)]
    return " ".join(parts)


def build_create_args(mode: str, command: str, env: dict[str, str] | None = None) -> list[str]:
    env = env if env is not None else dict(os.environ)
    exe = ntpath.join(env.get("SystemRoot", r"C:\Windows"), "System32", "schtasks.exe")
    base = [exe, "/Create", "/TN", TASK_NAME, "/TR", command, "/F"]
    if mode == "boot-system":
        return base + ["/SC", "ONSTART", "/DELAY", "0001:00", "/RU", "SYSTEM", "/RL", "HIGHEST"]
    if mode == "logon-user":
        return base + ["/SC", "ONLOGON", "/RL", "LIMITED"]
    raise ValidationError(f"Mode tidak dikenal: {mode}")


def system_data_dir(env: dict[str, str] | None = None) -> str:
    env = env if env is not None else dict(os.environ)
    return ntpath.join(env.get("ProgramData", r"C:\ProgramData"), "NetworkSharingDoctor")


Runner = Callable[..., "subprocess.CompletedProcess"]


def _run(runner: Runner, args: list[str]):
    return runner(args, capture_output=True, text=True, timeout=60, shell=False, check=False)


def install(mode: str, *, host: str, share: str, target_type: str, interval: int,
            exe: str | None = None, frozen: bool | None = None, platform: str | None = None,
            elevated: bool = False, env: dict[str, str] | None = None, runner: Runner = subprocess.run,
            i_understand_risk: bool = False) -> Outcome:
    env = env if env is not None else dict(os.environ)
    if (platform or sys.platform) != "win32":
        return Outcome(False, "Autostart hanya tersedia di Windows.")
    if mode not in MODES:
        return Outcome(False, f"Mode harus salah satu dari {MODES}.")
    if not (frozen if frozen is not None else getattr(sys, "frozen", False)):
        return Outcome(False, "Autostart hanya untuk build terpaket (NSD.exe), bukan skrip Python.")
    exe = exe or sys.executable
    data_dir: str | None = None
    if mode == "boot-system":
        if not elevated:
            return Outcome(False, "Mode boot-system butuh hak administrator.")
        if not is_protected_path(exe, env) and not i_understand_risk:
            return Outcome(False, f"Ditolak: {exe} bukan di Program Files/Windows. Menjalankan file dari folder yang "
                                  "bisa ditulis pengguna biasa sebagai SYSTEM memungkinkan eskalasi hak akses. "
                                  "Pasang di Program Files, atau gunakan mode logon-user.")
        data_dir = system_data_dir(env)
    try:
        cmd = build_task_command(exe, host=host, share=share, target_type=target_type, interval=interval, data_dir=data_dir)
        args = build_create_args(mode, cmd, env)
    except (ValidationError, ValueError) as exc:
        return Outcome(False, f"Parameter tidak valid: {exc}")
    if data_dir:   # kunci ACL folder data SEBELUM tugas dibuat
        os.makedirs(data_dir, exist_ok=True)
        r = _run(runner, [ntpath.join(env.get("SystemRoot", r"C:\Windows"), "System32", "icacls.exe"), data_dir,
                          "/inheritance:r", "/grant:r", f"{_SID_SYSTEM}:(OI)(CI)F", f"{_SID_ADMINS}:(OI)(CI)F",
                          f"{_SID_USERS}:(OI)(CI)RX"])
        if r.returncode != 0:
            return Outcome(False, "Gagal mengunci izin folder data; tugas tidak dibuat: " + (r.stderr or r.stdout)[:200])
    r = _run(runner, args)
    if r.returncode != 0:
        return Outcome(False, "schtasks gagal: " + (r.stderr or r.stdout)[:300])
    return Outcome(True, f"Tugas '{TASK_NAME}' dibuat (mode {mode}). Monitor hanya MEMBACA; tidak ada perbaikan otomatis.")


def uninstall(*, platform: str | None = None, env: dict[str, str] | None = None, runner: Runner = subprocess.run) -> Outcome:
    if (platform or sys.platform) != "win32":
        return Outcome(False, "Autostart hanya tersedia di Windows.")
    env = env if env is not None else dict(os.environ)
    exe = ntpath.join(env.get("SystemRoot", r"C:\Windows"), "System32", "schtasks.exe")
    r = _run(runner, [exe, "/Delete", "/TN", TASK_NAME, "/F"])
    return Outcome(r.returncode == 0, "Tugas dihapus." if r.returncode == 0 else "Gagal/tidak ada tugas: " + (r.stderr or r.stdout)[:200])


def status(*, platform: str | None = None, env: dict[str, str] | None = None, runner: Runner = subprocess.run) -> Outcome:
    if (platform or sys.platform) != "win32":
        return Outcome(False, "Autostart hanya tersedia di Windows.")
    env = env if env is not None else dict(os.environ)
    exe = ntpath.join(env.get("SystemRoot", r"C:\Windows"), "System32", "schtasks.exe")
    r = _run(runner, [exe, "/Query", "/TN", TASK_NAME, "/FO", "LIST"])
    if r.returncode != 0:
        return Outcome(False, "Tugas belum terpasang.")
    return Outcome(True, r.stdout.strip())
