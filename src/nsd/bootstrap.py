"""Rakit komponen aplikasi (DB, pengaturan, audit, adapter)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nsd.app_config import DEFAULT_SETTINGS, data_dir, data_dir_warnings, setup_logging
from nsd.application.policy_service import PolicyLevel
from nsd.application.scan_service import ScanService
from nsd.storage.database import open_database
from nsd.storage.repositories import AuditRepository, CaseRepository, SettingsRepository
from nsd.windows.powershell import RealWindowsAdapter


@dataclass
class AppContext:
    data_dir: Path
    cases: CaseRepository
    settings: SettingsRepository
    audit: AuditRepository
    adapter: RealWindowsAdapter
    warnings: list[str]

    def scan_service(self) -> ScanService:
        # Fase 1: level dikunci ke 'Diagnosis saja' apa pun isi pengaturan.
        return ScanService(self.adapter, self.cases, self.audit, level=PolicyLevel.DIAGNOSE_ONLY)


def bootstrap(directory: Path | None = None) -> AppContext:
    d = directory or data_dir()
    setup_logging(d)
    conn = open_database(d / "nsd.sqlite3")
    settings = SettingsRepository(conn, DEFAULT_SETTINGS)
    cases = CaseRepository(conn)
    cases.prune(settings.get("retention_days"), settings.get("retention_max_cases"))
    return AppContext(d, cases, settings, AuditRepository(conn), RealWindowsAdapter(), data_dir_warnings(d))
