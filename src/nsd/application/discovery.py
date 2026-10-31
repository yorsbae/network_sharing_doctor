"""Cari komputer yang bisa menjadi server di jaringan lokal (dimulai pengguna, BACA-SAJA).

Batas yang disengaja (lihat SECURITY.md):
* hanya subnet /24 dari alamat IPv4 pribadi komputer ini (maksimum 253 alamat),
* hanya satu port: TCP 445 (SMB), dengan sambungan biasa yang langsung ditutup,
* tidak mengirim kredensial, tidak membaca isi share, tidak mengubah apa pun,
* tidak pernah jalan otomatis; hanya saat pengguna menekan tombol cari.
"""
from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable

from nsd.security.allowlist import ValidationError, validate_host

SMB_PORT = 445
Probe = Callable[[str, float], bool]
Namer = Callable[[str], str]


@dataclass
class FoundServer:
    address: str
    name: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.address})" if self.name else self.address

    @property
    def host(self) -> str:
        """Nilai yang dipakai untuk menyambung: nama bila ada, kalau tidak alamat IP."""
        return self.name or self.address


@dataclass
class DiscoveryResult:
    servers: list[FoundServer] = field(default_factory=list)
    scanned: int = 0
    subnets: list[str] = field(default_factory=list)
    note: str = ""
    cancelled: bool = False


def subnet_hosts(address: str) -> list[str]:
    """Alamat lain di /24 yang sama, hanya untuk IPv4 pribadi. Selain itu daftar kosong."""
    try:
        a = ipaddress.ip_address(address)
    except ValueError:
        return []
    if a.version != 4 or not a.is_private or a.is_loopback or a.is_link_local:
        return []
    net = ipaddress.ip_network(f"{address}/24", strict=False)
    return [str(h) for h in net.hosts() if str(h) != address]


def _probe(host: str, timeout: float) -> bool:
    try:
        with socket.create_connection((host, SMB_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def _name(address: str) -> str:
    try:
        raw = socket.gethostbyaddr(address)[0].rstrip(".")
    except OSError:
        return ""
    try:
        return validate_host(raw)
    except ValidationError:
        return ""


def _ip_key(s: FoundServer) -> tuple:
    return tuple(int(p) for p in s.address.split("."))


def discover(local_addresses: list[str], probe: Probe | None = None, namer: Namer | None = None,
             progress: Callable[[int, int], None] | None = None, should_stop: Callable[[], bool] | None = None,
             timeout: float = 0.6, workers: int = 48, name_wait: float = 6.0) -> DiscoveryResult:
    probe, namer = probe or _probe, namer or _name
    res = DiscoveryResult()
    targets: list[str] = []
    for ip in local_addresses:
        hosts = subnet_hosts(ip)
        if hosts:
            res.subnets.append(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
            targets += [h for h in hosts if h not in targets and h not in local_addresses]
    if not targets:
        res.note = ("Tidak ada alamat jaringan lokal (pribadi) yang ditemukan. Sambungkan komputer ke Wi-Fi atau kabel LAN, "
                    "atau ketik nama atau alamat IP server secara manual.")
        return res
    total, found = len(targets), []
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        pending = {pool.submit(probe, t, timeout): t for t in targets}
        while pending:
            if should_stop and should_stop():
                res.cancelled = True
                break
            done, _ = wait(list(pending), timeout=0.2, return_when=FIRST_COMPLETED)
            for f in done:
                t = pending.pop(f)
                res.scanned += 1
                if f.exception() is None and f.result():
                    found.append(t)
            if progress:
                progress(res.scanned, total)
        names = {}
        if found and not res.cancelled:
            futs = {pool.submit(namer, ip): ip for ip in found}
            done, _ = wait(list(futs), timeout=name_wait)
            names = {futs[f]: f.result() for f in done if f.exception() is None}
        res.servers = sorted((FoundServer(ip, names.get(ip, "")) for ip in found), key=_ip_key)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if not res.servers and not res.cancelled:
        res.note = ("Tidak ada komputer dengan layanan berbagi (port 445) di jaringan ini. Pastikan komputer server menyala, "
                    "satu jaringan dengan komputer ini, dan firewall mengizinkan File and Printer Sharing. "
                    "Anda tetap bisa mengetik nama atau alamat IP server secara manual.")
    return res
