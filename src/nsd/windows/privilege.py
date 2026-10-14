"""Deteksi elevasi. Tidak pernah meminta/menyimpan kata sandi admin atau mem-bypass UAC."""
from __future__ import annotations

import os
import sys


def is_elevated() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0
