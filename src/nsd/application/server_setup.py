"""Kesiapan komputer ini sebagai server printer sharing (BACA-SAJA) dan alamat yang diberikan ke client.

"Server" di sini hanya berarti komputer yang printernya terpasang dan dibagikan. Tidak ada program
server yang harus berjalan: Windows sendiri yang melayani client lewat layanan Server dan Print Spooler.
Modul ini hanya membaca keadaan dan menyusun petunjuk; tidak mengubah apa pun.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Callable

from nsd.application import printers
from nsd.windows.powershell import as_list


@dataclass
class Step:
    key: str
    title: str
    tone: str                 # ok | warn | fail | unknown
    status: str               # teks status singkat (selalu ada, warna hanya penguat)
    detail: str = ""
    howto: str = ""           # langkah manual bila belum ok dan tidak bisa disiapkan otomatis
    auto: bool = False        # True bila "Siapkan otomatis" bisa memperbaikinya


@dataclass
class SharedPrinter:
    name: str
    share_name: str
    status_text: str
    tone: str
    unc: str                  # \\NAMA\Share


@dataclass
class ServerInfo:
    computer_name: str = ""
    addresses: list[str] = field(default_factory=list)
    printers: list[SharedPrinter] = field(default_factory=list)
    unshared: list[str] = field(default_factory=list)      # nama printer terpasang yang belum dibagikan


@dataclass
class Readiness:
    steps: list[Step]
    info: ServerInfo

    @property
    def verdict(self) -> tuple[str, str]:
        """(teks, nada) untuk keseluruhan."""
        tones = [s.tone for s in self.steps]
        if "fail" in tones:
            return ("Belum siap", "fail")
        if "warn" in tones:
            return ("Perlu perhatian", "warn")
        if tones and all(t == "ok" for t in tones):
            return ("Siap dipakai client", "ok")
        return ("Belum diperiksa", "unknown")

    @property
    def ready(self) -> bool:
        return self.verdict[1] == "ok"


def local_ipv4_addresses(names: Callable[[], list[str]] | None = None, route: Callable[[], str] | None = None) -> list[str]:
    """Alamat IPv4 komputer ini yang berguna bagi client. Alamat rute utama diletakkan lebih dulu."""
    found: list[str] = []

    def add(ip: str) -> None:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return
        if a.version != 4 or a.is_loopback or a.is_link_local or a.is_unspecified or ip in found:
            return
        found.append(ip)

    try:
        add(route() if route else _route_address())
    except OSError:
        pass
    try:
        for ip in (names() if names else _host_addresses()):
            add(ip)
    except OSError:
        pass
    return found


def _route_address() -> str:
    """Alamat yang dipakai rute keluar. Soket UDP yang di-connect tidak mengirim paket apa pun."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))            # TEST-NET-1 (RFC 5737): tidak pernah dirutekan
        return s.getsockname()[0]


def _host_addresses() -> list[str]:
    return [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]


def _unknown(key: str, title: str, reason: str) -> Step:
    return Step(key, title, "unknown", "Belum diperiksa", reason or "Tidak dapat dibaca.")


def _service_step(adapter, key: str, title: str, service: str, howto: str) -> Step:
    op = adapter.run("get_service", service=service)
    if not op.ok or not isinstance(op.data, dict):
        return _unknown(key, title, op.error)
    st = str(op.data.get("Status") or "")
    if st == "Running":
        return Step(key, title, "ok", "Berjalan")
    if st == "Stopped":
        return Step(key, title, "fail", "Berhenti", "Layanan ini harus berjalan agar client bisa menyambung.", howto, auto=True)
    return Step(key, title, "warn", st or "Tidak diketahui", "", howto)


def _profile_step(adapter) -> Step:
    title = "Profil jaringan mendukung sharing"
    op = adapter.run("net_profile")
    if not op.ok:
        return _unknown("profile", title, op.error)
    rows = [r for r in as_list(op.data) if isinstance(r, dict) and r.get("IPv4") != "Disconnected"]
    if not rows:
        return _unknown("profile", title, "Tidak ada koneksi aktif yang terbaca. Sambungkan komputer ke jaringan.")
    cats = sorted({str(r.get("Category")) for r in rows})
    if "Public" in cats:
        return Step("profile", title, "warn", "Publik",
                    "Jaringan berprofil Publik biasanya memblokir akses dari komputer lain.",
                    "Buka Settings > Network & internet, pilih koneksi yang dipakai, lalu ubah jenis jaringan ke Private. "
                    "Jika komputer dikelola organisasi, tanyakan administrator.", auto=True)
    return Step("profile", title, "ok", "Pribadi" if "Private" in cats else ", ".join(cats))


