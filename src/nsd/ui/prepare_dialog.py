from __future__ import annotations

from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton,
                               QVBoxLayout)

from nsd.application import server_prepare
from nsd.ui import theme
from nsd.ui.widgets.worker import run_async
from nsd.windows.powershell import RealWindowsAdapter
from nsd.windows.privilege import relaunch_as_admin

_OUTCOME = {"verified": "Berhasil", "unverified": "Terkirim, belum terbukti", "failed": "Gagal", "refused": "Ditolak"}


class PrepareDialog(QDialog):
    """Pilih apa yang disiapkan, lalu terapkan dan verifikasi. Persetujuan = klik Terapkan di dialog ini."""

    def __init__(self, ctx, actions, parent=None) -> None:
        super().__init__(parent)
        self.ctx, self.actions, self.applied_any, self._busy = ctx, actions, False, False
        self.setWindowTitle("Siapkan server otomatis")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(theme.label("Pilih yang disiapkan", "section"))
        lay.addWidget(theme.label(
            "Hanya perubahan yang dibutuhkan agar client bisa mencetak. Firewall tidak dimatikan dan layanan tidak "
            "diubah tipe startupnya. Hasil tiap langkah dicek ulang dan dicatat di log audit.", "caption"))
        self.checks: list[tuple[QCheckBox, server_prepare.PrepareAction]] = []
        for a in actions:
            cb = QCheckBox(a.label)
            cb.setChecked(a.default_on)
            cb.toggled.connect(self._sync)
            self.checks.append((cb, a))
            lay.addWidget(cb)
        self.admin_row = QHBoxLayout()
        lay.addLayout(self.admin_row)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(110)
        self.log.setVisible(False)
        lay.addWidget(self.log)
        row = QHBoxLayout()
        row.addStretch(1)
        self.apply_btn = QPushButton("Siapkan sekarang")
        theme.set_role(self.apply_btn, "primary")
        self.apply_btn.clicked.connect(self._apply)
        self.close_btn = QPushButton("Tutup")
        self.close_btn.clicked.connect(self.accept)
        row.addWidget(self.close_btn)
        row.addWidget(self.apply_btn)
        lay.addLayout(row)
        self._refresh_admin()

    def _refresh_admin(self) -> None:
        while self.admin_row.count():
            it = self.admin_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.elevated = bool(self.ctx.adapter.is_elevated())
        self.admin_row.addWidget(theme.label("Hak administrator", wrap=False))
        self.admin_row.addWidget(theme.chip("Ya" if self.elevated else "Belum", "ok" if self.elevated else "warn"))
        self.admin_row.addStretch(1)
        if not self.elevated:
            b = QPushButton("Buka ulang sebagai administrator")
            b.clicked.connect(self._relaunch)
            self.admin_row.addWidget(b)
        self._sync()

    def _sync(self) -> None:
        any_on = any(cb.isChecked() for cb, _ in self.checks)
        self.apply_btn.setEnabled(self.elevated and any_on and not self._busy)
        self.apply_btn.setToolTip("" if self.elevated else "Perlu hak administrator. Klik Buka ulang sebagai administrator.")

    def _relaunch(self) -> None:
        if QMessageBox.question(self, "Hak administrator", "Aplikasi ditutup lalu dibuka lagi sebagai administrator "
                                "(Windows meminta persetujuan Anda). Setelah terbuka, klik Siapkan otomatis sekali lagi. Lanjutkan?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if relaunch_as_admin("start --wait-previous"):
            QApplication.quit()
        else:
            QMessageBox.information(self, "Hak administrator", "Permintaan tidak dilanjutkan. Tidak ada yang berubah.")

    def _apply(self) -> None:
        chosen = [a for cb, a in self.checks if cb.isChecked()]
        if not chosen or self._busy:
            return
        self._busy = True
        self.apply_btn.setEnabled(False)
        self.log.setVisible(True)
        self.log.setPlainText("Menyiapkan dan memverifikasi, bisa sampai beberapa detik per langkah.")
        # Adapter dengan izin ubah dibuat hanya di sini, setelah klik; pengaturan global tidak diubah.
        adapter, audit = RealWindowsAdapter(allow_mutation=True), self.ctx.audit
        run_async(self, lambda: server_prepare.apply(adapter, chosen, audit), self._done, self._failed)

    def _done(self, results) -> None:
        self._busy = False
        self.applied_any = any(r.outcome == "verified" for r in results)
        self.log.setPlainText("\n".join(f"{_OUTCOME[r.outcome]}: {r.action.label}. {r.message}" for r in results))
        self._sync()

    def _failed(self, msg: str) -> None:
        self._busy = False
        self.log.setPlainText(f"Gagal menjalankan penyiapan: {msg}. Tidak ada klaim berhasil.")
        self._sync()
