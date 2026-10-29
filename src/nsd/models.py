"""Model data bersama (tanpa ketergantungan ke Windows/UI)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    UNKNOWN = "unknown"

    @property
    def label_id(self) -> str:
        return {
            Status.PASS: "Berfungsi",
            Status.WARNING: "Perlu perhatian",
            Status.FAIL: "Gagal",
            Status.UNKNOWN: "Belum diperiksa",
        }[self]

    @property
    def tag(self) -> str:
        """Penanda teks (warna tidak boleh jadi satu-satunya penanda)."""
        return {
            Status.PASS: "[LULUS]",
            Status.WARNING: "[PERINGATAN]",
            Status.FAIL: "[GAGAL]",
            Status.UNKNOWN: "[BELUM DIPERIKSA]",
        }[self]


class Role(str, Enum):
    CLIENT = "client"
    SERVER = "server"


class TargetType(str, Enum):
    PRINTER = "printer"
    FOLDER = "folder"
    BOTH = "both"

    def includes(self, kind: str) -> bool:
        return self is TargetType.BOTH or self.value == kind


class Layer(str, Enum):
    """Lapisan pemeriksaan (spesifikasi §5.5)."""
    TARGET = "Target"
    NETWORK = "Jaringan"
    NAME = "Resolusi nama"
    SERVICE = "Layanan dan protokol"
    FIREWALL = "Firewall"
    SHARING = "Sharing"
    AUTH = "Autentikasi dan izin"
    DRIVER = "Driver dan spooler"
    POLICY = "Kebijakan Windows"
    FINAL = "Operasi akhir"
    CONTEXT = "Konteks komputer"


_CODE_RE = re.compile(r"0[xX][0-9a-fA-F]{1,8}")


def normalize_error_code(text: str) -> str:
    """Ambil kode 0x... pertama dari teks dan normalkan jadi 0x0000011B."""
    m = _CODE_RE.search(text or "")
    if not m:
        return ""
    return "0x%08X" % int(m.group(0), 16)


@dataclass
class ScanRequest:
    role: Role
    target_type: TargetType
    host: str
    share: str = ""
    error_text: str = ""

    @property
    def error_code(self) -> str:
        return normalize_error_code(self.error_text)


@dataclass
class CheckResult:
    id: str
    layer: Layer
    title: str
    status: Status
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "layer": self.layer.value,
            "title": self.title,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Finding:
    """Kemungkinan penyebab hasil pencocokan aturan. Fase 1: hanya disarankan."""
    rule_id: str
    version: int
    title: str
    explanation: str
    confidence: str  # tinggi | sedang | rendah
    risk: str
    auto_policy: str
    requires_admin: bool
    actions: list[dict[str, Any]]
    verification: list[str]
    rollback: dict[str, Any]
    escalation: str
    matched_conditions: list[str]
    matched_error_code: bool
    decision: str = ""        # blocked | suggest_only | needs_confirmation | read_only
    decision_text: str = ""
    lifecycle: str = "terdeteksi"  # terdeteksi→disarankan→disetujui→diterapkan→terverifikasi

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)
