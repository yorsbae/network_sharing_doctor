"""Menjalankan scan di thread terpisah agar UI tidak membeku."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot


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


class _Relay(QObject):
    """Hidup di thread utama; menerima sinyal dari pekerja lalu memanggil callback di thread UI."""

    def __init__(self, owner, on_done, on_fail) -> None:
        super().__init__(owner)
        self._on_done, self._on_fail = on_done, on_fail

    @Slot(object)
    def done(self, result) -> None:
        self._on_done(result)

    @Slot(str)
    def failed(self, msg: str) -> None:
        if self._on_fail:
            self._on_fail(msg)


class _CallWorker(QObject):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self._fn())
        except Exception as exc:  # noqa: BLE001 - tampilkan ke pengguna, jangan crash
            self.failed.emit(f"{exc.__class__.__name__}: {exc}")
        finally:
            QThread.currentThread().quit()


_ACTIVE: set = set()      # menjaga thread/pekerja tetap hidup sampai selesai, walau halaman pemilik sudah dihancurkan


def run_async(owner: QObject, fn, on_done, on_fail=None) -> QThread:
    """Jalankan `fn()` di thread latar; `on_done(hasil)` dipanggil di thread UI. `fn` tidak boleh menyentuh widget.

    Bila `owner` dihancurkan sebelum selesai, hasil dibuang tanpa crash.
    """
    thread, worker = QThread(), _CallWorker(fn)
    worker.moveToThread(thread)
    relay = _Relay(owner, on_done, on_fail)
    thread.started.connect(worker.run)
    worker.done.connect(relay.done)
    worker.failed.connect(relay.failed)
    entry = (thread, worker)
    _ACTIVE.add(entry)

    def cleanup() -> None:
        _ACTIVE.discard(entry)
        worker.deleteLater()
        thread.deleteLater()

    thread.finished.connect(cleanup)
    thread.start()
    return thread
