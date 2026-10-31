"""Validasi parameter dan allowlist operasi.

Tidak ada string shell yang dibangun dari input pengguna: semua nilai
divalidasi di sini dan diteruskan lewat variabel lingkungan / argumen.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Callable


class ValidationError(ValueError):
    """Parameter tidak lolos validasi."""


_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
_HOST_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})*$")
# Karakter shell/PowerShell yang berbahaya ikut ditolak (defense-in-depth; nilai tetap hanya
# dikirim lewat variabel lingkungan). Trade-off: share bernama mis. "R&D" tidak didukung di Fase 1.
_SHARE_FORBIDDEN = set('\\/:*?"<>|\'`;&%^!{}()[]~#@,=+')


def validate_host(value: str) -> str:
    v = (value or "").strip()
    if not v or len(v) > 253:
        raise ValidationError("Nama komputer/alamat IP kosong atau terlalu panjang.")
    if "%" in v:
        raise ValidationError("Zone ID tidak didukung.")
    try:
        ipaddress.ip_address(v)
        return v
    except ValueError:
        pass
    if not _HOST_RE.match(v):
        raise ValidationError(
            "Nama komputer hanya boleh berisi huruf, angka, '-' dan '.' (atau alamat IP yang valid)."
        )
    return v


def validate_share(value: str) -> str:
    v = (value or "").strip()
    if not v or len(v) > 80:
        raise ValidationError("Nama share kosong atau lebih dari 80 karakter.")
    for ch in v:
        if ch in _SHARE_FORBIDDEN or ord(ch) < 32:
            raise ValidationError(f"Nama share mengandung karakter terlarang: {ch!r}.")
    if "$" in v[:-1]:
        raise ValidationError("Karakter '$' hanya boleh di akhir nama share (share administratif).")
    if v.endswith((".", " ")):
        raise ValidationError("Nama share tidak boleh berakhir dengan titik/spasi.")
    return v


def build_unc(host: str, share: str) -> str:
    return "\\\\" + validate_host(host) + "\\" + validate_share(share)


def validate_unc(value: str) -> str:
    if not value.startswith("\\\\"):
        raise ValidationError("Jalur UNC harus diawali \\\\.")
    parts = value[2:].split("\\")
    if len(parts) != 2:
        raise ValidationError("Jalur UNC harus berbentuk \\\\HOST\\SHARE.")
    return build_unc(parts[0], parts[1])


def validate_printer_name(value: str) -> str:
    """Nama printer Windows (bebas, tetapi tanpa karakter kontrol). Hanya dikirim lewat variabel lingkungan."""
    v = (value or "").strip()
    if not v or len(v) > 200 or any(ord(ch) < 32 for ch in v):
        raise ValidationError("Nama printer kosong, terlalu panjang, atau memuat karakter kontrol.")
    return v


def validate_share_plain(value: str) -> str:
    """Nama share untuk printer yang dibagikan otomatis: aturan validate_share, tanpa spasi."""
    v = validate_share(value)
    if " " in v:
        raise ValidationError("Nama share tidak boleh memuat spasi.")
    return v


ALLOWED_SERVICES = frozenset(
    {"Spooler", "LanmanWorkstation", "LanmanServer", "FDResPub", "fdPHost", "Dnscache"}
)


def validate_service(value: str) -> str:
    if value not in ALLOWED_SERVICES:
        raise ValidationError(f"Layanan tidak ada dalam allowlist: {value!r}.")
    return value


# --- Allowlist operasi untuk aturan (aksi bertipe) -------------------------

_CONTEXT_TOKENS = {"$selected_printer", "$target_share"}


def _firewall_group(v: str) -> str:
    if v != "file_and_printer_sharing":
        raise ValidationError("Grup firewall tidak diizinkan.")
    return v


def _context_token(v: str) -> str:
    if v not in _CONTEXT_TOKENS:
        raise ValidationError("Token konteks tidak dikenal.")
    return v


def _advice_text(v: str) -> str:
    if not v or len(v) > 400:
        raise ValidationError("Teks saran kosong atau terlalu panjang.")
    return v


@dataclass(frozen=True)
class OperationSpec:
    mutating: bool
    params: dict[str, Callable[[str], str]]


ALLOWED_OPERATIONS: dict[str, OperationSpec] = {
    # tanpa perubahan
    "advise": OperationSpec(False, {"text": _advice_text}),
    # mengubah sistem (Fase 2+; di Fase 1 hanya disarankan, tidak pernah dieksekusi)
    "start_service": OperationSpec(True, {"service_name": validate_service}),
    "enable_specific_firewall_rule": OperationSpec(True, {"group": _firewall_group}),
    "share_printer": OperationSpec(True, {"printer_name": _context_token, "share_name": _context_token}),
    "set_network_profile_private": OperationSpec(True, {}),
}

# Nama operasi yang TIDAK PERNAH boleh muncul di aturan (spesifikasi §3).
FORBIDDEN_OPERATIONS = frozenset(
    {
        "disable_firewall",
        "enable_smb1",
        "enable_insecure_guest",
        "disable_smb_signing",
        "grant_everyone_full_control",
        "recursive_acl_rewrite",
        "reset_all_network_settings",
        "delete_all_printer_drivers",
        "weaken_point_and_print",
        "install_untrusted_driver",
        "run_shell",
        "run_powershell",
    }
)


def validate_action(action: dict) -> list[str]:
    """Kembalikan daftar kesalahan untuk satu aksi aturan (kosong = valid)."""
    errors: list[str] = []
    op = action.get("operation")
    if op in FORBIDDEN_OPERATIONS:
        return [f"operasi terlarang: {op}"]
    spec = ALLOWED_OPERATIONS.get(op)
    if spec is None:
        return [f"operasi tidak ada di allowlist: {op!r}"]
    given = {k: v for k, v in action.items() if k != "operation"}
    for name in given:
        if name not in spec.params:
            errors.append(f"{op}: parameter tidak dikenal {name!r}")
    for name, validator in spec.params.items():
        if name not in given:
            errors.append(f"{op}: parameter wajib {name!r} tidak ada")
            continue
        try:
            validator(str(given[name]))
        except ValidationError as exc:
            errors.append(f"{op}.{name}: {exc}")
    return errors
