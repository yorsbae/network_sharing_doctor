"""Lapisan Sharing/Driver untuk printer (baca-saja)."""
from __future__ import annotations

from nsd.diagnostics.base import DiagContext, op_failure_detail, result
from nsd.models import CheckResult, Layer, Status
from nsd.windows.powershell import as_list


def classify_printer_error(text: str) -> str:
    t = (text or "").lower()
    if "access is denied" in t or "0x80070005" in t or "unauthorizedaccess" in t:
        return "access_denied"
    if "rpc server is unavailable" in t or "0x800706ba" in t or "1722" in t:
        return "rpc_unavailable"
    if "network path was not found" in t or "0x80070035" in t:
        return "unreachable"
    return "other"


REMOTE_TEXT = {
    "access_denied": "Akses ke spooler server ditolak untuk akun saat ini (belum tentu printer share bermasalah).",
    "rpc_unavailable": "Layanan RPC/Spooler di server tidak dapat dihubungi (firewall atau spooler server mati).",
    "unreachable": "Server tidak terjangkau saat meminta daftar printer.",
    "other": "Daftar printer server tidak dapat dibaca; lihat pesan error.",
}


def _match_share(printers: list[dict], share: str) -> dict | None:
    s = share.lower()
    for p in printers:
        if not isinstance(p, dict):
            continue
        if str(p.get("ShareName") or "").lower() == s or str(p.get("Name") or "").lower() == s:
            return p
    return None


def check_remote_printers(ctx: DiagContext) -> list[CheckResult]:
    """Peran client / target remote: apakah printer share ada di server."""
    req = ctx.request
    if not req.target_type.includes("printer") or ctx.is_local_target and req.role.value == "server":
        return []
    title = "Printer share terdaftar di server"
    if ctx.status_of("net.tcp445") is not Status.PASS:
        return [result("printer.remote_share", Layer.SHARING, title, Status.UNKNOWN,
                       "Dilewati: port SMB belum terbukti terjangkau.")]
    op = ctx.adapter.run("list_remote_printers", host=req.host)
    if op.unsupported or op.timed_out:
        return [result("printer.remote_share", Layer.SHARING, title, Status.UNKNOWN, op_failure_detail(op))]
    if not op.ok:
        cat = classify_printer_error(op.error)
        return [result("printer.remote_share", Layer.AUTH, title, Status.FAIL, REMOTE_TEXT[cat],
                       category=cat, error=op.error[:300])]
    printers = as_list(op.data)
    for p in printers:
        if isinstance(p, dict):
            ctx.mark_sensitive("PRINTER", str(p.get("Name") or ""))
            ctx.mark_sensitive("SHARE", str(p.get("ShareName") or ""))
    shared = [p for p in printers if isinstance(p, dict) and p.get("Shared")]
    if not req.share:
        return [result("printer.remote_share", Layer.SHARING, title,
                       Status.PASS if shared else Status.WARNING,
                       f"Server membagikan {len(shared)} printer.", shared_count=len(shared))]
    hit = _match_share(printers, req.share)
    if hit and hit.get("Shared"):
        return [result("printer.remote_share", Layer.SHARING, title, Status.PASS,
                       "Printer share ditemukan dan berstatus dibagikan.",
                       printer_status=hit.get("Status"), driver=hit.get("Driver"))]
    names = ", ".join(str(p.get("ShareName")) for p in shared[:10] if p.get("ShareName")) or "(tidak ada)"
    return [result("printer.remote_share", Layer.SHARING, title, Status.FAIL,
                   f"Printer share dengan nama itu tidak ditemukan. Share yang ada: {names}.",
                   category="not_found", available=[p.get("ShareName") for p in shared[:10]])]


def check_local_printers(ctx: DiagContext) -> list[CheckResult]:
    """Peran server: printer lokal, status dibagikan, status perangkat."""
    req = ctx.request
    if req.role.value != "server" or not req.target_type.includes("printer"):
        return []
    title = "Printer lokal dibagikan"
    op = ctx.adapter.run("list_local_printers")
    if not op.ok:
        return [result("local.printer_share", Layer.SHARING, title, Status.UNKNOWN, op_failure_detail(op))]
    printers = [p for p in as_list(op.data) if isinstance(p, dict)]
    for p in printers:
        ctx.mark_sensitive("PRINTER", str(p.get("Name") or ""))
        ctx.mark_sensitive("SHARE", str(p.get("ShareName") or ""))
    if not printers:
        return [result("local.printer_share", Layer.SHARING, title, Status.FAIL,
                       "Tidak ada printer terpasang di komputer ini.", category="no_printers", count=0)]
    if not req.share:
        n = sum(1 for p in printers if p.get("Shared"))
        return [result("local.printer_share", Layer.SHARING, title,
                       Status.PASS if n else Status.FAIL,
                       f"{n} dari {len(printers)} printer dibagikan.",
                       category=None if n else "not_shared", shared_count=n)]
    hit = _match_share(printers, req.share)
    if hit is None:
        return [result("local.printer_share", Layer.SHARING, title, Status.FAIL,
                       "Tidak ada printer dengan nama/share tersebut di komputer ini.", category="not_found")]
    out: list[CheckResult] = []
    if not hit.get("Shared"):
        out.append(result("local.printer_share", Layer.SHARING, title, Status.FAIL,
                          "Printer ada, tetapi belum dibagikan.", category="not_shared"))
    else:
        out.append(result("local.printer_share", Layer.SHARING, title, Status.PASS,
                          "Printer ada dan dibagikan.", driver=hit.get("Driver")))
    st = str(hit.get("Status"))
    out.append(result("local.printer_status", Layer.DRIVER, "Status printer normal",
                      Status.PASS if st == "Normal" else Status.WARNING,
                      f"Status printer: {st}.", printer_status=st, driver=hit.get("Driver")))
    return out


def check_printer_connect_not_tested(ctx: DiagContext) -> list[CheckResult]:
    if not ctx.request.target_type.includes("printer"):
        return []
    return [result("printer.connect_test", Layer.FINAL, "Printer benar-benar dapat dipasang/dipakai",
                   Status.UNKNOWN,
                   "Belum diuji: Fase 1 hanya membaca; tidak memasang printer atau mencetak halaman uji.")]
