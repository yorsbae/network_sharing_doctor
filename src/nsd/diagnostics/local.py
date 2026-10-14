"""Konteks komputer lokal: OS, elevasi, profil jaringan, firewall, konfigurasi SMB."""
from __future__ import annotations

from nsd.diagnostics.base import DiagContext, op_failure_detail, result
from nsd.models import CheckResult, Layer, Status
from nsd.windows.powershell import as_list


def check_os(ctx: DiagContext) -> list[CheckResult]:
    op = ctx.adapter.run("os_info")
    title = "Informasi Windows lokal"
    if not op.ok or not isinstance(op.data, dict):
        return [result("local.os", Layer.CONTEXT, title, Status.UNKNOWN, op_failure_detail(op))]
    ctx.os_info = op.data
    ctx.mark_sensitive("LOCALPC", str(op.data.get("ComputerName") or ""))
    ctx.mark_sensitive("DOMAIN", str(op.data.get("Domain") or "")) if op.data.get("PartOfDomain") else None
    return [result("local.os", Layer.CONTEXT, title, Status.PASS,
                   f"{op.data.get('Caption')} (build {op.data.get('Build')}); "
                   f"{'domain' if op.data.get('PartOfDomain') else 'workgroup'}.",
                   build=op.data.get("Build"), domain_joined=bool(op.data.get("PartOfDomain")))]


def check_privilege(ctx: DiagContext) -> list[CheckResult]:
    title = "Hak administrator"
    if ctx.adapter.is_elevated():
        return [result("local.privilege", Layer.CONTEXT, title, Status.PASS, "Berjalan dengan hak administrator.", elevated=True)]
    return [result("local.privilege", Layer.CONTEXT, title, Status.WARNING,
                   "Berjalan tanpa hak administrator; pemeriksaan tertentu (mis. konfigurasi SMB server) terbatas.",
                   elevated=False)]


def check_profile(ctx: DiagContext) -> list[CheckResult]:
    title = "Profil jaringan mendukung sharing"
    op = ctx.adapter.run("net_profile")
    if not op.ok:
        return [result("local.profile", Layer.FIREWALL, title, Status.UNKNOWN, op_failure_detail(op))]
    rows = [r for r in as_list(op.data) if isinstance(r, dict) and r.get("IPv4") != "Disconnected"]
    if not rows:
        return [result("local.profile", Layer.FIREWALL, title, Status.UNKNOWN, "Tidak ada koneksi aktif yang terbaca.")]
    cats = sorted({str(r.get("Category")) for r in rows})
    if "Public" in cats:
        return [result("local.profile", Layer.FIREWALL, title, Status.WARNING,
                       "Ada koneksi aktif berprofil Publik; penemuan jaringan dan sharing biasanya dibatasi. "
                       "Perubahan profil bisa dibatasi kebijakan organisasi.", categories=cats, category="Public")]
    return [result("local.profile", Layer.FIREWALL, title, Status.PASS, "Profil: " + ", ".join(cats) + ".", categories=cats)]


def check_firewall(ctx: DiagContext) -> list[CheckResult]:
    if ctx.request.role.value != "server":
        return []
    title = "Aturan firewall File and Printer Sharing aktif"
    op = ctx.adapter.run("firewall_sharing")
    if not op.ok:
        return [result("local.firewall", Layer.FIREWALL, title, Status.UNKNOWN, op_failure_detail(op))]
    rules = [r for r in as_list(op.data) if isinstance(r, dict)]
    if not rules:
        return [result("local.firewall", Layer.FIREWALL, title, Status.UNKNOWN,
                       "Grup aturan tidak terbaca (bisa karena firewall pihak ketiga atau ID grup belum tervalidasi).")]
    ok = [r for r in rules if r.get("Enabled") == "True" and r.get("Direction") == "Inbound" and r.get("Action") == "Allow"]
    if ok:
        return [result("local.firewall", Layer.FIREWALL, title, Status.PASS,
                       f"{len(ok)} aturan masuk aktif. Firewall pihak ketiga tidak dievaluasi.", enabled_inbound=len(ok))]
    return [result("local.firewall", Layer.FIREWALL, title, Status.FAIL,
                   "Semua aturan masuk File and Printer Sharing nonaktif.", enabled_inbound=0, total=len(rules))]


def check_smb_client(ctx: DiagContext) -> list[CheckResult]:
    title = "Konfigurasi klien SMB aman"
    op = ctx.adapter.run("smb_client_config")
    if not op.ok or not isinstance(op.data, dict):
        return [result("local.smb_client", Layer.SERVICE, title, Status.UNKNOWN, op_failure_detail(op))]
    if op.data.get("EnableInsecureGuestLogons"):
        return [result("local.smb_client", Layer.SERVICE, title, Status.WARNING,
                       "Logon tamu tidak aman (insecure guest) aktif di klien. Aplikasi tidak mengubahnya.",
                       insecure_guest=True)]
    return [result("local.smb_client", Layer.SERVICE, title, Status.PASS, "Logon tamu tidak aman nonaktif.", insecure_guest=False)]


def check_smb_server(ctx: DiagContext) -> list[CheckResult]:
    if ctx.request.role.value != "server":
        return []
    title = "Konfigurasi server SMB aman"
    op = ctx.adapter.run("smb_server_config")
    if not op.ok or not isinstance(op.data, dict):
        return [result("local.smb_server", Layer.SERVICE, title, Status.UNKNOWN,
                       op_failure_detail(op) + " (umumnya butuh hak administrator)")]
    if op.data.get("EnableSMB1Protocol"):
        return [result("local.smb_server", Layer.SERVICE, title, Status.WARNING,
                       "SMB1 aktif di server. Protokol lama dan tidak aman; aplikasi tidak mengubahnya.", smb1=True)]
    if op.data.get("EnableSMB2Protocol") is False:
        return [result("local.smb_server", Layer.SERVICE, title, Status.FAIL, "SMB2/3 nonaktif di server.", smb1=False, smb2=False)]
    return [result("local.smb_server", Layer.SERVICE, title, Status.PASS, "SMB1 nonaktif, SMB2/3 aktif.", smb1=False)]


def check_local_folder_share(ctx: DiagContext) -> list[CheckResult]:
    req = ctx.request
    if req.role.value != "server" or not req.target_type.includes("folder") or not req.share:
        return []
    title = "Share folder terdaftar di komputer ini"
    op = ctx.adapter.run("list_local_shares")
    if not op.ok:
        return [result("local.folder_share", Layer.SHARING, title, Status.UNKNOWN, op_failure_detail(op))]
    names = [str(r.get("Name")) for r in as_list(op.data) if isinstance(r, dict)]
    if req.share.lower() in (n.lower() for n in names):
        return [result("local.folder_share", Layer.SHARING, title, Status.PASS, "Share ditemukan.")]
    return [result("local.folder_share", Layer.SHARING, title, Status.FAIL,
                   "Tidak ada share dengan nama tersebut di komputer ini.", category="not_found")]
