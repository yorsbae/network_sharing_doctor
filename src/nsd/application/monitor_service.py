"""Monitor latar belakang BACA-SAJA (opsional).

* Hanya memakai ScanService.run() → adapter.run(); tidak pernah memanggil apply() / perbaikan.
* Tidak menyimpan kasus tiap putaran: hanya saat status BERUBAH (setelah dikonfirmasi) agar
  riwayat tidak penuh dan retensi tidak menghapus bukti penting.
* Debounce: perubahan baru dianggap nyata bila terlihat pada `confirm_ticks` putaran berturut-turut.
* status.json ditulis atomik; berisi ringkasan, bukan bukti mentah.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsd import __version__
from nsd.application.scan_service import ScanOutcome, ScanService
from nsd.models import ScanRequest, Status
from nsd.storage.repositories import AuditRepository

log = logging.getLogger("nsd.monitor")
MIN_INTERVAL = 30
MAX_INTERVAL = 86400


def signature(o: ScanOutcome) -> tuple[str, ...]:
    """Pemeriksaan yang tidak lulus (id:status). 'Lulus' tidak masuk agar stabil."""
    return tuple(sorted(f"{c.id}:{c.status.value}" for c in o.checks if c.status is not Status.PASS))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class MonitorState:
    overall: str
    sig: tuple[str, ...]
    since: str
    case_id: str = "-"


@dataclass
class MonitorService:
    scan: ScanService
    request: ScanRequest
    data_dir: Path
    audit: AuditRepository | None = None
    interval: int = 300
    confirm_ticks: int = 2
    state: MonitorState | None = None
    _pending: tuple[str, ...] | None = field(default=None, repr=False)
    _pending_n: int = field(default=0, repr=False)
    ticks: int = 0

    def __post_init__(self) -> None:
        if not MIN_INTERVAL <= self.interval <= MAX_INTERVAL:
            raise ValueError(f"interval harus {MIN_INTERVAL}–{MAX_INTERVAL} detik")

    # -- satu putaran -----------------------------------------------------
    def tick(self) -> MonitorState:
        out = self.scan.run(self.request, persist=False)
        sig = signature(out)
        self.ticks += 1
        if self.state is None:                                  # baseline
            self.scan.save(out)
            self.state = MonitorState(out.overall, sig, _now(), out.case_id)
            self._event("monitor_baseline", out, overall=out.overall, problems=len(sig))
        elif sig == self.state.sig:
            self._pending, self._pending_n = None, 0
        else:
            self._pending_n = self._pending_n + 1 if sig == self._pending else 1
            self._pending = sig
            if self._pending_n >= self.confirm_ticks:
                old = self.state
                self.scan.save(out)                             # simpan bukti saat berubah
                self.state = MonitorState(out.overall, sig, _now(), out.case_id)
                self._pending, self._pending_n = None, 0
                recovered = not sig and bool(old.sig)
                self._event("monitor_recovered" if recovered else "monitor_state_changed", out,
                            from_overall=old.overall, to_overall=out.overall,
                            added=sorted(set(sig) - set(old.sig)), removed=sorted(set(old.sig) - set(sig)))
                (log.info if recovered else log.warning)("status berubah: %s -> %s", old.overall, out.overall)
        self._write_status(out)
        return self.state

    def _event(self, name: str, out: ScanOutcome, **detail: Any) -> None:
        if self.audit:
            self.audit.log(name, out.case_id, out.elevated, policy_decision="read_only", **detail)

    # -- status.json ------------------------------------------------------
    def _write_status(self, out: ScanOutcome) -> None:
        st = self.state
        assert st is not None
        doc = {
            "app_version": __version__, "pid": os.getpid(), "read_only": True,
            "updated_at": _now(), "interval_seconds": self.interval, "ticks": self.ticks,
            "target": {"role": self.request.role.value, "type": self.request.target_type.value,
                       "host": self.request.host, "share": self.request.share},
            "state": {"overall": st.overall, "since": st.since, "case_id": st.case_id,
                      "pending_change": self._pending is not None},
            "problems": [{"id": c.id, "status": c.status.value, "detail": c.detail}
                         for c in out.checks if c.status in (Status.FAIL, Status.WARNING)],
            "unknown_checks": sum(1 for c in out.checks if c.status is Status.UNKNOWN),
            "findings": [{"rule_id": f.rule_id, "title": f.title, "confidence": f.confidence}
                         for f in out.findings],
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.data_dir / "status.json.tmp"
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.data_dir / "status.json")

    # -- loop -------------------------------------------------------------
    def run_forever(self, stop: threading.Event, max_ticks: int | None = None) -> None:
        if self.audit:
            self.audit.log("monitor_started", policy_decision="read_only", interval=self.interval,
                           host=self.request.host, share=self.request.share)
        errors = 0
        while not stop.is_set():
            try:
                self.tick()
                errors = 0
            except Exception as exc:  # noqa: BLE001 - monitor tidak boleh mati karena satu putaran
                errors += 1
                log.error("putaran monitor gagal: %s", exc.__class__.__name__)
                if self.audit and errors in (1, 10, 100):      # batasi banjir audit
                    self.audit.log("monitor_error", policy_decision="read_only", error=exc.__class__.__name__, consecutive=errors)
            if max_ticks is not None and self.ticks + errors >= max_ticks:
                break
            stop.wait(min(self.interval * (2 ** min(errors, 3)) if errors else self.interval, MAX_INTERVAL))
        if self.audit:
            self.audit.log("monitor_stopped", policy_decision="read_only")


class SingleInstance:
    """Cegah dua monitor berjalan bersamaan (kunci berkas non-blocking)."""

    def __init__(self, path: Path) -> None:
        self.path, self._fh = Path(path), None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        fh.seek(0); fh.truncate(); fh.write(str(os.getpid())); fh.flush()
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None
