"""Akses data. Evidence disaring dari rahasia sebelum disimpan."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from nsd.models import CheckResult, Finding
from nsd.security.redaction import redact_secrets


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dump(obj: Any) -> str:
    return redact_secrets(json.dumps(obj, ensure_ascii=False, default=str))


class CaseRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_case(self, role: str, target_type: str, target: str, error_code: str,
                    os_summary: str, elevated: bool, rules_digest: str) -> str:
        cid = uuid.uuid4().hex[:12]
        with self.conn:
            self.conn.execute(
                "INSERT INTO cases(id,started_at,role,target_type,target,error_code,os_summary,elevated,status,rules_digest)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (cid, now_iso(), role, target_type, target, error_code, os_summary, int(elevated), "running", rules_digest))
        return cid

    def finish_case(self, cid: str, status: str, checks: list[CheckResult], findings: list[Finding]) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT INTO diagnostic_checks(case_id,check_id,layer,title,status,detail,evidence_json,duration_ms)"
                " VALUES(?,?,?,?,?,?,?,?)",
                [(cid, c.id, c.layer.value, c.title, c.status.value, redact_secrets(c.detail),
                  _dump(c.evidence), c.duration_ms) for c in checks])
            self.conn.executemany(
                "INSERT INTO repair_plans(case_id,rule_id,rule_version,confidence,risk,policy_decision,lifecycle,finding_json)"
                " VALUES(?,?,?,?,?,?,?,?)",
                [(cid, f.rule_id, f.version, f.confidence, f.risk, f.decision, f.lifecycle, _dump(f.to_dict()))
                 for f in findings])
            self.conn.execute("UPDATE cases SET ended_at=?, status=? WHERE id=?", (now_iso(), status, cid))

    def list_cases(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM cases ORDER BY started_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()

    def get_checks(self, cid: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM diagnostic_checks WHERE case_id=? ORDER BY id", (cid,)).fetchall()

    def get_plans(self, cid: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM repair_plans WHERE case_id=? ORDER BY id", (cid,)).fetchall()

    def prune(self, retention_days: int, max_cases: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.conn:
            n = self.conn.execute("DELETE FROM cases WHERE started_at < ?", (cutoff,)).rowcount
            n += self.conn.execute(
                "DELETE FROM cases WHERE id NOT IN (SELECT id FROM cases ORDER BY started_at DESC, rowid DESC LIMIT ?)",
                (max_cases,)).rowcount
        return n

    def clear_history(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM cases")
            self.conn.execute("DELETE FROM audit_events")


class SettingsRepository:
    def __init__(self, conn: sqlite3.Connection, defaults: dict) -> None:
        self.conn, self.defaults = conn, defaults

    def get(self, key: str) -> Any:
        row = self.conn.execute("SELECT value_json FROM app_settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else self.defaults[key]

    def set(self, key: str, value: Any) -> None:
        if key not in self.defaults:
            raise KeyError(key)
        with self.conn:
            self.conn.execute("INSERT INTO app_settings(key,value_json) VALUES(?,?) "
                              "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json", (key, json.dumps(value)))


class AuditRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def log(self, event_type: str, case_id: str | None = None, elevated: bool = False,
            policy_decision: str | None = None, **detail: Any) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO audit_events(ts,case_id,event_type,elevated,policy_decision,detail_json) VALUES(?,?,?,?,?,?)",
                (now_iso(), case_id, event_type, int(elevated), policy_decision, _dump(detail)))

    def list(self, case_id: str | None = None) -> list[sqlite3.Row]:
        if case_id:
            return self.conn.execute("SELECT * FROM audit_events WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
        return self.conn.execute("SELECT * FROM audit_events ORDER BY id").fetchall()


class RepairRepository:
    """Catatan tindakan, snapshot sebelum perubahan, dan hasil verifikasi (Fase 2)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def start_action(self, case_id: str, operation: str, params: dict) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO actions(case_id,operation,params_json,started_at) VALUES(?,?,?,?)",
                (case_id, operation, _dump(params), now_iso()))
        return int(cur.lastrowid)

    def finish_action(self, action_id: int, success: bool, result_code: int | None = None) -> None:
        with self.conn:
            self.conn.execute("UPDATE actions SET ended_at=?, success=?, result_code=? WHERE id=?",
                              (now_iso(), int(success), result_code, action_id))

    def add_snapshot(self, case_id: str, action_id: int | None, kind: str, payload: dict,
                     restore_supported: bool) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO snapshots(case_id,action_id,snapshot_type,payload_json,restore_supported) VALUES(?,?,?,?,?)",
                (case_id, action_id, kind, _dump(payload), int(restore_supported)))
        return int(cur.lastrowid)

    def link_snapshot(self, snapshot_id: int, action_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE snapshots SET action_id=? WHERE id=?", (action_id, snapshot_id))

    def snapshot_for_action(self, action_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM snapshots WHERE action_id=? ORDER BY id DESC LIMIT 1",
                                 (action_id,)).fetchone()

    def get_action(self, action_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()

    def add_verification(self, case_id: str, test_id: str, status: str, evidence: dict) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO verification_results(case_id,test_id,status,evidence_json) VALUES(?,?,?,?)",
                              (case_id, test_id, status, _dump(evidence)))

    def verifications(self, case_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM verification_results WHERE case_id=? ORDER BY id", (case_id,)).fetchall()

    def actions(self, case_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM actions WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
