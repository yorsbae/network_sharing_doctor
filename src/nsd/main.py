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
    st = sub.add_parser("settings", help="Lihat/ubah pengaturan")
    st.add_argument("--set", dest="assign", metavar="KUNCI=NILAI(JSON)", help="mis. execution_enabled=true")
    r = sub.add_parser("repair", help="[Fase 2] Terapkan perbaikan yang disarankan pada sebuah kasus")
    r.add_argument("--case", required=True); r.add_argument("--rule", required=True)
    r.add_argument("--confirm", action="store_true", help="Persetujuan eksplisit. Tanpa ini hanya menampilkan rencana.")
    m = sub.add_parser("monitor", help="Monitor latar belakang BACA-SAJA (status.json + log perubahan)")
    m.add_argument("--role", choices=["client", "server"], default="server")
    m.add_argument("--type", dest="ttype", choices=["printer", "folder", "both"], default="both")
    m.add_argument("--host", default="localhost")
    m.add_argument("--share", default="")
    m.add_argument("--interval", type=int, default=300, help="detik antar pemeriksaan (30–86400)")
    m.add_argument("--data-dir", type=Path, help="folder data (mis. untuk mode SYSTEM)")
    m.add_argument("--once", action="store_true", help="satu putaran lalu keluar")
    m.add_argument("--status", action="store_true", help="tampilkan status.json terakhir")
    au = sub.add_parser("autostart", help="Pasang/hapus autostart monitor (Task Scheduler)")
    au.add_argument("action", choices=["install", "uninstall", "status"])
    au.add_argument("--mode", choices=["logon-user", "boot-system"], default="logon-user")
    au.add_argument("--type", dest="ttype", choices=["printer", "folder", "both"], default="both")
    au.add_argument("--host", default="localhost")
    au.add_argument("--share", default="")
    au.add_argument("--interval", type=int, default=300)
    au.add_argument("--i-understand-risk", action="store_true", help="Lewati penjagaan lokasi file (TIDAK disarankan)")
    rb = sub.add_parser("rollback", help="[Fase 2] Pulihkan keadaan sebelum perbaikan")
    rb.add_argument("--case", required=True); rb.add_argument("--action", type=int, required=True)
    rb.add_argument("--confirm", action="store_true")
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


def _cmd_settings(a: argparse.Namespace) -> int:
    import json

    from nsd.app_config import DEFAULT_SETTINGS
    from nsd.bootstrap import bootstrap

    ctx = bootstrap()
    if a.assign:
        key, _, raw = a.assign.partition("=")
        if key not in DEFAULT_SETTINGS or key == "policy_level":
            print(f"Pengaturan tidak dikenal/terkunci: {key}", file=sys.stderr)
            return 2
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            print("Nilai harus JSON (mis. true, 30, \"client\").", file=sys.stderr)
            return 2
        ctx.settings.set(key, value)
        ctx.audit.log("setting_changed", key=key, value=value)
        if key == "execution_enabled" and value:
            print("PERINGATAN: eksekusi perbaikan diaktifkan. Perubahan tetap butuh --confirm, hak administrator, dan snapshot.")
    for k in DEFAULT_SETTINGS:
        print(f"{k} = {json.dumps(ctx.settings.get(k))}")
    return 0


def _rescan(ctx, case_row, rule_id: str) -> None:
    from nsd.models import Role, ScanRequest, TargetType

    host, _, share = case_row["target"].partition("\\")
    req = ScanRequest(Role(case_row["role"]), TargetType(case_row["target_type"]), host, share, case_row["error_code"] or "")
    out = ctx.scan_service().run(req)
    still = rule_id in [f.rule_id for f in out.findings]
    print(f"\nPemindaian ulang (kasus {out.case_id}): " +
          ("masalah awal MASIH terdeteksi." if still else "masalah awal tidak lagi terdeteksi oleh aturan ini."))
    print("Uji koneksi sebenarnya (buka share/tambah printer) tetap diperlukan untuk memastikan.")


