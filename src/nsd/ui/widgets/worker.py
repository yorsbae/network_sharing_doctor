"""Menjalankan scan di thread terpisah agar UI tidak membeku."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ScanWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, service, request) -> None:
        super().__init__()
        self._service, self._request = service, request

    def run(self) -> None:
        try:
            out = self._service.run(self._request, lambda d, t, n: self.progress.emit(d, t, n))
            self.finished.emit(out)
        except Exception as exc:  # noqa: BLE001 - tampilkan ke pengguna, jangan crash
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")
