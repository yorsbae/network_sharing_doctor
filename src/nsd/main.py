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
    pp = sub.add_parser("paper", help="Ukuran kertas khusus di client (lokal, tanpa server)")
    ps = pp.add_subparsers(dest="paper_cmd", required=True)
    ps.add_parser("list", help="Daftar ukuran bawaan + milik pengguna")
    pa = ps.add_parser("add", help="Tambah ukuran khusus")
    pa.add_argument("--name", required=True)
    pa.add_argument("--width", type=float, required=True, help="mm")
    pa.add_argument("--height", type=float, required=True, help="mm")
    pr = ps.add_parser("remove", help="Hapus ukuran khusus")
    pr.add_argument("--name", required=True)
    pl = ps.add_parser("layout", help="Hitung tata letak halaman")
    pl.add_argument("--paper", required=True)
    pl.add_argument("--landscape", action="store_true")
    pl.add_argument("--margin", type=float, default=10.0, help="mm, semua sisi")
    pl.add_argument("--scale", type=float, default=100.0)
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


def _cmd_paper(a: argparse.Namespace) -> int:
    from nsd.app_config import data_dir
    from nsd.paper import Margins, Orientation, PageLayout, PaperError, PaperStore

    store = PaperStore(data_dir())
    try:
        if a.paper_cmd == "list":
            custom = {p.name for p in store.custom()}
            for p in store.all():
                print(f"{'khusus' if p.name in custom else 'bawaan':7} {p.label()}")
            for w in store.load_errors:
                print("PERINGATAN:", w, file=sys.stderr)
        elif a.paper_cmd == "add":
            p = store.add(a.name, a.width, a.height)
            print(f"Ditambahkan (lokal di client): {p.label()}")
        elif a.paper_cmd == "remove":
            ok = store.remove(a.name)
            print("Dihapus." if ok else "Tidak ditemukan.")
            return 0 if ok else 1
        else:
            paper = next((p for p in store.all() if p.name.lower() == a.paper.strip().lower()), None)
            if paper is None:
                raise PaperError(f"Ukuran '{a.paper}' tidak ada.")
            m = a.margin
            lay = PageLayout(paper, Orientation.LANDSCAPE if a.landscape else Orientation.PORTRAIT,
                             Margins(m, m, m, m), a.scale)
            w, h = lay.page_mm
            print(f"{paper.label()} {'lanskap' if a.landscape else 'potret'}: halaman {w:g}×{h:g} mm, "
                  f"area isi {lay.content_width_mm:g}×{lay.content_height_mm:g} mm, skala {a.scale:g}%")
    except PaperError as exc:
        print(f"Input tidak valid: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd in (None, "gui"):
            from nsd.ui.main_window import run_gui

            return run_gui()
        return {"scan": _cmd_scan, "history": _cmd_history,
                "rules-validate": _cmd_rules_validate, "clear-history": _cmd_clear,
                "paper": _cmd_paper}[args.cmd](args)
    except ValidationError as exc:
        print(f"Input tidak valid: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
