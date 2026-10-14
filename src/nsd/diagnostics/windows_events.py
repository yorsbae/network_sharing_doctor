"""Event log pencetakan terbaru (baca-saja)."""
from __future__ import annotations

from nsd.diagnostics.base import DiagContext, op_failure_detail, result
from nsd.models import CheckResult, Layer, Status
from nsd.windows.powershell import as_list


def check_print_events(ctx: DiagContext) -> list[CheckResult]:
    if not ctx.request.target_type.includes("printer"):
        return []
    title = "Event error pencetakan 24 jam terakhir"
    op = ctx.adapter.run("recent_print_errors")
    if not op.ok:
        return [result("local.events.print", Layer.POLICY, title, Status.UNKNOWN, op_failure_detail(op))]
    events = as_list(op.data)
    if not events:
        return [result("local.events.print", Layer.POLICY, title, Status.PASS,
                       "Tidak ada event error pada log PrintService/Admin.", count=0)]
    ids = sorted({e.get("Id") for e in events if isinstance(e, dict)})
    return [result("local.events.print", Layer.POLICY, title, Status.WARNING,
                   f"Ditemukan {len(events)} event error terbaru (ID: {', '.join(map(str, ids))}).",
                   count=len(events), event_ids=ids, events=events)]
