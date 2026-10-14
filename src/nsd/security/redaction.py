"""Penyamaran data sensitif untuk laporan/ekspor (default aktif)."""
from __future__ import annotations

import getpass
import re
import socket
from typing import Any

_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_SECRET = re.compile(r"(?i)\b(password|passwd|pwd|kata\s*sandi|token|secret)\b(\s*[:=]\s*)(\S+)")
MASK = "[DISEMBUNYIKAN]"


def redact_secrets(text: str) -> str:
    """Hapus kata sandi/token yang tampak jelas. Selalu dipakai sebelum menyimpan/log."""
    return _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)


class Redactor:
    """Mengganti nilai sensitif dengan token stabil (HOST-1, SHARE-1, ...)."""

    def __init__(self, include_local_identity: bool = True) -> None:
        self._map: dict[str, str] = {}
        self._counters: dict[str, int] = {}
        if include_local_identity:
            try:
                self.add("USER", getpass.getuser())
            except Exception:  # noqa: BLE001
                pass
            try:
                self.add("LOCALPC", socket.gethostname())
            except Exception:  # noqa: BLE001
                pass

    def add(self, kind: str, value: str) -> None:
        value = (value or "").strip()
        if len(value) < 2 or value.lower() in self._map:
            return
        self._counters[kind] = self._counters.get(kind, 0) + 1
        self._map[value.lower()] = f"{kind}-{self._counters[kind]}"

    def _ip(self, m: re.Match) -> str:
        key = m.group(0).lower()
        if key not in self._map:
            self._counters["IP"] = self._counters.get("IP", 0) + 1
            self._map[key] = f"IP-{self._counters['IP']}"
        return self._map[key]

    def redact(self, text: str) -> str:
        text = redact_secrets(text)
        text = _IPV4.sub(self._ip, text)
        for value in sorted(self._map, key=len, reverse=True):
            if _IPV4.fullmatch(value):
                continue
            pattern = r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])"
            text = re.sub(pattern, self._map[value], text, flags=re.IGNORECASE)
        return text

    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.redact_obj(v) for v in obj]
        return obj
