"""Titik masuk: GUI (default) dan CLI."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nsd import __version__
from nsd.models import Role, ScanRequest, TargetType
from nsd.security.allowlist import ValidationError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="nsd", description="Network Sharing Doctor — diagnosis (baca-saja) sharing printer & folder.")
    p.add_argument("--version", action="version", version=f"nsd {__version__}")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="Buka antarmuka grafis (default)")
    s = sub.add_parser("scan", help="Jalankan diagnosis")
    s.add_argument("--role", choices=["client", "server"], default="client")
    s.add_argument("--type", dest="ttype", choices=["printer", "folder", "both"], default="both")
    s.add_argument("--host", required=True, help="Nama komputer atau alamat IP target")
    s.add_argument("--share", default="", help="Nama share folder/printer")
    s.add_argument("--error", default="", help="Kode/pesan error persis, mis. 0x0000011B")
    s.add_argument("--json", action="store_true", help="Keluaran JSON")
    s.add_argument("--no-redact", action="store_true", help="Jangan samarkan laporan (hati-hati saat dibagikan)")
    s.add_argument("--out", type=Path, help="Simpan laporan ke berkas")
    s.add_argument("--no-save", action="store_true", help="Jangan simpan kasus ke riwayat")
    h = sub.add_parser("history", help="Tampilkan riwayat kasus")
    h.add_argument("--limit", type=int, default=20)
    sub.add_parser("rules-validate", help="Validasi berkas aturan")
    sub.add_parser("clear-history", help="Hapus seluruh riwayat kasus")
    return p


def _cmd_scan(a: argparse.Namespace) -> int:
    from nsd.application.report_service import build_json, build_text
    from nsd.application.scan_service import ScanService
    from nsd.bootstrap import bootstrap
    from nsd.models import Status
    from nsd.windows.powershell import RealWindowsAdapter

    req = ScanRequest(Role(a.role), TargetType(a.ttype), a.host, a.share, a.error)
    if a.no_save:
        svc = ScanService(RealWindowsAdapter())
    else:
        svc = bootstrap().scan_service()
    out = svc.run(req)
    redact = not a.no_redact
    text = build_json(out, redact) if a.json else build_text(out, redact)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
        print(f"Laporan disimpan: {a.out}" + (" (disamarkan)" if redact else " (TIDAK disamarkan)"))
    else:
        sys.stdout.write(text)
    return 1 if out.count(Status.FAIL) else 0


def _cmd_history(a: argparse.Namespace) -> int:
    from nsd.bootstrap import bootstrap

    rows = bootstrap().cases.list_cases(a.limit)
    if not rows:
        print("Belum ada riwayat.")
    for r in rows:
        print(f"{r['id']}  {r['started_at']}  {r['role']:6} {r['target_type']:7} {r['status']:28} {r['target']}")
    return 0


def _cmd_rules_validate(_: argparse.Namespace) -> int:
    from nsd.rules.loader import load_rules

    rs = load_rules()
    print(f"{len(rs.rules)} aturan valid. Digest: {rs.digest[:16]}")
    for e in rs.errors:
        print("DITOLAK:", e)
    return 2 if rs.errors else 0


def _cmd_clear(_: argparse.Namespace) -> int:
    from nsd.bootstrap import bootstrap

    bootstrap().cases.clear_history()
    print("Riwayat dihapus.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd in (None, "gui"):
            from nsd.ui.main_window import run_gui

            return run_gui()
        return {"scan": _cmd_scan, "history": _cmd_history,
                "rules-validate": _cmd_rules_validate, "clear-history": _cmd_clear}[args.cmd](args)
    except ValidationError as exc:
        print(f"Input tidak valid: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