def _cmd_repair(a: argparse.Namespace) -> int:
    from nsd.bootstrap import bootstrap
    from nsd.repairs.executor import finding_for_rule
    from nsd.rules.loader import load_rules

    ctx = bootstrap()
    row = next((r for r in ctx.cases.list_cases(500) if r["id"] == a.case), None)
    plan = next((p for p in ctx.cases.get_plans(a.case) if p["rule_id"] == a.rule), None)
    if row is None or plan is None:
        print("Kasus atau aturan tidak ditemukan pada riwayat; jalankan 'scan' terlebih dahulu.", file=sys.stderr)
        return 2
    rs = load_rules()
    finding = finding_for_rule(rs.rules, a.rule)
    if finding is None or finding.version != plan["rule_version"]:
        print("Aturan tidak ada/versinya berubah sejak scan; jalankan scan ulang.", file=sys.stderr)
        return 2
    print(f"Rencana: {finding.title}")
    for act in finding.actions:
        print("  - " + (act["text"] if act["operation"] == "advise" else f"{act['operation']} {({k: v for k, v in act.items() if k != 'operation'})}"))
    print(f"  Risiko: {finding.risk}; butuh admin: {'ya' if finding.requires_admin else 'tidak'}; rollback: {finding.rollback.get('type')}")
    if not a.confirm:
        print("\nBelum ada perubahan. Tambahkan --confirm untuk menyetujui.")
        return 0
    res = ctx.repair_executor().execute(finding, a.case, approved=True)
    for line in res.steps:
        print("  • " + line)
    print(f"Hasil: {res.outcome} — {res.message}")
    if res.rollback_available:
        print(f"Untuk memulihkan: nsd rollback --case {a.case} --action {res.action_id} --confirm")
    if res.outcome == "verified":
        _rescan(ctx, row, a.rule)
    return 0 if res.success else 1


def _cmd_rollback(a: argparse.Namespace) -> int:
    from nsd.bootstrap import bootstrap

    ctx = bootstrap()
    res = ctx.repair_executor().rollback(a.case, a.action, approved=a.confirm)
    print(f"Hasil: {res.outcome} — {res.message}")
    return 0 if res.success else 1


def _cmd_monitor(a: argparse.Namespace) -> int:
    import json
    import signal
    import threading

    from nsd.application.monitor_service import MonitorService, SingleInstance
    from nsd.application.scan_service import ScanService
    from nsd.bootstrap import bootstrap
    from nsd.windows.powershell import RealWindowsAdapter

    ctx = bootstrap(a.data_dir)
    if a.status:
        f = ctx.data_dir / "status.json"
        print(f.read_text(encoding="utf-8") if f.exists() else "Belum ada status.json (monitor belum pernah berjalan).")
        return 0
    req = ScanRequest(Role(a.role), TargetType(a.ttype), a.host, a.share, "")
    lock = SingleInstance(ctx.data_dir / "monitor.lock")
    if not lock.acquire():
        print("Monitor sudah berjalan pada folder data ini.", file=sys.stderr)
        return 3
    try:
        # Adapter TANPA izin mutasi, apa pun isi pengaturan: monitor tidak pernah memperbaiki apa pun.
        svc = ScanService(RealWindowsAdapter(), ctx.cases, ctx.audit)
        mon = MonitorService(svc, req, ctx.data_dir, ctx.audit, interval=a.interval)
        if a.once:
            st = mon.tick()
            print(json.dumps({"overall": st.overall, "problems": list(st.sig), "case_id": st.case_id}, ensure_ascii=False))
            return 0 if not st.sig else 1
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        mon.run_forever(stop)
        return 0
    finally:
        lock.release()


def _cmd_autostart(a: argparse.Namespace) -> int:
    from nsd.application import autostart
    from nsd.windows.privilege import is_elevated

    if a.action == "install":
        res = autostart.install(a.mode, host=a.host, share=a.share, target_type=a.ttype, interval=a.interval,
                                elevated=is_elevated(), i_understand_risk=a.i_understand_risk)
    elif a.action == "uninstall":
        res = autostart.uninstall()
    else:
        res = autostart.status()
    print(res.message)
    return 0 if res.ok else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd in (None, "gui"):
            from nsd.ui.main_window import run_gui

            return run_gui()
        return {"scan": _cmd_scan, "history": _cmd_history,
                "rules-validate": _cmd_rules_validate, "clear-history": _cmd_clear,
                "settings": _cmd_settings, "repair": _cmd_repair, "rollback": _cmd_rollback,
                "monitor": _cmd_monitor, "autostart": _cmd_autostart}[args.cmd](args)
    except (ValidationError, ValueError) as exc:
        print(f"Input tidak valid: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
