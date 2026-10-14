from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from nsd.application.report_service import build_json, build_text
from nsd.models import Role, ScanRequest, Status, TargetType
from nsd.security.allowlist import ValidationError
from nsd.ui.widgets.worker import ScanWorker

_HEAD = [(Status.FAIL, "Masalah ditemukan"), (Status.WARNING, "Peringatan"),
         (Status.PASS, "Lulus"), (Status.UNKNOWN, "Belum diperiksa")]


class ExportDialog(QDialog):
    """Pratinjau sebelum ekspor; penyamaran aktif secara default."""

    def __init__(self, outcome, redact_default: bool, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ekspor laporan")
        self.resize(760, 520)
        self.o = outcome
        lay = QVBoxLayout(self)
        self.chk = QCheckBox("Samarkan nama komputer, IP, share, printer, dan pengguna")
        self.chk.setChecked(redact_default)
        self.chk.toggled.connect(self._refresh)
        lay.addWidget(self.chk)
        self.fmt = QComboBox()
        self.fmt.addItems(["Teks (.txt)", "JSON (.json)"])
        self.fmt.currentIndexChanged.connect(self._refresh)
        lay.addWidget(self.fmt)
        self.view = QPlainTextEdit(readOnly=True)
        lay.addWidget(self.view)
        row = QHBoxLayout()
        save = QPushButton("Simpan…")
        save.clicked.connect(self._save)
        close = QPushButton("Tutup")
        close.clicked.connect(self.reject)
        row.addStretch(1); row.addWidget(save); row.addWidget(close)
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
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self.outcome, self._thread, self._worker = ctx, None, None, None
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.role = QComboBox(); self.role.addItems(["Client (komputer yang mengakses)", "Server (komputer yang membagikan)"])
        self.role.setCurrentIndex(0 if ctx.settings.get("role") == "client" else 1)
        self.ttype = QComboBox(); self.ttype.addItems(["Printer dan folder", "Printer", "Folder"])
        self.host = QLineEdit(); self.host.setPlaceholderText("Nama komputer atau alamat IP server")
        self.share = QLineEdit(); self.share.setPlaceholderText("Nama share folder / printer")
        self.error = QLineEdit(); self.error.setPlaceholderText("Kode/pesan error persis, mis. 0x0000011B (opsional)")
        form.addRow("Peran komputer ini", self.role); form.addRow("Jenis target", self.ttype)
        form.addRow("Server / target", self.host); form.addRow("Nama share", self.share)
        form.addRow("Error", self.error)
        lay.addLayout(form)
        row = QHBoxLayout()
        self.go = QPushButton("Scan && Diagnosa"); self.go.clicked.connect(self.start)
        self.fix = QPushButton("Perbaiki Otomatis"); self.fix.setEnabled(False)
        self.fix.setToolTip("Belum tersedia: Fase 1 bersifat baca-saja. Saran perbaikan tampil di panel penyebab.")
        self.export = QPushButton("Ekspor laporan…"); self.export.setEnabled(False); self.export.clicked.connect(self._export)
        self.print_btn = QPushButton("Cetak…"); self.print_btn.setEnabled(False); self.print_btn.clicked.connect(self._print)
        self.cp_id = QPushButton("Salin ID kasus"); self.cp_id.setEnabled(False); self.cp_id.clicked.connect(self._copy_id)
        for b in (self.go, self.fix, self.export, self.print_btn, self.cp_id):
            row.addWidget(b)
        lay.addLayout(row)
        self.bar = QProgressBar(); self.bar.setVisible(False)
        self.status = QLabel(""); lay.addWidget(self.bar); lay.addWidget(self.status)
        split = QSplitter(Qt.Vertical)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Pemeriksaan", "Hasil", "Penjelasan"])
        self.causes = QTextBrowser()
        split.addWidget(self.tree); split.addWidget(self.causes); split.setSizes([320, 200])
        lay.addWidget(split, 1)

    def start(self) -> None:
        if self._thread is not None:
            return
        try:
            req = ScanRequest(Role.CLIENT if self.role.currentIndex() == 0 else Role.SERVER,
                              (TargetType.BOTH, TargetType.PRINTER, TargetType.FOLDER)[self.ttype.currentIndex()],
                              self.host.text(), self.share.text(), self.error.text())
            svc = self.ctx.scan_service()
        except ValidationError as exc:
            QMessageBox.warning(self, "Input tidak valid", str(exc)); return
        self.go.setEnabled(False); self.bar.setVisible(True); self.bar.setValue(0); self.status.setText("Memeriksa…")
        self._thread, self._worker = QThread(), ScanWorker(svc, req)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda d, t, n: (self.bar.setMaximum(t), self.bar.setValue(d)))
        self._worker.finished.connect(self._done); self._worker.failed.connect(self._failed)
        self._thread.start()

    def _cleanup(self) -> None:
        self._thread.quit(); self._thread.wait()
        self._thread = self._worker = None
        self.go.setEnabled(True); self.bar.setVisible(False)

    def _print(self) -> None:
        if self.outcome is None:
            return
        from nsd.printing import TextJob
        from nsd.ui.print_dialog import PrintLayoutDialog

        raw = self.ctx.settings.get("redact_exports")
        redact = True if raw is None else bool(raw)   # aman: samarkan bila pengaturan tidak ada
        PrintLayoutDialog(TextJob(build_text(self.outcome, redact), f"Laporan {self.outcome.case_id}"), parent=self).exec()

    def _failed(self, msg: str) -> None:
        self._cleanup(); self.status.setText("Pemeriksaan gagal dijalankan."); QMessageBox.critical(self, "Kesalahan", msg)

    def _done(self, o) -> None:
        self._cleanup(); self.outcome = o
        self.status.setText(f"Selesai. ID kasus {o.case_id}. Tidak ada perubahan dilakukan pada sistem.")
        self.export.setEnabled(True); self.print_btn.setEnabled(True); self.cp_id.setEnabled(True)
        self.tree.clear()
        for st, title in _HEAD:
            rows = [c for c in o.checks if c.status is st]
            if not rows:
                continue
            top = QTreeWidgetItem([f"{title} ({len(rows)})"]); self.tree.addTopLevelItem(top)
            for c in rows:
                top.addChild(QTreeWidgetItem([c.title, f"{st.tag}", c.detail]))
            top.setExpanded(st in (Status.FAIL, Status.WARNING))
        for i in range(3):
            self.tree.resizeColumnToContents(i)
        html = []
        for f in o.findings:
            acts = "".join(f"<li>{a['text']}</li>" if a["operation"] == "advise" else
                           f"<li><b>Disarankan (belum diterapkan):</b> {a['operation']}</li>" for a in f.actions)
            html.append(f"<h4>{f.title} <small>(keyakinan {f.confidence}, risiko {f.risk})</small></h4>"
                        f"<p>{f.explanation}</p><ul>{acts}</ul><p><i>{f.decision_text}</i></p>")
        self.causes.setHtml("".join(html) or "<p>Tidak ada aturan yang cocok dengan bukti. Itu bukan bukti "
                            "bahwa tidak ada masalah; lihat pemeriksaan 'Belum diperiksa'.</p>")

    def _export(self) -> None:
        if self.outcome:
            ExportDialog(self.outcome, self.ctx.settings.get("redact_exports"), self).exec()

    def _copy_id(self) -> None:
        if self.outcome:
            QGuiApplication.clipboard().setText(self.outcome.case_id)
