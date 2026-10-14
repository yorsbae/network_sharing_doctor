"""Pemeriksaan layanan Windows (Spooler, Workstation, Server, dll.)."""
from __future__ import annotations

from nsd.diagnostics.base import DiagContext, op_failure_detail, result
from nsd.models import CheckResult, Layer, Status


def _service(ctx: DiagContext, check_id: str, service: str, title: str, layer: Layer,
             stopped_is_fail: bool = True) -> list[CheckResult]:
    op = ctx.adapter.run("get_service", service=service)
    if not op.ok or not isinstance(op.data, dict):
        return [result(check_id, layer, title, Status.UNKNOWN, op_failure_detail(op), service=service)]
    state = str(op.data.get("Status"))
    start = str(op.data.get("StartType"))
    ev = {"service": service, "state": state, "start_type": start}
    if state == "Running":
        return [result(check_id, layer, title, Status.PASS, f"Layanan {service} berjalan.", **ev)]
    if state == "Stopped":
        status = Status.FAIL if stopped_is_fail else Status.WARNING
        extra = " Tipe startup 'Disabled' berarti perubahan startup perlu keputusan administrator." if start == "Disabled" else ""
        return [result(check_id, layer, title, status, f"Layanan {service} berhenti.{extra}", **ev)]
    return [result(check_id, layer, title, Status.WARNING, f"Layanan {service} berstatus {state}.", **ev)]


def check_workstation(ctx: DiagContext) -> list[CheckResult]:
    return _service(ctx, "local.svc.workstation", "LanmanWorkstation",
                    "Layanan Workstation (klien SMB) berjalan", Layer.SERVICE)


def check_server_service(ctx: DiagContext) -> list[CheckResult]:
    if ctx.request.role.value != "server":
        return []
    return _service(ctx, "local.svc.server", "LanmanServer",
                    "Layanan Server (berbagi SMB) berjalan", Layer.SERVICE)


def check_spooler(ctx: DiagContext) -> list[CheckResult]:
    if not ctx.request.target_type.includes("printer"):
        return []
    return _service(ctx, "local.svc.spooler", "Spooler", "Layanan Print Spooler berjalan", Layer.DRIVER)


def check_fdres(ctx: DiagContext) -> list[CheckResult]:
    if ctx.request.role.value != "server":
        return []
    return _service(ctx, "local.svc.fdres", "FDResPub",
                    "Layanan publikasi penemuan (Function Discovery Resource Publication)",
                    Layer.SERVICE, stopped_is_fail=False)
