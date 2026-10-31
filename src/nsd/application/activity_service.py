"""Log aktivitas server: siapa menyambung dan siapa mencetak (BACA-SAJA).

Polling dua operasi baca-saja (`list_smb_sessions`/`list_smb_connections` dan `list_print_jobs`),
lalu mencatat PERBEDAANNYA sebagai peristiwa ke `activity.jsonl` (satu JSON per baris, dirotasi).
Tidak mengubah apa pun pada sistem. Dipakai oleh `nsd serve` dan dibaca GUI (halaman Server).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from nsd.windows.powershell import WindowsAdapter, as_list

LOG_NAME = "activity.jsonl"
MAX_LOG_BYTES = 1024 * 1024
MAX_LOG_LINES_READ = 500

# kind -> (label, nada UI)
KINDS = {
    "server_start": ("Server dijalankan", "info"),
    "server_stop": ("Server dihentikan", "info"),
    "connect": ("Tersambung", "ok"),
    "disconnect": ("Terputus", "neutral"),
    "job_new": ("Cetak masuk antrean", "info"),
    "job_progress": ("Status cetak berubah", "info"),
    "job_done": ("Cetak selesai", "ok"),
    "job_error": ("Cetak bermasalah", "bad"),
    "warn": ("Peringatan", "warn"),
}
_ERROR_WORDS = ("error", "offline", "paperout", "usercintervention", "blocked", "deleting")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def describe(ev: dict) -> str:
    """Satu baris teks yang mudah dibaca untuk sebuah peristiwa."""
    label = KINDS.get(ev.get("kind", ""), (ev.get("kind", "?"), ""))[0]
    who = ev.get("client") or ev.get("owner") or ""
    parts = [label]
    if ev.get("kind") in ("connect", "disconnect"):
        parts.append(f"dari {who}" + (f" ({ev['user']})" if ev.get("user") else ""))
    elif ev.get("kind", "").startswith("job_"):
        doc = ev.get("document") or "(tanpa judul)"
        parts.append(f"“{doc}” di {ev.get('printer', '?')}")
        extra = []
        if who:
            extra.append(f"dari {who}")
        if ev.get("pages"):
            extra.append(f"{ev['pages']} hlm")
        if ev.get("status"):
            extra.append(str(ev["status"]))
        if extra:
            parts.append(", ".join(extra))
    elif ev.get("message"):
        parts.append(str(ev["message"]))
    return " · ".join(parts)


@dataclass
class ActivityWatcher:
    adapter: WindowsAdapter
    data_dir: Path
    seen_sessions: dict[str, dict] | None = None
    seen_jobs: dict[str, dict] | None = None
    _warned: set[str] = field(default_factory=set, repr=False)

    @property
    def path(self) -> Path:
        return self.data_dir / LOG_NAME

    # -- penulisan log -----------------------------------------------------
    def emit(self, kind: str, **fields: Any) -> dict:
        ev = {"ts": _now(), "kind": kind, **{k: v for k, v in fields.items() if v not in (None, "")}}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if self.path.exists() and self.path.stat().st_size > MAX_LOG_BYTES:
                os.replace(self.path, self.path.with_suffix(".jsonl.1"))
        except OSError:
            pass
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def _warn_once(self, key: str, msg: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            self.emit("warn", message=msg)

    # -- pembacaan ---------------------------------------------------------
    def _read_sessions(self) -> dict[str, dict] | None:
        res = self.adapter.run("list_smb_sessions")
        if not res.ok:                                  # tanpa admin: pakai koneksi TCP 445 (hanya alamat IP)
            res = self.adapter.run("list_smb_connections")
            if res.ok:
                self._warn_once("sess", "Tanpa hak administrator, yang tampil hanya alamat IP. "
                                        "Buka aplikasi sebagai administrator untuk melihat nama komputer dan pengguna.")
        if not res.ok:
            self._warn_once("conn", "Daftar koneksi tidak bisa dibaca: " + (res.error or "tidak didukung")[:120])
            return None
        out: dict[str, dict] = {}
        for r in as_list(res.data):
            if not isinstance(r, dict):
                continue
            client = str(r.get("Client") or "").strip()
            if not client or client in ("::1", "127.0.0.1"):
                continue
            key = client + "|" + str(r.get("User") or "")
            out[key] = {"client": client, "user": r.get("User") or ""}
        return out

    def _read_jobs(self) -> dict[str, dict] | None:
        res = self.adapter.run("list_print_jobs")
        if not res.ok:
            self._warn_once("jobs", "Antrean cetak tidak bisa dibaca: " + (res.error or "tidak didukung")[:120])
            return None
        out: dict[str, dict] = {}
        for r in as_list(res.data):
            if not isinstance(r, dict):
                continue
            key = f"{r.get('Printer')}#{r.get('Id')}"
            out[key] = {"printer": r.get("Printer"), "document": r.get("Document"), "status": str(r.get("Status") or ""),
                        "pages": r.get("Pages"), "owner": r.get("Owner") or "", "client": r.get("Client") or ""}
        return out

    # -- satu putaran ------------------------------------------------------
    def tick(self) -> list[dict]:
        events: list[dict] = []
        sess = self._read_sessions()
        if sess is not None:
            if self.seen_sessions is not None:           # putaran pertama = baseline, bukan "koneksi baru"
                for k, v in sess.items():
                    if k not in self.seen_sessions:
                        events.append(self.emit("connect", **v))
                for k, v in self.seen_sessions.items():
                    if k not in sess:
                        events.append(self.emit("disconnect", **v))
            else:
                for v in sess.values():
                    events.append(self.emit("connect", baseline=True, **v))
            self.seen_sessions = sess
        jobs = self._read_jobs()
        if jobs is not None:
            prev = self.seen_jobs if self.seen_jobs is not None else {}
            for k, v in jobs.items():
                old = prev.get(k)
                if old is None:
                    events.append(self.emit("job_new", **v))
                elif old["status"] != v["status"]:
                    bad = any(w in v["status"].lower() for w in _ERROR_WORDS)
                    events.append(self.emit("job_error" if bad else "job_progress", **v))
            for k, old in prev.items():
                if k not in jobs:      # hilang dari antrean = sudah dikirim ke printer (atau dibatalkan)
                    bad = any(w in old["status"].lower() for w in ("error", "deleting"))
                    events.append(self.emit("job_error" if bad else "job_done", **old))
            self.seen_jobs = jobs
        return events


def read_events(data_dir: Path, limit: int = 200) -> list[dict]:
    """Peristiwa terbaru (paling baru di akhir). Baris rusak dilewati."""
    p = Path(data_dir) / LOG_NAME
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-min(limit, MAX_LOG_LINES_READ):]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            ev = json.loads(ln)
            if isinstance(ev, dict):
                out.append(ev)
        except json.JSONDecodeError:
            continue
    return out
