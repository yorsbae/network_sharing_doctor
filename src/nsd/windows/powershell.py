"""Adapter Windows: operasi bertipe lewat PowerShell.

Aturan keamanan:
* Skrip adalah konstanta di bawah ini; tidak ada skrip dari input pengguna/aturan.
* Parameter divalidasi (allowlist.py) dan dikirim lewat variabel lingkungan
  NSD_P_*, tidak pernah disisipkan ke teks skrip.
* subprocess dengan daftar argumen, tanpa shell=True, dengan timeout dan batas output.
* Path powershell.exe eksplisit di System32 (bukan dari PATH).
* `run()` hanya mengenal operasi BACA-SAJA. Operasi pengubah hanya lewat `apply()`,
  yang menolak kecuali `allow_mutation=True` dan proses berjalan sebagai administrator.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from nsd.security.allowlist import (
    ValidationError,
    validate_host,
    validate_printer_name,
    validate_service,
    validate_share_plain,
    validate_unc,
)
from nsd.windows.privilege import is_elevated

MAX_OUTPUT_BYTES = 256 * 1024
_PS_PREFIX = (
    "$ErrorActionPreference='Stop'; "
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
)


@dataclass
class OpResult:
    ok: bool
    data: Any = None
    error: str = ""
    unsupported: bool = False
    timed_out: bool = False
    exit_code: int | None = None


class WindowsAdapter(Protocol):
    def run(self, operation: str, **params: str) -> OpResult: ...
    def apply(self, operation: str, **params: str) -> OpResult: ...
    def is_windows(self) -> bool: ...
    def is_elevated(self) -> bool: ...


@dataclass(frozen=True)
class ReadOp:
    script: str
    params: dict[str, Callable[[str], str]] = field(default_factory=dict)
    timeout: int = 20


_PRINTER_PROJ = (
    "ForEach-Object { [pscustomobject]@{Name=$_.Name;Driver=$_.DriverName;Port=$_.PortName;"
    "Shared=[bool]$_.Shared;ShareName=$_.ShareName;Status=$_.PrinterStatus.ToString()} }"
)

_SVC_STATE = (
    "$s=Get-Service -Name $env:NSD_P_SERVICE; "
    "[pscustomobject]@{Name=$s.Name;Status=$s.Status.ToString();StartType=$s.StartType.ToString()} "
    "| ConvertTo-Json -Compress"
)

_NET_PROFILE = (
    "@(Get-NetConnectionProfile | ForEach-Object { [pscustomobject]@{"
    "Category=$_.NetworkCategory.ToString();IPv4=$_.IPv4Connectivity.ToString()} }) "
    "| ConvertTo-Json -Compress"
)
_FW_GROUP = "Get-NetFirewallRule -Group '@FirewallAPI.dll,-32752'"
_FIREWALL_SHARING = (
    f"@({_FW_GROUP} | ForEach-Object {{ [pscustomobject]@{{"
    "Enabled=$_.Enabled.ToString();Direction=$_.Direction.ToString();"
    "Action=$_.Action.ToString();Profile=$_.Profile.ToString()} }) | ConvertTo-Json -Compress"
)

READ_OPERATIONS: dict[str, ReadOp] = {
    "os_info": ReadOp(
        "$os=Get-CimInstance Win32_OperatingSystem; $cs=Get-CimInstance Win32_ComputerSystem; "
        "[pscustomobject]@{Caption=$os.Caption;Version=$os.Version;Build=$os.BuildNumber;"
        "ComputerName=$cs.Name;PartOfDomain=[bool]$cs.PartOfDomain;Domain=$cs.Domain} "
        "| ConvertTo-Json -Compress"
    ),
    "get_service": ReadOp(_SVC_STATE, {"service": validate_service}),
    "net_profile": ReadOp(_NET_PROFILE),
    # Grup 'File and Printer Sharing'. ID resource HARUS divalidasi di VM Windows
    # (lihat docs/test-matrix.md); hasil kosong dilaporkan sebagai 'belum diperiksa'.
    "firewall_sharing": ReadOp(_FIREWALL_SHARING),
    "smb_client_config": ReadOp(
        "Get-SmbClientConfiguration | Select-Object EnableInsecureGuestLogons,"
        "RequireSecuritySignature,EnableSecuritySignature | ConvertTo-Json -Compress"
    ),
    "smb_server_config": ReadOp(
        "Get-SmbServerConfiguration | Select-Object EnableSMB1Protocol,EnableSMB2Protocol,"
        "RequireSecuritySignature | ConvertTo-Json -Compress"
    ),
    "list_local_printers": ReadOp(f"@(Get-Printer | {_PRINTER_PROJ}) | ConvertTo-Json -Compress"),
    "list_remote_printers": ReadOp(
        f"@(Get-Printer -ComputerName $env:NSD_P_HOST | {_PRINTER_PROJ}) | ConvertTo-Json -Compress",
        {"host": validate_host},
        timeout=30,
    ),
    # Antrean cetak (BACA-SAJA): tidak menjeda/membatalkan/menghapus pekerjaan apa pun.
    "list_print_jobs": ReadOp(
        "@(Get-Printer | ForEach-Object { $p=$_.Name; Get-PrintJob -PrinterName $p -ErrorAction SilentlyContinue "
        "| ForEach-Object { [pscustomobject]@{Id=$_.Id;Document=$_.DocumentName;Printer=$p;"
        "Status=$_.JobStatus.ToString();Pages=$_.TotalPages;Size=$_.Size;Submitted=$_.SubmittedTime.ToString('s');"
        "Owner=$_.UserName;Client=$_.ComputerName} } }) "
        "| ConvertTo-Json -Compress",
        timeout=30,
    ),
    # Koneksi masuk ke komputer ini (BACA-SAJA). Get-SmbSession butuh admin; TCP 445 tidak.
    "list_smb_sessions": ReadOp(
        "@(Get-SmbSession | ForEach-Object { [pscustomobject]@{Client=$_.ClientComputerName;"
        "User=$_.ClientUserName;Opens=$_.NumOpens} }) | ConvertTo-Json -Compress"
    ),
    "list_smb_connections": ReadOp(
        "@(Get-NetTCPConnection -LocalPort 445 -State Established -ErrorAction SilentlyContinue "
        "| ForEach-Object { [pscustomobject]@{Client=$_.RemoteAddress;User=$null;Opens=$null} }) "
        "| ConvertTo-Json -Compress"
    ),
    "list_local_shares": ReadOp(
        "@(Get-SmbShare | ForEach-Object { [pscustomobject]@{Name=$_.Name;Special=[bool]$_.Special} }) "
        "| ConvertTo-Json -Compress"
    ),
    "test_unc": ReadOp(
        "$r=$null; try { $null=Get-ChildItem -LiteralPath $env:NSD_P_UNC -ErrorAction Stop "
        "| Select-Object -First 1; $r=[pscustomobject]@{Ok=$true;ErrorType=$null;HResult=0;Message=$null} } "
        "catch { $r=[pscustomobject]@{Ok=$false;ErrorType=$_.Exception.GetType().Name;"
        "HResult=$_.Exception.HResult;Message=$_.Exception.Message} }; $r | ConvertTo-Json -Compress",
        {"unc": validate_unc},
        timeout=30,
    ),
    "recent_print_errors": ReadOp(
        "$r=@(); try { $r=@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-PrintService/Admin';"
        "Level=2;StartTime=(Get-Date).AddDays(-1)} -MaxEvents 5 | ForEach-Object { "
        "$m=($_.Message -replace '\\s+',' '); [pscustomobject]@{Id=$_.Id;Time=$_.TimeCreated.ToString('s');"
        "Message=$m.Substring(0,[Math]::Min(200,$m.Length))} }) } "
        "catch { if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { throw } }; "
        "$r | ConvertTo-Json -Compress"
    ),
}

# Operasi PENGUBAH (Fase 2). Tanpa -Force: layanan dependen tidak dihentikan paksa.
# Tipe startup TIDAK pernah diubah.
MUTATING_OPERATIONS: dict[str, ReadOp] = {
    "start_service": ReadOp(
        "Start-Service -Name $env:NSD_P_SERVICE -ErrorAction Stop; " + _SVC_STATE,
        {"service": validate_service}, timeout=45),
    # Persiapan server. Tidak pernah mematikan firewall, tidak menyentuh profil Public pada aturan firewall,
    # dan hanya mengubah koneksi yang sedang aktif dari Public ke Private.
    "set_network_private": ReadOp(
        "Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' -and $_.IPv4Connectivity -ne 'Disconnected' } "
        "| ForEach-Object { Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private -ErrorAction Stop }; "
        + _NET_PROFILE, timeout=45),
    "enable_sharing_firewall": ReadOp(
        f"{_FW_GROUP} -Direction Inbound | Where-Object {{ $p=$_.Profile.ToString(); $p -match 'Private|Domain' "
        "-and $p -notmatch 'Public|Any' } | Enable-NetFirewallRule -ErrorAction Stop; " + _FIREWALL_SHARING, timeout=45),
    "share_printer": ReadOp(
        "Set-Printer -Name $env:NSD_P_PRINTER -Shared $true -ShareName $env:NSD_P_SHARE -ErrorAction Stop; "
        f"@(Get-Printer -Name $env:NSD_P_PRINTER | {_PRINTER_PROJ}) | ConvertTo-Json -Compress",
        {"printer": validate_printer_name, "share": validate_share_plain}, timeout=45),
    "stop_service": ReadOp(
        "Stop-Service -Name $env:NSD_P_SERVICE -ErrorAction Stop; " + _SVC_STATE,
        {"service": validate_service}, timeout=45),
}


def _powershell_exe() -> str:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


class RealWindowsAdapter:
    def __init__(self, platform: str | None = None, allow_mutation: bool = False) -> None:
        self._platform = platform or sys.platform
        self.allow_mutation = allow_mutation

    def is_windows(self) -> bool:
        return self._platform == "win32"

    def is_elevated(self) -> bool:
        return is_elevated()

    def run(self, operation: str, **params: str) -> OpResult:
        """Hanya operasi BACA-SAJA."""
        spec = READ_OPERATIONS.get(operation)
        if spec is None:
            return OpResult(False, error=f"Operasi tidak diizinkan: {operation}", unsupported=True)
        return self._execute(operation, spec, params)

    def apply(self, operation: str, **params: str) -> OpResult:
        """Operasi PENGUBAH. Ditolak kecuali eksekusi diaktifkan dan proses elevated."""
        spec = MUTATING_OPERATIONS.get(operation)
        if spec is None:
            return OpResult(False, error=f"Operasi pengubah tidak diizinkan: {operation}", unsupported=True)
        if not self.allow_mutation:
            return OpResult(False, error="Eksekusi perubahan dinonaktifkan.", unsupported=True)
        if not self.is_windows():
            return OpResult(False, error="Hanya tersedia di Windows.", unsupported=True)
        if not self.is_elevated():
            return OpResult(False, error="Butuh hak administrator.", unsupported=True)
        return self._execute(operation, spec, params)

    def _execute(self, operation: str, spec: ReadOp, params: dict) -> OpResult:
        if not self.is_windows():
            return OpResult(False, error="Pemeriksaan ini hanya tersedia di Windows.", unsupported=True)
        unknown = set(params) - set(spec.params)
        if unknown:
            raise ValidationError(f"Parameter tidak dikenal untuk {operation}: {sorted(unknown)}")
        env = dict(os.environ)
        for name, validator in spec.params.items():
            if name not in params:
                raise ValidationError(f"Parameter wajib hilang untuk {operation}: {name}")
            env[f"NSD_P_{name.upper()}"] = validator(str(params[name]))

        args = [_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", _PS_PREFIX + spec.script]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(  # noqa: S603 - argumen daftar, skrip konstan
                args, capture_output=True, timeout=spec.timeout, env=env,
                shell=False, creationflags=flags, check=False,
            )
        except subprocess.TimeoutExpired:
            return OpResult(False, error=f"Waktu habis ({spec.timeout}s).", timed_out=True)
        except OSError as exc:
            return OpResult(False, error=f"PowerShell tidak dapat dijalankan: {exc}")

        stdout = proc.stdout[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace").strip()
        stderr = proc.stderr[:4000].decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return OpResult(False, error=(stderr or stdout)[:500], exit_code=proc.returncode)
        if not stdout:
            return OpResult(True, data=None, exit_code=0)
        try:
            return OpResult(True, data=json.loads(stdout), exit_code=0)
        except json.JSONDecodeError:
            return OpResult(False, error="Keluaran PowerShell bukan JSON yang valid.", exit_code=0)


def as_list(data: Any) -> list:
    """PowerShell menyederhanakan array 1 elemen menjadi objek; samakan kembali."""
    if data is None:
        return []
    return data if isinstance(data, list) else [data]
