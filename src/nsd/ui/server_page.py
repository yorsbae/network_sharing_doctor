from __future__ import annotations

import sys
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from nsd.application import autostart, server_control, server_setup
from nsd.application.activity_service import describe, read_events
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
            "Windows sendiri melayani client selama printer terpasang dan dibagikan di komputer ini. Tombol "
            "\"Jalankan server\" menyalakan pemantau di latar belakang yang mencatat siapa yang menyambung dan siapa yang "
            "mencetak (hanya membaca). Komputer ini harus menyala dan tersambung ke jaringan saat client mencetak."))

        lay.addWidget(self._control_panel())
        lay.addWidget(self._activity_panel())

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

    # -- kontrol server, autostart, log aktivitas ---------------------------
    def _control_panel(self) -> QWidget:
        box, bl = panel()
        top = QHBoxLayout()
        top.addWidget(theme.label("Server NSD", "section"), 1)
        self.run_chip_row = QHBoxLayout()
        top.addLayout(self.run_chip_row)
        bl.addLayout(top)
        row = QHBoxLayout()
        self.run_btn = QPushButton("Jalankan server")
        theme.set_role(self.run_btn, "primary")
        self.run_btn.clicked.connect(self._toggle_server)
        row.addWidget(self.run_btn)
        row.addStretch(1)
        bl.addLayout(row)
        self.autostart_cb = QCheckBox("Jalankan server otomatis saat Windows menyala (saat login)")
        usable = sys.platform == "win32" and getattr(sys, "frozen", False)
        self._autostart_usable = usable
        if usable:
            self.autostart_cb.setChecked(autostart.status().ok)
            self.autostart_cb.toggled.connect(self._toggle_autostart)
        else:
            self.autostart_cb.setEnabled(False)
        bl.addWidget(self.autostart_cb)
        self.ctl_note = theme.label(
            "" if usable else "Autostart tersedia di Windows pada aplikasi terpaket (NSD.exe). Dari skrip Python, "
                              "pilihan ini dimatikan; tombol Jalankan server tetap bisa dipakai.", "caption")
        bl.addWidget(self.ctl_note)
        self.ctl_note.setVisible(bool(self.ctl_note.text()))
        return box

    def _activity_panel(self) -> QWidget:
        box, bl = panel()
        bl.addWidget(theme.label("Aktivitas langsung", "section"))
        bl.addWidget(theme.label("Yang menyambung ke komputer ini dan pekerjaan cetak yang masuk. Tanpa hak administrator, "
                                 "hanya alamat IP yang terlihat.", "caption"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setMinimumHeight(180)
        self.log_view.setAccessibleName("Log aktivitas server")
        self.log_view.setPlaceholderText("Belum ada aktivitas. Klik Jalankan server, lalu cetak dari komputer client.")
        bl.addWidget(self.log_view)
        self._log_sig = None
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._poll)
        return box

    def _poll(self) -> None:
        self._update_run_state()
        self._render_log()

    def _update_run_state(self) -> None:
        running = server_control.is_running(self.ctx.data_dir)
        clear(self.run_chip_row)
        self.run_chip_row.addWidget(theme.chip("Berjalan" if running else "Berhenti", "ok" if running else "neutral"))
        self.run_btn.setText("Hentikan server" if running else "Jalankan server")
        self.run_btn.setEnabled(True)

    def _render_log(self) -> None:
        evs = read_events(self.ctx.data_dir, 200)
        sig = (len(evs), evs[-1] if evs else None)
        if sig == self._log_sig:
            return
        self._log_sig = sig
        self.log_view.setPlainText("\n".join(f"{e.get('ts', '')[11:]}  {describe(e)}" for e in evs[::-1]))   # terbaru di atas

    def _toggle_server(self) -> None:
        self.run_btn.setEnabled(False)
        if server_control.is_running(self.ctx.data_dir):
            msg = server_control.stop(self.ctx.data_dir)
        else:
            try:
                msg = server_control.start(self.ctx.data_dir)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Server", f"Server tidak bisa dijalankan: {exc}")
                msg = ""
        if msg:
            self.note.setText(msg)
        QTimer.singleShot(1500, self._poll)

    def _toggle_autostart(self, on: bool) -> None:
        res = (autostart.install("logon-user", host="localhost", share="", target_type="printer", interval=300, task="serve")
               if on else autostart.uninstall())
        if not res.ok:
            self.autostart_cb.blockSignals(True)
            self.autostart_cb.setChecked(not on)
            self.autostart_cb.blockSignals(False)
            QMessageBox.warning(self, "Autostart", res.message)
        else:
            self.note.setText("Server akan jalan otomatis saat login." if on else "Autostart dimatikan.")

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()                     # tidak membaca log saat halaman tidak terlihat
        super().hideEvent(e)

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self._poll()
        self.timer.start()
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
