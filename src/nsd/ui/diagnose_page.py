from __future__ import annotations

from html import escape

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLineEdit,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QStackedWidget,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from nsd.application.report_service import build_json, build_text
from nsd.models import Role, ScanRequest, Status, TargetType
from nsd.security.allowlist import ValidationError
from nsd.ui import theme
from nsd.ui.widgets.cards import panel
from nsd.ui.widgets.worker import ScanWorker

_HEAD = [(Status.FAIL, "Masalah ditemukan"), (Status.WARNING, "Peringatan"),
         (Status.PASS, "Lulus"), (Status.UNKNOWN, "Belum diperiksa")]

_EMPTY = "Belum ada hasil. Isi target di atas, lalu klik Mulai scan."


class ExportDialog(QDialog):
    """Pratinjau sebelum ekspor; penyamaran aktif secara default."""

    def __init__(self, outcome, redact_default: bool, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ekspor laporan")
        self.resize(760, 520)
        self.o = outcome
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        self.chk = QCheckBox("Samarkan nama komputer, IP, share, printer, dan pengguna")
        self.chk.setChecked(redact_default)
        self.chk.toggled.connect(self._refresh)
        lay.addWidget(self.chk)
        self.fmt = QComboBox()
        self.fmt.addItems(["Teks (.txt)", "JSON (.json)"])
        self.fmt.currentIndexChanged.connect(self._refresh)
        lay.addWidget(self.fmt)
        self.view = QPlainTextEdit(readOnly=True)
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        save = QPushButton("Simpan…")
        theme.set_role(save, "primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        close = QPushButton("Tutup")
        close.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(close)
        row.addWidget(save)
        lay.addLayout(row)
        self._refresh()

    def _text(self) -> str:
        redact = self.chk.isChecked()
        return build_json(self.o, redact) if self.fmt.currentIndex() else build_text(self.o, redact)

    def _refresh(self) -> None:
        self.view.setPlainText(self._text())

    def _save(self) -> None:
        ext = "json" if self.fmt.currentIndex() else "txt"
        path, _ = QFileDialog.getSaveFileName(self, "Simpan laporan", f"laporan-{self.o.case_id}.{ext}")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text())
            self.accept()


class DiagnosePage(QWidget):
    scanned = Signal()
    find_server = Signal()        # buka halaman Client untuk mencari server

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self.outcome, self._thread, self._worker = ctx, None, None, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 20)
        lay.setSpacing(14)
        lay.addWidget(theme.header(
            "Scan printer", "Pemeriksaan lengkap yang hanya membaca. Tidak ada yang diubah pada sistem."))
        self.mode = "server" if ctx.settings.get("role_chosen") and ctx.settings.get("role") == "server" else "client"

        formbox, form_lay = panel()
        grid = QGridLayout()
        form_lay.addLayout(grid)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        self.mode_note = theme.label("", "caption")
        form_lay.insertWidget(0, self.mode_note)
        self.ttype = QComboBox()
        self.ttype.addItems(["Printer dan folder", "Printer", "Folder"])
        self.host = QLineEdit()
        self.host.setPlaceholderText("Nama atau IP server")
        self.host.setText(str(ctx.settings.get("last_server") or "") if self.mode == "client" else "localhost")
        self.find_btn = QPushButton("Cari server…")
        self.find_btn.setToolTip("Buka halaman Client untuk mencari server di jaringan")
        self.find_btn.clicked.connect(self.find_server.emit)
        host_box = QWidget()
        hb = QHBoxLayout(host_box)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(8)
        hb.addWidget(self.host, 1)
        hb.addWidget(self.find_btn)
        self.share = QLineEdit()
        self.share.setPlaceholderText("Nama share folder / printer")
        self.error = QLineEdit()
        self.error.setPlaceholderText("Kode/pesan error persis, mis. 0x0000011B (opsional)")
        for edit in (self.host, self.share, self.error):
            edit.returnPressed.connect(self.start)
        for row_, col, text, field, span in (
            (0, 0, "Jenis target", self.ttype, 1), (0, 1, "Nama share", self.share, 1),
            (2, 0, "Server", host_box, 2), (4, 0, "Error", self.error, 2),
        ):
            cap = theme.label(text, "caption")
            if field is host_box:
                self.host_cap, self.host_box = cap, host_box
            cap.setBuddy(self.host if field is host_box else field)
            if row_:
                cap.setContentsMargins(0, 8, 0, 0)
            grid.addWidget(cap, row_, col, 1, span)
            grid.addWidget(field, row_ + 1, col, 1, span)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addWidget(formbox)
        self.set_mode(self.mode)

        row = QHBoxLayout()
        self.go = QPushButton("Mulai scan")
        theme.set_role(self.go, "primary")
        self.go.clicked.connect(self.start)
        self.export = QPushButton("Ekspor laporan…")
        self.export.setEnabled(False)
        self.export.clicked.connect(self._export)
        self.print_btn = QPushButton("Cetak…")
        self.print_btn.setEnabled(False)
        self.print_btn.setToolTip("Cetak laporan (Ctrl+P)")
        self.print_btn.clicked.connect(self.print_report)
        self.cp_id = QPushButton("Salin ID kasus")
        self.cp_id.setEnabled(False)
        self.cp_id.clicked.connect(self._copy_id)
        self.fix = QPushButton("Perbaiki otomatis…")
        self.fix.setEnabled(False)
        self.fix.setToolTip("Aktif setelah scan menemukan sesuatu yang bisa diperbaiki atau dipandu.")
        self.fix.clicked.connect(self._open_repair)
        row.addWidget(self.go)
        row.addWidget(self.export)
        row.addWidget(self.print_btn)
        row.addWidget(self.cp_id)
        row.addStretch(1)
        row.addWidget(self.fix)
        lay.addLayout(row)

        self.summary = QWidget()
        self.summary_lay = QHBoxLayout(self.summary)
        self.summary_lay.setContentsMargins(0, 0, 0, 0)
        self.summary_lay.setSpacing(8)
        self.summary.setVisible(False)
        self.fix.setEnabled(False)
        lay.addWidget(self.summary)

        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar.setTextVisible(False)
        self.status = theme.label("", "caption")
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Pemeriksaan", "Hasil", "Penjelasan"])
        self.tree.setAlternatingRowColors(True)
        self.causes = QTextBrowser()
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.tree)
        split.addWidget(self.causes)
        split.setSizes([320, 200])
        self.empty = theme.label(_EMPTY, "empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.results = QStackedWidget()
        self.results.addWidget(self.empty)
        self.results.addWidget(split)
        lay.addWidget(self.results, 1)

    def set_mode(self, mode: str) -> None:
        """Mode komputer menentukan isian: server = komputer ini (tanpa kolom server), client = server yang dituju."""
        self.mode = "server" if mode == "server" else "client"
        server = self.mode == "server"
        self.host_cap.setVisible(not server)
        self.host_box.setVisible(not server)
        if server:
            self.host.setText("localhost")
            self.mode_note.setText("Mode Server: yang diperiksa adalah komputer ini. Isi nama share bila ingin memeriksa folder "
                                   "yang dibagikan.")
            self.share.setPlaceholderText("Nama share folder (opsional)")
        else:
            if self.host.text().strip().lower() == "localhost":
                self.host.clear()
            self.mode_note.setText("Mode Client: isi server yang gagal diakses. Belum tahu namanya? Klik Cari server.")
            self.share.setPlaceholderText("Nama share printer atau folder")

    def prefill(self, role: str, ttype: str, host: str, share: str = "", error: str = "") -> None:
        self.set_mode(role)
        self.ttype.setCurrentIndex({"both": 0, "printer": 1, "folder": 2}.get(ttype, 0))
        self.host.setText(host)
        self.share.setText(share)
        self.error.setText(error)

    def check_server(self, host: str, share: str, ttype: str) -> None:
        """Dari halaman Client: periksa koneksi ke printer/folder di server tanpa mengisi form lagi."""
        if self._thread is not None:
            return
        self.prefill("client", ttype, host, share)
        self.start()

    def scan_this_computer(self) -> None:
        """Dashboard > Scan sekarang: periksa printer dan spooler di komputer ini tanpa mengisi form."""
        if self._thread is not None:
            return
        self.set_mode("server")                # komputer ini yang diperiksa
        self.ttype.setCurrentIndex(1)          # printer
        self.host.setText("localhost")
        self.share.clear()
        self.error.clear()
        self.start()

    def start(self) -> None:
        if self._thread is not None:
            return
        try:
            req = ScanRequest(Role.SERVER if self.mode == "server" else Role.CLIENT,
                              (TargetType.BOTH, TargetType.PRINTER, TargetType.FOLDER)[self.ttype.currentIndex()],
                              self.host.text(), self.share.text(), self.error.text())
            svc = self.ctx.scan_service()
        except ValidationError as exc:
            QMessageBox.warning(self, "Input tidak valid", str(exc))
            return
        self.go.setEnabled(False)
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self.status.setText("Memeriksa…")
        self.summary.setVisible(False)
        self.empty.setText("Memeriksa target. Hasil muncul di sini setelah selesai.")
        self.results.setCurrentIndex(0)
        self._thread, self._worker = QThread(), ScanWorker(svc, req)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._progress)
        self._worker.finished.connect(self._done)
        self._worker.failed.connect(self._failed)
        self._thread.start()

    def _progress(self, done: int, total: int, name: str) -> None:
        self.bar.setMaximum(total)
        self.bar.setValue(done)
        self.status.setText(f"Memeriksa ({done} dari {total}): {name}")

    def _cleanup(self) -> None:
        self._thread.quit()
        self._thread.wait()
        self._thread = self._worker = None
        self.go.setEnabled(True)
        self.bar.setVisible(False)

    def _failed(self, msg: str) -> None:
        self._cleanup()
        self.status.setText("Pemeriksaan gagal dijalankan.")
        self.empty.setText("Pemeriksaan tidak dapat dijalankan. Periksa pesan kesalahan, lalu coba lagi.")
        self.results.setCurrentIndex(0)
        QMessageBox.critical(self, "Kesalahan", msg)

    def _done(self, o) -> None:
        self._cleanup()
        self.outcome = o
        self.status.setText(f"Selesai. ID kasus {o.case_id}. Tidak ada perubahan dilakukan pada sistem.")
        self.export.setEnabled(True)
        self.print_btn.setEnabled(True)
        self.cp_id.setEnabled(True)
        self._fill_summary(o)
        from nsd.application.repair_plan import build_plan
        from nsd.rules.loader import load_rules

        plan = build_plan(o.findings, load_rules().rules)
        self.fix.setEnabled(bool(plan.auto or plan.manual))
        self.fix.setText(f"Perbaiki otomatis… ({len(plan.auto)})" if plan.auto else "Perbaiki otomatis…")
        self.scanned.emit()
        self.tree.clear()
        for st, title in _HEAD:
            rows = [c for c in o.checks if c.status is st]
            if not rows:
                continue
            color = QBrush(QColor(theme.status_color(st)))
            top = QTreeWidgetItem([f"{title} ({len(rows)})"])
            top.setForeground(0, color)
            font = top.font(0)
            font.setBold(True)
            top.setFont(0, font)
            self.tree.addTopLevelItem(top)
            for c in rows:
                item = QTreeWidgetItem([c.title, st.tag, c.detail])
                item.setForeground(1, color)
                top.addChild(item)
            top.setExpanded(st in (Status.FAIL, Status.WARNING))
        for i in range(3):
            self.tree.resizeColumnToContents(i)
        html = []
        for f in o.findings:
            acts = "".join(f"<li>{escape(a['text'])}</li>" if a["operation"] == "advise" else
                           f"<li><b>Disarankan (belum diterapkan):</b> {escape(a['operation'])}</li>" for a in f.actions)
            html.append(f"<h4>{escape(f.title)} <small>(keyakinan {escape(str(f.confidence))}, "
                        f"risiko {escape(str(f.risk))})</small></h4>"
                        f"<p>{escape(f.explanation)}</p><ul>{acts}</ul><p><i>{escape(f.decision_text)}</i></p>")
        self.causes.setHtml("".join(html) or "<p>Tidak ada aturan yang cocok dengan bukti. Itu bukan bukti "
                            "bahwa tidak ada masalah; lihat pemeriksaan 'Belum diperiksa'.</p>")
        self.results.setCurrentIndex(1)

    def _open_repair(self) -> None:
        from nsd.ui.repair_dialog import RepairDialog

        if self.outcome is None:
            return
        dlg = RepairDialog(self.ctx, self.outcome, self)
        dlg.exec()
        if dlg.applied_any:
            self.start()                       # scan ulang dengan masukan yang sama untuk membuktikan hasilnya

    def _fill_summary(self, o) -> None:
        while self.summary_lay.count():
            w = self.summary_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        tone = {Status.FAIL: "fail", Status.WARNING: "warn", Status.PASS: "ok", Status.UNKNOWN: "unknown"}
        for st, title in _HEAD:
            n = o.count(st)
            if n:
                self.summary_lay.addWidget(theme.chip(f"{n} {title.lower()}", tone[st]))
        self.summary_lay.addStretch(1)
        self.summary.setVisible(True)

    def _export(self) -> None:
        if self.outcome:
            ExportDialog(self.outcome, self.ctx.settings.get("redact_exports"), self).exec()

    def print_report(self) -> None:
        """Buka popup Print Layout untuk laporan. Pengaturan 'samarkan' berlaku juga di sini."""
        if self.outcome is None:
            return
        from nsd.printing import TextJob
        from nsd.ui.print_dialog import PrintLayoutDialog

        redact = self.ctx.settings.get("redact_exports")
        redact = True if redact is None else bool(redact)
        PrintLayoutDialog(TextJob(build_text(self.outcome, redact), f"Laporan {self.outcome.case_id}"), parent=self).exec()

    def _copy_id(self) -> None:
        if self.outcome:
            QGuiApplication.clipboard().setText(self.outcome.case_id)
