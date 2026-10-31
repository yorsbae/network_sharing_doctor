"""Data printer, spooler, dan antrean cetak untuk antarmuka (BACA-SAJA).

Semua dibaca lewat `adapter.run` (operasi baca-saja). Di non-Windows hasilnya `available=False`
dengan alasan, bukan daftar kosong yang menyesatkan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nsd.windows.powershell import as_list

# PrinterStatus Windows -> (teks tampilan, nada). Nada: ok | warn | fail | unknown
_PRINTER_STATUS = {
    "normal": ("Siap", "ok"), "idle": ("Siap", "ok"), "printing": ("Mencetak", "ok"),
    "offline": ("Offline", "warn"), "paused": ("Dijeda", "warn"), "waiting": ("Menunggu", "warn"),
    "error": ("Error", "fail"), "paperjam": ("Kertas macet", "fail"), "paperout": ("Kertas habis", "fail"),
    "tonerlow": ("Toner menipis", "warn"), "doordopen": ("Penutup terbuka", "fail"), "dooropen": ("Penutup terbuka", "fail"),
}
_JOB_STATUS = {
    "printing": ("Mencetak", "ok"), "spooling": ("Memproses", "ok"), "normal": ("Antre", "unknown"),
    "paused": ("Dijeda", "warn"), "error": ("Error", "fail"), "offline": ("Printer offline", "warn"),
    "retained": ("Ditahan", "warn"), "completed": ("Selesai", "ok"), "deleting": ("Dihapus", "unknown"),
}


def _tone(table: dict, raw: str) -> tuple[str, str]:
    key = (raw or "").replace(" ", "").replace("_", "").lower()
    if key in table:
        return table[key]
    for part in (raw or "").replace(",", " ").split():           # mis. "Paused, Error"
        if part.lower() in table and table[part.lower()][1] in ("fail", "warn"):
            return table[part.lower()]
    return (raw or "Tidak diketahui", "unknown")


@dataclass
class PrinterInfo:
    name: str
    status_text: str
    tone: str
    driver: str = ""
    port: str = ""
    shared: bool = False
    share_name: str = ""


@dataclass
class PrintJobInfo:
    job_id: int
    document: str
    printer: str
    status_text: str
    tone: str
    pages: int = 0
    size: int = 0
    submitted: str = ""


@dataclass
class Listing:
    items: list = field(default_factory=list)
    available: bool = True
    reason: str = ""


def _fail(op) -> Listing:
    return Listing([], False, op.error or "Tidak dapat dibaca.")


def _parse_printers(op) -> Listing:
    if not op.ok:
        return _fail(op)
    out = []
    for d in as_list(op.data):
        if isinstance(d, dict) and d.get("Name"):
            text, tone = _tone(_PRINTER_STATUS, str(d.get("Status") or ""))
            out.append(PrinterInfo(str(d["Name"]), text, tone, str(d.get("Driver") or ""), str(d.get("Port") or ""),
                                   bool(d.get("Shared")), str(d.get("ShareName") or "")))
    return Listing(out)


def list_printers(adapter) -> Listing:
    return _parse_printers(adapter.run("list_local_printers"))


def list_remote_printers(adapter, host: str, net=None) -> Listing:
    """Printer yang dibagikan server (BACA-SAJA). Port SMB dicek dulu agar pesan galat jelas, bukan batas waktu PowerShell."""
    from nsd.diagnostics.base import NetProbe
    from nsd.diagnostics.printer import REMOTE_TEXT, classify_printer_error

    ok, reason = (net or NetProbe()).tcp_connect(host, 445)
    if not ok:
        if reason == "error:gaierror":
            return Listing([], False, "Nama komputer tidak ditemukan. Periksa ejaan, atau pakai alamat IP server.")
        return Listing([], False, "Server tidak terjangkau di port SMB (445): komputer mati, beda jaringan, "
                                  "atau firewall memblokir.")
    op = adapter.run("list_remote_printers", host=host)
    if not op.ok:
        if op.unsupported:
            return _fail(op)
        return Listing([], False, REMOTE_TEXT[classify_printer_error(op.error)])
    lst = _parse_printers(op)
    lst.items = [p for p in lst.items if p.shared and p.share_name]
    return lst


def list_jobs(adapter) -> Listing:
    op = adapter.run("list_print_jobs")
    if not op.ok:
        return _fail(op)
    out = []
    for d in as_list(op.data):
        if isinstance(d, dict):
            text, tone = _tone(_JOB_STATUS, str(d.get("Status") or ""))
            out.append(PrintJobInfo(int(d.get("Id") or 0), str(d.get("Document") or "(tanpa nama)"),
                                    str(d.get("Printer") or ""), text, tone, int(d.get("Pages") or 0),
                                    int(d.get("Size") or 0), str(d.get("Submitted") or "").replace("T", " ")))
    return Listing(out)


def spooler_state(adapter) -> tuple[str, str]:
    """(teks, nada) untuk layanan Print Spooler."""
    op = adapter.run("get_service", service="Spooler")
    if not op.ok or not isinstance(op.data, dict):
        return ("Belum diperiksa", "unknown")
    st = str(op.data.get("Status") or "")
    return {"Running": ("Berjalan", "ok"), "Stopped": ("Berhenti", "fail")}.get(st, (st or "Belum diperiksa", "warn"))
