"""Lapisan SMB / jalur UNC folder."""
from __future__ import annotations

import re

from nsd.diagnostics.base import DiagContext, op_failure_detail, result
from nsd.models import CheckResult, Layer, Status
from nsd.security.allowlist import build_unc

_WIN32_FACILITY = 7


def classify_unc_error(error_type: str | None, hresult: int | None, message: str | None) -> str:
    """Kategori kegagalan akses UNC. Kode saja tidak cukup; gabungkan tipe & pesan."""
    msg = (message or "").lower()
    code = None
    if hresult:
        h = hresult & 0xFFFFFFFF
        if (h >> 16) & 0x1FFF == _WIN32_FACILITY:
            code = h & 0xFFFF
    if code == 5 or error_type == "UnauthorizedAccessException" or "access is denied" in msg:
        return "access_denied"
    if code == 1326 or "user name or password" in msg or "logon failure" in msg:
        return "logon_failure"
    if code == 1219 or "multiple connections" in msg:
        return "credential_conflict"
    if code == 67 or "network name cannot be found" in msg:
        return "bad_net_name"
    if code in (53, 1203, 1231) or "network path was not found" in msg:
        return "unreachable"
    if error_type in ("ItemNotFoundException", "DirectoryNotFoundException") or "does not exist" in msg:
        return "not_found"
    return "other"


_UNC_TEXT = {
    "access_denied": "Akses ditolak: server terjangkau, tetapi akun saat ini tidak punya izin (cek izin share DAN izin NTFS).",
    "logon_failure": "Autentikasi gagal: nama pengguna/kata sandi tidak diterima server.",
    "credential_conflict": "Sudah ada koneksi ke server ini dengan kredensial lain; putuskan koneksi lama lalu coba lagi.",
    "bad_net_name": "Server ditemukan, tetapi nama share tidak ada.",
    "not_found": "Jalur tidak ditemukan: nama share atau subfolder tidak ada/tidak dibagikan.",
    "unreachable": "Jalur jaringan tidak ditemukan: server tidak terjangkau melalui SMB.",
    "other": "Akses gagal dengan penyebab yang belum terklasifikasi; lihat pesan error lengkap di laporan.",
}


def check_unc_access(ctx: DiagContext) -> list[CheckResult]:
    req = ctx.request
    if not req.target_type.includes("folder") or not req.share:
        return []
    title = "Jalur folder (UNC) dapat dibuka"
    if ctx.status_of("net.tcp445") is not Status.PASS:
        return [result("smb.unc", Layer.SHARING, title, Status.UNKNOWN,
                       "Dilewati: port SMB belum terbukti terjangkau.")]
    unc = build_unc(req.host, req.share)
    op = ctx.adapter.run("test_unc", unc=unc)
    if op.unsupported or op.timed_out or not op.ok or not isinstance(op.data, dict):
        return [result("smb.unc", Layer.SHARING, title, Status.UNKNOWN, op_failure_detail(op),
                       unc=unc, timed_out=op.timed_out)]
    d = op.data
    if d.get("Ok"):
        return [result("smb.unc", Layer.SHARING, title, Status.PASS,
                       "Isi folder dapat dibaca oleh akun saat ini.", unc=unc)]
    cat = classify_unc_error(d.get("ErrorType"), d.get("HResult"), d.get("Message"))
    h = d.get("HResult")
    msg = re.sub(r"\s+", " ", str(d.get("Message") or ""))[:300]
    return [result("smb.unc", Layer.SHARING, title, Status.FAIL, _UNC_TEXT[cat],
                   category=cat, unc=unc, error_type=d.get("ErrorType"),
                   hresult=("0x%08X" % (h & 0xFFFFFFFF)) if isinstance(h, int) else None,
                   message=msg)]
