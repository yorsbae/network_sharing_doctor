"""Lapisan Target, Jaringan, dan Resolusi nama."""
from __future__ import annotations

import ipaddress

from nsd.diagnostics.base import DiagContext, result
from nsd.models import CheckResult, Layer, Status
from nsd.security.allowlist import ValidationError, validate_host, validate_share


def check_target(ctx: DiagContext) -> list[CheckResult]:
    req = ctx.request
    problems: list[str] = []
    try:
        validate_host(req.host)
    except ValidationError as exc:
        problems.append(str(exc))
    needs_share = req.role.value == "client" or bool(req.share)
    if needs_share and not req.share:
        problems.append("Nama share belum diisi.")
    elif req.share:
        try:
            validate_share(req.share)
        except ValidationError as exc:
            problems.append(str(exc))
    if problems:
        return [result("target.input", Layer.TARGET, "Target dan jalur share valid", Status.FAIL,
                       " ".join(problems), problems=problems)]
    ctx.mark_sensitive("HOST", req.host)
    if req.share:
        ctx.mark_sensitive("SHARE", req.share)
    return [result("target.input", Layer.TARGET, "Target dan jalur share valid", Status.PASS,
                   "Target diperiksa: peran %s, jenis %s." % (req.role.value, req.target_type.value))]


def check_dns(ctx: DiagContext) -> list[CheckResult]:
    title = "Nama server dapat diresolusikan"
    if ctx.status_of("target.input") is not Status.PASS:
        return [result("net.dns", Layer.NAME, title, Status.UNKNOWN, "Dilewati: target tidak valid.")]
    host = ctx.request.host
    try:
        ipaddress.ip_address(host)
        return [result("net.dns", Layer.NAME, title, Status.PASS,
                       "Target berupa alamat IP; resolusi nama tidak diperlukan "
                       "(resolusi nama TIDAK teruji).", literal_ip=True)]
    except ValueError:
        pass
    try:
        ips = ctx.net.resolve(host)
    except OSError as exc:
        return [result("net.dns", Layer.NAME, title, Status.FAIL,
                       "Nama komputer tidak dapat diresolusikan menjadi alamat IP.",
                       error=exc.__class__.__name__)]
    for ip in ips:
        ctx.mark_sensitive("IP", ip)
    return [result("net.dns", Layer.NAME, title, Status.PASS,
                   "Nama diresolusikan ke %d alamat." % len(ips), addresses=ips)]


def _tcp(ctx: DiagContext, check_id: str, port: int, title: str, decisive: bool) -> list[CheckResult]:
    if ctx.status_of("net.dns") is not Status.PASS:
        return [result(check_id, Layer.NETWORK, title, Status.UNKNOWN,
                       "Dilewati: nama server belum bisa diresolusikan.", port=port)]
    ok, reason = ctx.net.tcp_connect(ctx.request.host, port)
    if ok:
        return [result(check_id, Layer.NETWORK, title, Status.PASS,
                       f"Port TCP {port} dapat dihubungi (bukan sekadar ping).", port=port)]
    status = Status.FAIL if decisive else Status.WARNING
    hint = {
        "timeout": "tidak ada balasan (kemungkinan diblokir firewall atau host mati)",
        "refused": "ditolak (layanan tidak mendengarkan di port ini)",
    }.get(reason, "tidak dapat dijangkau")
    return [result(check_id, Layer.NETWORK, title, status,
                   f"Port TCP {port}: {hint}.", port=port, reason=reason)]


def check_tcp_445(ctx: DiagContext) -> list[CheckResult]:
    return _tcp(ctx, "net.tcp445", 445, "Port SMB (TCP 445) dapat dijangkau", decisive=True)


def check_tcp_135(ctx: DiagContext) -> list[CheckResult]:
    if not ctx.request.target_type.includes("printer"):
        return []
    return _tcp(ctx, "net.tcp135", 135, "Port RPC Endpoint Mapper (TCP 135) dapat dijangkau", decisive=False)
