from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from nsd.application import server_setup
from nsd.ui import theme
from nsd.ui.widgets.cards import clear, panel, scroll_body
from nsd.ui.widgets.worker import run_async


def step_row(step: server_setup.Step) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 4, 0, 4)
    h.setSpacing(12)
    chip = theme.chip(step.status, step.tone)
    chip.setMinimumWidth(130)
    h.addWidget(chip, 0, Qt.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(theme.label(step.title))
    if step.detail:
        col.addWidget(theme.label(step.detail, "caption", selectable=True))
    if step.howto and step.tone != "ok":
        col.addWidget(theme.label("Yang bisa dilakukan: " + step.howto, "caption", selectable=True))
    h.addLayout(col, 1)
    return row


class ServerPage(QWidget):
    """Komputer ini membagikan printer: cek kesiapan, tampilkan alamat untuk client, beri petunjuk siap kirim."""

    scan_self = Signal()          # buka Scan printer untuk komputer ini

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self.readiness, self._loaded_at, self._busy = ctx, None, 0.0, False
        lay = scroll_body(self)
        self.refresh_btn = QPushButton("Periksa ulang")
        self.refresh_btn.clicked.connect(self.refresh)
        lay.addWidget(theme.header("Server", "Komputer ini membagikan printer ke komputer lain di jaringan.", self.refresh_btn))
        lay.addWidget(theme.callout(
            "Tidak ada program server yang perlu dijalankan",
            "Windows sendiri melayani client selama printer terpasang dan dibagikan di komputer ini. Halaman ini memeriksa "
            "semua syaratnya, lalu memberi alamat yang tinggal disalin ke client. Komputer ini harus menyala dan "
            "tersambung ke jaringan saat client mencetak."))

        box, bl = panel()
        top = QHBoxLayout()
        top.addWidget(theme.label("Kesiapan server", "section"), 1)
        self.verdict_row = QHBoxLayout()
        top.addLayout(self.verdict_row)
        bl.addLayout(top)
        self.state = theme.label("Memeriksa kesiapan…", "caption")
        bl.addWidget(self.state)
        self.steps_lay = QVBoxLayout()
        self.steps_lay.setSpacing(2)
        bl.addLayout(self.steps_lay)
        lay.addWidget(box)

        box2, al = panel()
        al.addWidget(theme.label("Alamat untuk client", "section"))
        self.addr_lay = QVBoxLayout()
        self.addr_lay.setSpacing(6)
        al.addLayout(self.addr_lay)
        self.ident = theme.label("", "caption", selectable=True)
        al.addWidget(self.ident)
        row = QHBoxLayout()
        self.copy_guide = QPushButton("Salin petunjuk untuk client")
        theme.set_role(self.copy_guide, "primary")
        self.copy_guide.clicked.connect(self._copy_guide)
        self.scan_btn = QPushButton("Scan lengkap komputer ini")
        self.scan_btn.clicked.connect(self.scan_self.emit)
        row.addWidget(self.copy_guide)
        row.addWidget(self.scan_btn)
        row.addStretch(1)
        al.addLayout(row)
        self.note = theme.label("", "caption")
        al.addWidget(self.note)
        lay.addWidget(box2)
        lay.addStretch(1)
        self._render_addresses(None)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if self.readiness is None or time.monotonic() - self._loaded_at > 30:
            self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy, self._loaded_at = True, time.monotonic()
        self.refresh_btn.setEnabled(False)
        self.state.setText("Memeriksa kesiapan…")
        self.state.setVisible(True)
        ad = self.ctx.adapter
        run_async(self, lambda: server_setup.check_readiness(ad), self._apply, self._failed)

    def _failed(self, msg: str) -> None:
        self._busy = False
        self.refresh_btn.setEnabled(True)
        self.state.setText("Pemeriksaan gagal dijalankan. Klik Periksa ulang untuk mencoba lagi.")

    def _apply(self, r: server_setup.Readiness) -> None:
        self._busy = False
        self.readiness = r
        self.refresh_btn.setEnabled(True)
        self.state.setVisible(False)
        clear(self.verdict_row)
        text, tone = r.verdict
        self.verdict_row.addWidget(theme.chip(text, tone))
        clear(self.steps_lay)
        for s in r.steps:
            self.steps_lay.addWidget(step_row(s))
        self._render_addresses(r)

    def _render_addresses(self, r: server_setup.Readiness | None) -> None:
        clear(self.addr_lay)
        has = bool(r and r.info.printers)
        if not has:
            msg = ("Belum ada printer yang dibagikan. Selesaikan langkah di atas, lalu klik Periksa ulang."
                   if r else "Alamat muncul di sini setelah pemeriksaan selesai.")
            self.addr_lay.addWidget(theme.label(msg, "empty"))
        else:
            for p in r.info.printers:
                row = QHBoxLayout()
                col = QVBoxLayout()
                col.setSpacing(0)
                col.addWidget(theme.label(p.unc, "section", selectable=True))
                col.addWidget(theme.label(f"{p.name}, {p.status_text}", "caption"))
                row.addLayout(col, 1)
                b = QPushButton("Salin alamat")
                b.clicked.connect(lambda _=False, t=p.unc: self._copy(t, "Alamat tersalin."))
                row.addWidget(b)
                self.addr_lay.addLayout(row)
        info = r.info if r else None
        parts = []
        if info and info.computer_name:
            parts.append(f"Nama komputer: {info.computer_name}")
        if info and info.addresses:
            parts.append("Alamat IP: " + ", ".join(info.addresses))
        self.ident.setText(". ".join(parts) + ("." if parts else ""))
        self.ident.setVisible(bool(parts))
        self.copy_guide.setEnabled(has)

    def _copy(self, text: str, note: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.note.setText(note)

    def _copy_guide(self) -> None:
        if self.readiness:
            text = server_setup.client_instructions(self.readiness.info)
            if text:
                self._copy(text, "Petunjuk tersalin. Tempel ke pesan atau chat untuk pengguna client.")
