from __future__ import annotations

from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from nsd.application.repair_plan import build_plan
from nsd.rules.loader import load_rules
from nsd.ui import theme
from nsd.ui.widgets.worker import run_async
from nsd.windows.privilege import relaunch_as_admin

_ENABLE_TEXT = (
    "Perbaikan otomatis akan mengubah komputer ini. Saat ini hanya satu jenis perubahan yang didukung: "
    "menyalakan layanan Windows yang berhenti (Print Spooler, Workstation, Server). Tipe startup tidak diubah.\n\n"
    "Tiap perbaikan tetap meminta persetujuan Anda, keadaan awal disimpan, hasilnya diverifikasi ulang, "
    "dan semuanya dicatat di log audit. Aktifkan?")


class RepairDialog(QDialog):
    """Pratinjau, persetujuan, penerapan, dan verifikasi perbaikan. Tidak ada yang diubah tanpa klik 'Terapkan'."""

    def __init__(self, ctx, outcome, parent=None) -> None:
        super().__init__(parent)
        self.ctx, self.outcome = ctx, outcome
        self.applied_any, self._rollbacks, self._busy = False, [], False
        self.plan = build_plan(outcome.findings, load_rules().rules)
        self.setWindowTitle("Perbaiki otomatis")
        self.resize(640, 620)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(12)
        root.addWidget(theme.header("Perbaiki otomatis", "Pratinjau dulu. Tidak ada yang berubah sampai Anda menekan Terapkan."))

        self.prereq = QFrame()
        self.prereq.setProperty("role", "panel")
        self.prereq_lay = QVBoxLayout(self.prereq)
        self.prereq_lay.setContentsMargins(14, 10, 14, 10)
        root.addWidget(self.prereq)

        body = QWidget()
        self.body_lay = QVBoxLayout(body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(8)
        self.checks: list[tuple[QCheckBox, object]] = []
        self._build_items()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        self.log.setAccessibleName("Hasil perbaikan")
        self.log.setVisible(False)
        root.addWidget(self.log)

        row = QHBoxLayout()
        self.undo = QPushButton("Kembalikan perubahan")
        self.undo.setVisible(False)
        self.undo.clicked.connect(self._rollback)
        self.apply_btn = QPushButton("Terapkan yang dipilih")
        theme.set_role(self.apply_btn, "primary")
        self.apply_btn.clicked.connect(self._apply)
        close = QPushButton("Tutup")
        close.clicked.connect(self.accept)
        row.addWidget(self.undo)
        row.addStretch(1)
        row.addWidget(close)
        row.addWidget(self.apply_btn)
        root.addLayout(row)
        self._refresh_prereq()

    # -- isi ---------------------------------------------------------------
    def _build_items(self) -> None:
        lay = self.body_lay
        lay.addWidget(theme.label("Dapat diperbaiki otomatis", "section"))
        if not self.plan.auto:
            lay.addWidget(theme.label("Tidak ada perbaikan otomatis untuk temuan ini. Lihat langkah manual di bawah.", "caption"))
        for item in self.plan.auto:
            cb = QCheckBox(item.finding.title)
            cb.setChecked(True)
            cb.toggled.connect(self._sync_apply)
            self.checks.append((cb, item))
            lay.addWidget(cb)
            lay.addWidget(theme.label(f"{item.summary} Risiko rendah; keadaan awal disimpan dan hasilnya diverifikasi.", "caption"))
        if self.plan.manual:
            lay.addSpacing(8)
            lay.addWidget(theme.label("Perlu langkah manual", "section"))
        for item in self.plan.manual:
            box, bl = QFrame(), None
            box.setProperty("role", "callout")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 10, 12, 10)
            bl.setSpacing(4)
            bl.addWidget(theme.label(item.finding.title, "section"))
            bl.addWidget(theme.label(item.summary))
            bl.addWidget(theme.label(f"Kenapa tidak otomatis: {item.reason}", "caption"))
            lay.addWidget(box)
        lay.addStretch(1)

    def _refresh_prereq(self) -> None:
        while self.prereq_lay.count():
            it = self.prereq_lay.takeAt(0)
            if it.layout():
                while it.layout().count():
                    w = it.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
            elif it.widget():
                it.widget().deleteLater()
        self.enabled = bool(self.ctx.settings.get("execution_enabled"))
        self.elevated = bool(self.ctx.adapter.is_elevated())
        for ok, name, on, off, btn_text, handler in (
            (self.enabled, "Perbaikan otomatis", "Aktif", "Nonaktif", "Aktifkan…", self._enable),
            (self.elevated, "Hak administrator", "Ya", "Tidak", "Jalankan ulang sebagai administrator", self._relaunch),
        ):
            r = QHBoxLayout()
            r.addWidget(theme.label(name, wrap=False))
            r.addWidget(theme.chip(on if ok else off, "ok" if ok else "warn"))
            r.addStretch(1)
            if not ok:
                b = QPushButton(btn_text)
                b.clicked.connect(handler)
                r.addWidget(b)
            self.prereq_lay.addLayout(r)
        self._sync_apply()

    def _sync_apply(self) -> None:
        any_checked = any(cb.isChecked() for cb, _ in self.checks)
        self.apply_btn.setEnabled(self.enabled and self.elevated and any_checked and not self._busy)
        if not (self.enabled and self.elevated):
            self.apply_btn.setToolTip("Aktifkan perbaikan otomatis dan jalankan sebagai administrator terlebih dahulu.")
        else:
            self.apply_btn.setToolTip("")

    # -- prasyarat -----------------------------------------------------------
    def _enable(self) -> None:
        if QMessageBox.question(self, "Aktifkan perbaikan otomatis", _ENABLE_TEXT, QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            self.ctx.settings.set("execution_enabled", True)
            self.ctx.adapter.allow_mutation = True
            self._refresh_prereq()

    def _relaunch(self) -> None:
        if QMessageBox.question(self, "Jalankan sebagai administrator",
                                "Aplikasi akan ditutup lalu dibuka lagi sebagai administrator (Windows akan meminta "
                                "persetujuan Anda). Hasil scan ini tetap tersimpan di Log. Lanjutkan?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            if relaunch_as_admin():
                QApplication.quit()
            else:
                QMessageBox.information(self, "Administrator", "Permintaan tidak dilanjutkan. Tidak ada yang berubah.")

    # -- eksekusi --------------------------------------------------------------
    def _show(self, lines: list[str]) -> None:
        self.log.setVisible(True)
        self.log.setPlainText("\n".join(lines))

    def _apply(self) -> None:
        chosen = [item for cb, item in self.checks if cb.isChecked()]
        if not chosen or self._busy:
            return
        self._busy = True
        self.apply_btn.setEnabled(False)
        self._show(["Menerapkan dan memverifikasi… (hingga 15 detik per perbaikan)"])
        executor, case_id = self.ctx.repair_executor(), self.outcome.case_id

        def work():
            return [(item, executor.execute(item.finding, case_id, approved=True)) for item in chosen]

        run_async(self, work, self._applied, lambda m: self._applied_failed(m))

    def _applied(self, results) -> None:
        self._busy = False
        lines = []
        for item, res in results:
            lines.append(f"{item.finding.title}: {res.outcome}. {res.message}")
            lines += ["   " + s for s in res.steps]
            if res.outcome == "verified":
                self.applied_any = True
            if res.rollback_available and res.action_id:
                self._rollbacks.append(res.action_id)
        if self.applied_any:
            lines.append("\nSelesai. Setelah Tutup, scan diulang otomatis untuk memastikan masalahnya hilang.")
        self._show(lines)
        self.undo.setVisible(bool(self._rollbacks))
        self._sync_apply()

    def _applied_failed(self, msg: str) -> None:
        self._busy = False
        self._show([f"Gagal menjalankan perbaikan: {msg}", "Tidak ada klaim berhasil; periksa log audit."])
        self._sync_apply()

    def _rollback(self) -> None:
        ids, executor, case_id = list(self._rollbacks), self.ctx.repair_executor(), self.outcome.case_id
        self.undo.setEnabled(False)

        def work():
            return [executor.rollback(case_id, a, approved=True) for a in ids]

        def done(results):
            self._rollbacks.clear()
            self.applied_any = False
            self.undo.setVisible(False)
            self._show(["Pemulihan:"] + [f"{r.outcome}. {r.message}" for r in results])

        run_async(self, work, done, lambda m: self._show([f"Pemulihan gagal: {m}"]))
