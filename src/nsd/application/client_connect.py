"""Sisi client: pasang printer bersama dari server ke komputer ini (mengubah profil pengguna ini saja).

Tidak butuh administrator. Hasil diverifikasi dengan membaca daftar printer lokal; perintah yang tidak berefek
dilaporkan "belum terbukti", bukan sukses.
"""
from __future__ import annotations

from dataclasses import dataclass

from nsd.security.allowlist import ValidationError, build_unc
from nsd.windows.powershell import as_list


@dataclass
class ConnectResult:
    outcome: str        # verified | unverified | failed | refused
    message: str


def connect_printer(adapter, host: str, share: str, audit=None) -> ConnectResult:
    try:
        unc = build_unc(host, share)
    except ValidationError as exc:
        return ConnectResult("refused", f"Alamat tidak valid: {exc}")
    res = adapter.apply("add_printer_connection", unc=unc)
    if not res.ok:
        kind = "refused" if res.unsupported else "failed"
        msg = (res.error or "Tanpa pesan.")[:200]
        out = ConnectResult(kind, msg)
    else:
        lst = adapter.run("list_local_printers")
        found = lst.ok and any(isinstance(x, dict) and str(x.get("Name", "")).lower() == unc.lower() for x in as_list(lst.data))
        out = (ConnectResult("verified", f"Printer {unc} terpasang di komputer ini.") if found else
               ConnectResult("unverified", "Perintah terkirim, tetapi printer belum terbaca di daftar printer komputer ini."))
    if audit:
        audit.log("client_connect_printer", None, False, policy_decision="user_approved", unc=unc, outcome=out.outcome)
    return out
