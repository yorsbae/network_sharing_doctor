"""Urutan pemeriksaan baca-saja. Urutan mengikuti lapisan, bukan berhenti saat ping lulus."""
from __future__ import annotations

from typing import Callable

from nsd.diagnostics import local, network, printer, smb, spooler, windows_events
from nsd.diagnostics.base import CheckFn, DiagContext, timed
from nsd.models import CheckResult

PIPELINE: list[CheckFn] = [
    network.check_target,
    local.check_os,
    local.check_privilege,
    network.check_dns,
    network.check_tcp_445,
    network.check_tcp_135,
    smb.check_unc_access,
    printer.check_remote_printers,
    spooler.check_workstation,
    spooler.check_server_service,
    spooler.check_spooler,
    spooler.check_fdres,
    local.check_profile,
    local.check_firewall,
    local.check_smb_client,
    local.check_smb_server,
    local.check_local_folder_share,
    printer.check_local_printers,
    windows_events.check_print_events,
    printer.check_printer_connect_not_tested,
]

Progress = Callable[[int, int, str], None]


def run_all(ctx: DiagContext, progress: Progress | None = None) -> list[CheckResult]:
    ordered: list[CheckResult] = []
    total = len(PIPELINE)
    for i, fn in enumerate(PIPELINE, start=1):
        if progress:
            progress(i - 1, total, fn.__name__)
        for r in timed(fn, ctx):
            ctx.results[r.id] = r
            ordered.append(r)
    if progress:
        progress(total, total, "selesai")
    return ordered
