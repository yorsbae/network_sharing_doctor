"""Popup 'Print Layout' (gaya aplikasi akuntansi): printer, kertas, margin, skala, pratinjau, Cetak."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from nsd.app_config import data_dir
from nsd.paper import Margins, Orientation, PageLayout, PaperError, PaperSize, PaperStore
from nsd.ui import theme
from nsd.ui.paper_fields import SizeFields
from nsd.printing import PrintError, PrintJob, RulerTestJob, available_printers, print_job, render_preview
from nsd.printing.render import PDF_LABEL, printer_hard_margin_mm

_CUSTOM_NOTE = ("Ukuran khusus dikirim ke printer bersama dokumen. Apakah driver printer menerimanya apa adanya "
                "tidak bisa dipastikan dari sini: cetak 'Halaman uji' dan periksa dengan penggaris.")


class AddPaperDialog(QDialog):
    def __init__(self, store: PaperStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tambah ukuran kertas")
        self.store, self.added = store, None
        form = QFormLayout(self)
        self.name = QLineEdit(); self.name.setPlaceholderText("mis. F4 Kantor")
        self.size = SizeFields()
        self.w, self.h = self.size.w, self.size.h
        form.addRow("Nama", self.name); form.addRow("Lebar x tinggi", self.size)
        row = QHBoxLayout()
        ok, no = QPushButton("Simpan"), QPushButton("Batal")
        theme.set_role(ok, "primary"); ok.setDefault(True)
        ok.clicked.connect(self._save); no.clicked.connect(self.reject)
        row.addStretch(1); row.addWidget(ok); row.addWidget(no); form.addRow(row)

    def _save(self) -> None:
        try:
            self.added = self.store.add(self.name.text(), *self.size.mm())
        except PaperError as exc:
            QMessageBox.warning(self, "Ukuran tidak valid", str(exc)); return
        self.accept()


class PrintLayoutDialog(QDialog):
    def __init__(self, job: PrintJob, store: PaperStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Print Layout")
        self.resize(940, 640)
        self.job, self.store = job, store or PaperStore(data_dir())
        self.page = 0
        self.last_printed: tuple | None = None

        self.printer = QComboBox()
        self.paper = QComboBox()
        self.orient = QComboBox(); self.orient.addItems(["Potret", "Lanskap"])
        self.m = {k: self._spin(0, 200, 10, " mm") for k in ("top", "right", "bottom", "left")}
        self.scale = self._spin(10, 400, 100, " %")
        self.copies = QSpinBox(); self.copies.setRange(1, 99)
        self.note = QLabel(); self.note.setWordWrap(True)
        self.preview = QLabel(alignment=Qt.AlignCenter); self.preview.setMinimumSize(380, 460)
        theme.set_role(self.preview, "canvas")
        self.pager = QLabel("")
        prev, nxt = QPushButton("Sebelumnya"), QPushButton("Berikutnya")
        prev.clicked.connect(self._prev_page); nxt.clicked.connect(self._next_page)

        add = QPushButton("Tambah ukuran…"); add.clicked.connect(self._add_paper)
        ruler = QPushButton("Cetak halaman uji…"); ruler.clicked.connect(self._print_ruler)
        self.go = QPushButton("Cetak"); self.go.setDefault(True); self.go.clicked.connect(self._print)
        theme.set_role(self.go, "primary")
        cancel = QPushButton("Tutup"); cancel.clicked.connect(self.reject)

        gw = QWidget(self)                       # induk eksplisit: hindari objek tanpa pemilik
        grid = QGridLayout(gw)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, (lbl, k) in enumerate((("Atas", "top"), ("Kanan", "right"), ("Bawah", "bottom"), ("Kiri", "left"))):
            grid.addWidget(QLabel(lbl, gw), i // 2, (i % 2) * 2); grid.addWidget(self.m[k], i // 2, (i % 2) * 2 + 1)
        form = QFormLayout()
        form.addRow("Printer", self.printer)
        prow = QHBoxLayout(); prow.addWidget(self.paper, 1); prow.addWidget(add)
        form.addRow("Kertas", prow)
        form.addRow("Orientasi", self.orient)
        form.addRow("Margin", gw)
        form.addRow("Skala", self.scale); form.addRow("Salinan", self.copies)
        left = QVBoxLayout(); left.addLayout(form); left.addWidget(self.note); left.addStretch(1)
        btn = QHBoxLayout(); btn.addWidget(ruler); btn.addStretch(1); btn.addWidget(self.go); btn.addWidget(cancel)
        left.addLayout(btn)
        nav = QHBoxLayout(); nav.addStretch(1); nav.addWidget(prev); nav.addWidget(self.pager); nav.addWidget(nxt); nav.addStretch(1)
        right = QVBoxLayout(); right.addWidget(self.preview, 1); right.addLayout(nav)
        root = QHBoxLayout(self)
        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(400)
        root.addWidget(lw); root.addLayout(right, 1)

        self._load()
        for w in (self.printer, self.paper, self.orient):
            w.currentIndexChanged.connect(self._on_change)
        for w in (*self.m.values(), self.scale):
            w.valueChanged.connect(self._on_change)
        self._on_change()

    @staticmethod
    def _spin(lo, hi, val, suffix) -> QDoubleSpinBox:
        s = QDoubleSpinBox(); s.setRange(lo, hi); s.setValue(val); s.setSuffix(suffix); s.setDecimals(1)
        return s

    # ---- data ----
    def _load(self, select_paper: str | None = None) -> None:
        pf = self.store.load_prefs()
        for w in (self.printer, self.paper):
            w.blockSignals(True)
        if self.printer.count() == 0:
            self.printer.addItem(PDF_LABEL)
            self.printer.addItems(available_printers())
            want = pf.get("printer")
            i = self.printer.findText(want) if want else -1
            self.printer.setCurrentIndex(i if i >= 0 else (1 if self.printer.count() > 1 else 0))
            self.orient.setCurrentIndex(1 if pf.get("orientation") == "landscape" else 0)
            for k, spin in self.m.items():
                spin.setValue(float(pf.get("margins", {}).get(k, 10)))
            self.scale.setValue(float(pf.get("scale", 100)))
        self._papers = self.store.all()
        custom = {p.name for p in self.store.custom()}
        self.paper.clear()
        for p in self._papers:
            self.paper.addItem(p.label() + ("  [khusus]" if p.name in custom else ""))
        want = select_paper or pf.get("paper") or "A4"
        idx = next((i for i, p in enumerate(self._papers) if p.name == want), 1)
        self.paper.setCurrentIndex(idx)
        for w in (self.printer, self.paper):
            w.blockSignals(False)

    def _layout(self) -> PageLayout | None:
        i = self.paper.currentIndex()
        if not (0 <= i < len(self._papers)):
            return None
        mm = {k: s.value() for k, s in self.m.items()}
        pname = self.printer.currentText()
        hard = 0.0 if pname == PDF_LABEL else printer_hard_margin_mm(pname)
        try:
            return PageLayout(self._papers[i], Orientation.LANDSCAPE if self.orient.currentIndex() else Orientation.PORTRAIT,
                              Margins(mm["top"], mm["right"], mm["bottom"], mm["left"]), self.scale.value(), hard)
        except PaperError as exc:
            self.note.setText(f"Tidak valid: {exc}")
            return None

    # ---- tampilan ----
    def _on_change(self, *_a) -> None:
        lay = self._layout()
        self.go.setEnabled(lay is not None)
        if lay is None:
            self.preview.setText("Pengaturan tidak valid"); self.pager.setText(""); return
        notes = lay.warnings()
        if self.store and any(p.name == lay.paper.name for p in self.store.custom()):
            notes.append(_CUSTOM_NOTE)
        self.note.setText("\n\n".join(notes))
        self._draw(lay)

    def _draw(self, lay: PageLayout) -> None:
        img, pages = render_preview(lay, self.job, self.page, dpi=70)
        self.page = max(0, min(self.page, pages - 1))
        pm = QPixmap.fromImage(img)
        self.preview.setPixmap(pm.scaled(self.preview.size() - QSize(16, 16), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation))
        self.pager.setText(f"Halaman {self.page + 1} dari {pages}")

    def _prev_page(self) -> None:
        self._turn(-1)

    def _next_page(self) -> None:
        self._turn(1)

    def _turn(self, d: int) -> None:
        self.page = max(0, self.page + d)
        self._on_change()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        lay = self._layout() if hasattr(self, "_papers") else None
        if lay:
            self._draw(lay)

    # ---- aksi ----
    def _add_paper(self) -> None:
        dlg = AddPaperDialog(self.store, self)
        if dlg.exec() and dlg.added:
            self._load(dlg.added.name); self._on_change()

    def _save_prefs(self, lay: PageLayout) -> None:
        m = lay.margins
        self.store.save_prefs({"printer": self.printer.currentText(), "paper": lay.paper.name,
                               "orientation": lay.orientation.value, "scale": lay.scale_percent,
                               "margins": {"top": m.top, "right": m.right, "bottom": m.bottom, "left": m.left}})

    def _run(self, job: PrintJob, label: str) -> None:
        lay = self._layout()
        if lay is None:
            return
        pname = self.printer.currentText()
        pdf = None
        if pname == PDF_LABEL:
            pdf, _ = QFileDialog.getSaveFileName(self, "Simpan PDF", "dokumen.pdf", "PDF (*.pdf)")
            if not pdf:
                return
        else:
            ok = QMessageBox.question(self, "Cetak", f"Cetak {label} ke printer '{pname}'\n"
                                      f"pada kertas {lay.paper.label()}?")
            if ok != QMessageBox.Yes:
                return
        try:
            n = print_job(lay, job, None if pdf else pname, pdf, self.copies.value())
        except PrintError as exc:
            QMessageBox.critical(self, "Gagal mencetak", str(exc)); return
        self._save_prefs(lay)
        self.last_printed = (pname, lay.paper.name, n)
        QMessageBox.information(self, "Selesai", f"{n} halaman dikirim ke {'PDF' if pdf else pname}.")

    def _print(self) -> None:
        self._run(self.job, self.job.title.lower())

    def _print_ruler(self) -> None:
        self._run(RulerTestJob(), "halaman uji")
