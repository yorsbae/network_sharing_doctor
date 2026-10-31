"""Siapkan komputer ini sebagai server printer otomatis (mengubah sistem, hanya setelah pengguna menyetujui).

Urutan: rencana dari hasil pemeriksaan kesiapan -> pengguna memilih -> terapkan satu per satu -> verifikasi
ulang tiap langkah -> catat audit. Hanya operasi di allowlist adapter (`start_service`, `set_network_private`,
`enable_sharing_firewall`, `share_printer`). Tidak pernah mematikan firewall atau mengubah tipe startup layanan.
Perubahan ini tidak punya rollback otomatis; keadaan awal dicatat di log audit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from nsd.application.server_setup import Readiness
from nsd.security.allowlist import ValidationError, validate_share_plain
from nsd.windows.powershell import as_list

VIRTUAL_PRINTER = re.compile(r"pdf|xps|onenote|fax|anydesk|virtual", re.I)
_SERVICE_LABEL = {"spooler": ("Spooler", "Nyalakan layanan Print Spooler"),
                  "server_svc": ("LanmanServer", "Nyalakan layanan Server (berbagi file dan printer)")}


@dataclass
class PrepareAction:
    key: str                       # unik: spooler | server_svc | profile | firewall | share:<printer>
    label: str
    op: str
    params: dict = field(default_factory=dict)
    default_on: bool = True


@dataclass
class ActionResult:
    action: PrepareAction
    outcome: str                   # verified | failed | unverified | refused
    message: str


def suggest_share_name(printer: str, taken: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]", "", printer.replace(" ", ""))[:40] or "Printer"
    name, n = base, 2
    while name.lower() in {t.lower() for t in taken}:
        name, n = f"{base}{n}", n + 1
    try:
        return validate_share_plain(name)
    except ValidationError:
        return "Printer"


def plan(r: Readiness, existing_shares: set[str] | None = None) -> list[PrepareAction]:
    """Aksi untuk langkah yang belum ok dan bisa disiapkan otomatis. Urutan: layanan, jaringan, firewall, printer."""
    acts: list[PrepareAction] = []
    by = {s.key: s for s in r.steps}
    for key in ("spooler", "server_svc"):
        s = by.get(key)
        if s and s.auto and s.tone != "ok":
            svc, label = _SERVICE_LABEL[key]
            acts.append(PrepareAction(key, label, "start_service", {"service": svc}))
    if (s := by.get("profile")) and s.auto and s.tone != "ok":
        acts.append(PrepareAction("profile", "Ubah jaringan aktif dari Publik ke Private", "set_network_private"))
    if (s := by.get("firewall")) and s.auto and s.tone != "ok":
        acts.append(PrepareAction("firewall", "Aktifkan aturan firewall File and Printer Sharing (Private dan Domain)",
                                  "enable_sharing_firewall"))
    s = by.get("printers")
    if s and s.auto and s.tone != "ok":
        taken = set(existing_shares or ()) | {p.share_name for p in r.info.printers}
        for name in r.info.unshared:
            share = suggest_share_name(name, taken)
            taken.add(share)
            acts.append(PrepareAction(f"share:{name}", f"Bagikan printer {name} sebagai {share}", "share_printer",
                                      {"printer": name, "share": share}, default_on=not VIRTUAL_PRINTER.search(name)))
    return acts


def _verify(adapter, a: PrepareAction) -> tuple[bool, str]:
    if a.op == "start_service":
        d = adapter.run("get_service", service=a.params["service"])
        ok = d.ok and isinstance(d.data, dict) and d.data.get("Status") == "Running"
        return ok, "Layanan berjalan." if ok else "Layanan belum berjalan."
    if a.op == "set_network_private":
        d = adapter.run("net_profile")
        rows = [x for x in as_list(d.data) if isinstance(x, dict) and x.get("IPv4") != "Disconnected"]
        ok = d.ok and bool(rows) and all(x.get("Category") != "Public" for x in rows)
        return ok, "Jaringan aktif berprofil Private." if ok else "Masih ada jaringan berprofil Publik."
    if a.op == "enable_sharing_firewall":
        d = adapter.run("firewall_sharing")
        ok = d.ok and any(isinstance(x, dict) and x.get("Enabled") == "True" and x.get("Direction") == "Inbound"
                          and x.get("Action") == "Allow" for x in as_list(d.data))
        return ok, "Aturan masuk sudah aktif." if ok else "Belum ada aturan masuk yang aktif."
    if a.op == "share_printer":
        d = adapter.run("list_local_printers")
        ok = d.ok and any(isinstance(x, dict) and x.get("Name") == a.params["printer"] and x.get("Shared")
                          and x.get("ShareName") == a.params["share"] for x in as_list(d.data))
        return ok, "Printer dibagikan." if ok else "Printer belum tercatat dibagikan."
    return False, "Operasi tidak dikenal."


def apply(adapter, actions: list[PrepareAction], audit=None, sleep: Callable[[float], None] | None = None,
          retries: int = 5) -> list[ActionResult]:
    """Terapkan aksi terpilih. Satu aksi gagal tidak menghentikan yang lain; hasil dilaporkan jujur per aksi."""
    import time
    sleep = sleep or time.sleep
    out: list[ActionResult] = []
    elevated = bool(adapter.is_elevated())
    for a in actions:
        res = adapter.apply(a.op, **a.params)
        if not res.ok:
            kind = "refused" if res.unsupported else "failed"
            out.append(ActionResult(a, kind, (res.error or "Tanpa pesan.")[:200]))
        else:
            ok, msg = False, ""
            for i in range(max(1, retries)):         # layanan/profil kadang butuh beberapa detik
                ok, msg = _verify(adapter, a)
                if ok or i == retries - 1:
                    break
                sleep(1.0)
            out.append(ActionResult(a, "verified" if ok else "unverified", msg))
        if audit:
            audit.log("server_prepare", None, elevated, policy_decision="user_approved", action=a.key,
                      operation=a.op, outcome=out[-1].outcome)
    return out
