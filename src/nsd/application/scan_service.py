"""Orkestrasi scan: kumpulkan bukti → cocokkan aturan → gerbang kebijakan → simpan kasus."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from nsd.application.policy_service import PolicyLevel, apply_policy
from nsd.diagnostics.base import DiagContext, NetProbe
from nsd.diagnostics.runner import run_all
from nsd.models import CheckResult, Finding, ScanRequest, Status
from nsd.rules.loader import RuleSet, load_rules
from nsd.rules.matcher import match_rules
from nsd.storage.repositories import AuditRepository, CaseRepository
from nsd.windows.powershell import WindowsAdapter


@dataclass
class ScanOutcome:
    case_id: str
    request: ScanRequest
    started: str
    checks: list[CheckResult]
    findings: list[Finding]
    os_info: dict[str, Any] | None
    elevated: bool
    sensitive: list[tuple[str, str]]
    rule_errors: list[str] = field(default_factory=list)
    rules_digest: str = ""

    def count(self, status: Status) -> int:
        return sum(1 for c in self.checks if c.status is status)

    @property
    def overall(self) -> str:
        if self.count(Status.FAIL):
            return "masalah_ditemukan"
        if self.count(Status.WARNING):
            return "perlu_perhatian"
        if self.count(Status.UNKNOWN) == len(self.checks):
            return "tidak_dapat_diperiksa"
        return "tidak_ada_masalah_terbukti"


class ScanService:
    def __init__(self, adapter: WindowsAdapter, cases: CaseRepository | None = None,
                 audit: AuditRepository | None = None, rules: RuleSet | None = None,
                 net: NetProbe | None = None, level: PolicyLevel = PolicyLevel.DIAGNOSE_ONLY,
                 local_names: set[str] | None = None) -> None:
        self.adapter, self.cases, self.audit = adapter, cases, audit
        self.rules = rules or load_rules()
        self.net, self.level = net or NetProbe(), level
        self.local_names = local_names

    def run(self, request: ScanRequest, progress: Callable[[int, int, str], None] | None = None) -> ScanOutcome:
        elevated = self.adapter.is_elevated()
        ctx = DiagContext(request=request, adapter=self.adapter, net=self.net)
        if self.local_names:
            ctx.local_names |= {n.lower() for n in self.local_names}
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        checks = run_all(ctx, progress)
        findings = match_rules(self.rules.rules, ctx.results, request)
        apply_policy(findings, self.level)

        target = request.host + (("\\" + request.share) if request.share else "")
        case_id = "-"
        if self.cases:
            os_sum = (ctx.os_info or {}).get("Caption", "") if ctx.os_info else ""
            case_id = self.cases.create_case(request.role.value, request.target_type.value, target,
                                             request.error_code, str(os_sum), elevated, self.rules.digest)
        outcome = ScanOutcome(case_id, request, started, checks, findings, ctx.os_info, elevated,
                              ctx.sensitive, list(self.rules.errors), self.rules.digest)
        if self.cases:
            self.cases.finish_case(case_id, outcome.overall, checks, findings)
        if self.audit:
            self.audit.log("scan_completed", case_id, elevated, policy_decision="read_only",
                           checks=len(checks), findings=len(findings), rule_errors=len(self.rules.errors),
                           rules_digest=self.rules.digest[:16])
            for e in self.rules.errors:
                self.audit.log("rule_rejected", case_id, elevated, detail=e)
        return outcome
