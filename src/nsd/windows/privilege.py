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


def relaunch_as_admin(extra_args: str = "") -> bool:
    """Buka salinan aplikasi dengan prompt UAC standar Windows. Tidak menyimpan atau meminta kata sandi.

    True bila Windows menerima permintaan (pengguna menyetujui prompt); proses ini lalu sebaiknya ditutup.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        frozen = bool(getattr(sys, "frozen", False))
        params = extra_args if frozen else f"-m nsd {extra_args}".strip()
        return int(ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)) > 32  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False
