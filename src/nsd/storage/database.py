"""SQLite: riwayat kasus. Migrasi lewat PRAGMA user_version; cek integritas saat dibuka."""
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1
    """
    CREATE TABLE cases (
        id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT,
        role TEXT NOT NULL, target_type TEXT NOT NULL, target TEXT NOT NULL,
        error_code TEXT, os_summary TEXT, elevated INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL, rules_digest TEXT
    );
    CREATE TABLE diagnostic_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        check_id TEXT NOT NULL, layer TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
        detail TEXT NOT NULL, evidence_json TEXT NOT NULL, duration_ms INTEGER NOT NULL
    );
    CREATE TABLE repair_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        rule_id TEXT NOT NULL, rule_version INTEGER NOT NULL, confidence TEXT NOT NULL,
        risk TEXT NOT NULL, policy_decision TEXT NOT NULL, lifecycle TEXT NOT NULL, finding_json TEXT NOT NULL
    );
    CREATE TABLE actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        operation TEXT NOT NULL, params_json TEXT, started_at TEXT, ended_at TEXT, result_code INTEGER, success INTEGER
    );
    CREATE TABLE snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        action_id INTEGER, snapshot_type TEXT, payload_json TEXT, restore_supported INTEGER
    );
    CREATE TABLE verification_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        test_id TEXT, status TEXT, evidence_json TEXT
    );
    CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, case_id TEXT, event_type TEXT NOT NULL,
        elevated INTEGER NOT NULL DEFAULT 0, policy_decision TEXT, detail_json TEXT
    );
    CREATE TABLE app_settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
    CREATE INDEX idx_checks_case ON diagnostic_checks(case_id);
    CREATE INDEX idx_cases_started ON cases(started_at);
    """,
]


class DatabaseCorrupt(RuntimeError):
    pass


def _open(path: Path) -> sqlite3.Connection:
    # Scan GUI berjalan di QThread; koneksi dibuat di thread utama. DiagnosePage hanya mengizinkan satu scan sekaligus.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise DatabaseCorrupt("Database dibuat oleh versi aplikasi yang lebih baru.")
    for i in range(version, len(MIGRATIONS)):
        with conn:  # satu transaksi per migrasi
            conn.executescript("BEGIN;" + MIGRATIONS[i] + f"PRAGMA user_version={i + 1};COMMIT;")


def open_database(path: Path) -> sqlite3.Connection:
    """Buka DB; bila rusak, pindahkan ke *.corrupt-<ts> lalu buat baru (tidak menghapus apa pun)."""
    path = Path(path)
    try:
        conn = _open(path)
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise sqlite3.DatabaseError(ok)
        _migrate(conn)
        return conn
    except sqlite3.DatabaseError:
        try:
            conn.close()  # type: ignore[possibly-undefined]
        except Exception:  # noqa: BLE001
            pass
        backup = path.with_suffix(path.suffix + f".corrupt-{int(time.time())}")
        shutil.move(str(path), str(backup))
        conn = _open(path)
        _migrate(conn)
        return conn