def _firewall_step(adapter) -> Step:
    title = "Firewall mengizinkan File and Printer Sharing"
    op = adapter.run("firewall_sharing")
    if not op.ok:
        return _unknown("firewall", title, op.error)
    rules = [r for r in as_list(op.data) if isinstance(r, dict)]
    if not rules:
        return _unknown("firewall", title, "Aturan tidak terbaca (mungkin firewall pihak ketiga).")
    ok = [r for r in rules if r.get("Enabled") == "True" and r.get("Direction") == "Inbound" and r.get("Action") == "Allow"]
    if ok:
        return Step("firewall", title, "ok", "Aktif", "Firewall pihak ketiga tidak dievaluasi.")
    return Step("firewall", title, "fail", "Nonaktif", "Semua aturan masuk File and Printer Sharing nonaktif.",
                "Buka Control Panel > Windows Defender Firewall > Allow an app, lalu centang File and Printer Sharing "
                "untuk jaringan Private. Jangan mematikan firewall.", auto=True)


_SHARE_HOWTO = ("Buka Settings > Bluetooth & devices > Printers & scanners, pilih printer, Printer properties, tab Sharing, "
                "centang Share this printer, beri nama share tanpa spasi, lalu OK.")


def _printer_step(adapter, computer: str, info: ServerInfo) -> Step:
    title = "Printer terpasang dan dibagikan"
    lst = printers.list_printers(adapter)
    if not lst.available:
        return _unknown("printers", title, lst.reason)
    if not lst.items:
        return Step("printers", title, "fail", "Tidak ada printer", "Belum ada printer terpasang di komputer ini.",
                    "Pasang printer dulu (kabel USB atau jaringan), pastikan bisa mencetak halaman uji dari komputer ini, "
                    "lalu bagikan.")
    shared = [p for p in lst.items if p.shared and p.share_name]
    info.unshared = [p.name for p in lst.items if not (p.shared and p.share_name)]
    for p in shared:
        info.printers.append(SharedPrinter(p.name, p.share_name, p.status_text, p.tone, f"\\\\{computer}\\{p.share_name}"))
    if not shared:
        return Step("printers", title, "fail", "Belum dibagikan",
                    f"{len(lst.items)} printer terpasang, tidak ada yang dibagikan.", _SHARE_HOWTO, auto=True)
    bad = [p for p in shared if p.tone in ("fail", "warn")]
    if bad:
        return Step("printers", title, "warn", f"{len(shared)} dibagikan",
                    "Perlu dicek: " + ", ".join(f"{p.name} ({p.status_text})" for p in bad) + ".",
                    "Periksa kertas, kabel, dan status printer di Printers & scanners.")
    return Step("printers", title, "ok", f"{len(shared)} dibagikan")


def check_readiness(adapter, addresses: Callable[[], list[str]] | None = None) -> Readiness:
    """Periksa kesiapan komputer ini sebagai server. Hanya operasi baca-saja pada adapter."""
    name = ""
    op = adapter.run("os_info")
    if op.ok and isinstance(op.data, dict):
        name = str(op.data.get("ComputerName") or "")
    if not name:
        try:
            name = socket.gethostname()
        except OSError:
            name = ""
    info = ServerInfo(name, (addresses or local_ipv4_addresses)())
    steps = [
        _service_step(adapter, "spooler", "Print Spooler berjalan", "Spooler",
                      "Buka Services (services.msc), cari Print Spooler, klik kanan, Start. "
                      "Atau gunakan Perbaiki otomatis dari halaman Scan printer."),
        _service_step(adapter, "server_svc", "Layanan Server (berbagi file dan printer) berjalan", "LanmanServer",
                      "Buka Services (services.msc), cari Server, klik kanan, Start."),
        _profile_step(adapter),
        _firewall_step(adapter),
        _printer_step(adapter, name or "NAMA-KOMPUTER", info),
    ]
    return Readiness(steps, info)


def client_instructions(info: ServerInfo) -> str:
    """Teks siap tempel untuk dikirim ke pengguna client (tanpa data sensitif selain alamat yang memang diberikan)."""
    if not info.printers:
        return ""
    first = info.printers[0]
    ip = info.addresses[0] if info.addresses else ""
    lines = ["Cara memakai printer dari komputer lain", "",
             "1. Pastikan komputer Anda tersambung ke jaringan yang sama (Wi-Fi atau kabel LAN) dengan komputer printer.",
             "2. Tekan tombol Windows + R, tempel alamat di bawah ini, lalu tekan Enter:"]
    lines += [f"   {p.unc}" for p in info.printers]
    if ip:
        lines.append(f"   Jika nama tidak ditemukan, pakai alamat IP: \\\\{ip}\\{first.share_name}")
    lines += ["3. Klik dua kali printer yang muncul dan tunggu sampai driver terpasang.",
              "4. Jika gagal, buka Network Sharing Doctor, menu Client, isi alamat di atas, lalu klik Periksa koneksi."]
    return "\n".join(lines)
