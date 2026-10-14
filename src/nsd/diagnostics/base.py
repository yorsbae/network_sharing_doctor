"""Konteks & utilitas bersama untuk pemeriksaan baca-saja."""
from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from nsd.models import CheckResult, Layer, ScanRequest, Status
from nsd.windows.powershell import OpResult, WindowsAdapter


class NetProbe:
    """Probe jaringan murni (tanpa admin). Dipisah agar mudah di-mock."""

    def resolve(self, host: str) -> list[str]:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        seen: list[str] = []
        for info in infos:
            ip = info[4][0]
            if ip not in seen:
                seen.append(ip)
        return seen

    def tcp_connect(self, host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, "connected"
        except socket.timeout:
            return False, "timeout"
        except ConnectionRefusedError:
            return False, "refused"
        except OSError as exc:
            return False, f"error:{exc.__class__.__name__}"


@dataclass
class DiagContext:
    request: ScanRequest
    adapter: WindowsAdapter
    net: NetProbe = field(default_factory=NetProbe)
    local_names: set[str] = field(default_factory=lambda: {"localhost", "127.0.0.1", "::1"})
    results: dict[str, CheckResult] = field(default_factory=dict)
    sensitive: list[tuple[str, str]] = field(default_factory=list)
    os_info: dict[str, Any] | None = None

    def status_of(self, check_id: str) -> Status | None:
        r = self.results.get(check_id)
        return r.status if r else None

    @property
    def is_local_target(self) -> bool:
        return self.request.host.strip().lower() in self.local_names

    def mark_sensitive(self, kind: str, value: str) -> None:
        if value:
            self.sensitive.append((kind, value))


def result(check_id: str, layer: Layer, title: str, status: Status, detail: str, /, **evidence: Any) -> CheckResult:
    return CheckResult(check_id, layer, title, status, detail, dict(evidence))


def op_failure_detail(op: OpResult) -> str:
    if op.timed_out:
        return "Pemeriksaan melewati batas waktu."
    if op.unsupported:
        return op.error or "Tidak didukung di sistem ini."
    return (op.error or "Gagal tanpa pesan.")[:300]


CheckFn = Callable[[DiagContext], list[CheckResult]]


def timed(fn: CheckFn, ctx: DiagContext) -> list[CheckResult]:
    t0 = time.perf_counter()
    try:
        out = fn(ctx)
    except Exception as exc:  # noqa: BLE001 - satu pemeriksaan rusak tak boleh menggagalkan scan
        out = [result(
            f"internal.{fn.__name__}", Layer.CONTEXT, f"Pemeriksaan internal {fn.__name__}",
            Status.UNKNOWN, f"Pemeriksaan tidak dapat dijalankan ({exc.__class__.__name__}).",
        )]
    ms = int((time.perf_counter() - t0) * 1000)
    for r in out:
        r.duration_ms = ms
    return out
