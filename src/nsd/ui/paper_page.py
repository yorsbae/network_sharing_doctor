"""Halaman 'Kertas & Layout': ukuran kertas lokal di client + pratinjau tata letak halaman."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from nsd.app_config import data_dir
from nsd.paper import Margins, Orientation, PageLayout, PaperError, PaperStore


class PagePreview(QWidget):
    """Menggambar halaman dengan skala proporsional: tepi kertas, margin, dan area isi."""

    def __init__(self) -> None:
        super().__init__()
        self.layout_: PageLayout | None = None
        self.setMinimumSize(320, 360)

    def set_layout(self, lay: PageLayout | None) -> None:
        self.layout_ = lay
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#e5e7eb"))
        lay = self.layout_
        if lay is None:
            p.drawText(self.rect(), Qt.AlignCenter, "Pilih ukuran kertas")
            return
        pw, ph = lay.page_mm
        pad = 24
        k = min((self.width() - 2 * pad) / pw, (self.height() - 2 * pad - 20) / ph)
        x0, y0 = (self.width() - pw * k) / 2, (self.height() - ph * k - 20) / 2
        page = QRectF(x0, y0, pw * k, ph * k)
        p.fillRect(page.translated(3, 3), QColor(0, 0, 0, 40))
        p.fillRect(page, QColor("white"))
        p.setPen(QPen(QColor("#111827"), 1)); p.drawRect(page)
        m = lay.margins
        body = QRectF(x0 + m.left * k, y0 + m.top * k, lay.content_width_mm * k, lay.content_height_mm * k)
        pen = QPen(QColor("#2563eb"), 1, Qt.DashLine); p.setPen(pen); p.drawRect(body)
        p.setPen(QColor("#6b7280")); p.setFont(QFont("", 9))
        p.drawText(body, Qt.AlignCenter, f"Area isi\n{lay.content_width_mm:g} × {lay.content_height_mm:g} mm")
        p.setPen(QColor("#111827"))
        p.drawText(QRectF(0, page.bottom() + 4, self.width(), 18), Qt.AlignCenter,
                   f"{pw:g} × {ph:g} mm")
        p.end()


class PaperPage(QWidget):
    def __init__(self, ctx=None, store: PaperStore | None = None) -> None:
        super().__init__()
        self.store = store or PaperStore(data_dir())
        self.preview = PagePreview()

        self.papers = QListWidget()
        self.orient = QComboBox(); self.orient.addItems(["Potret", "Lanskap"])
        self.margin = self._spin(0, 200, 10, " mm")
        self.scale = self._spin(10, 400, 100, " %")
        self.info = QLabel(); self.info.setWordWrap(True)

        self.name = QLineEdit(); self.name.setPlaceholderText("mis. F4 Kantor")
        self.w = self._spin(10, 2000, 210, " mm"); self.h = self._spin(10, 2000, 330, " mm")
        add, rem = QPushButton("Tambah ukuran"), QPushButton("Hapus ukuran terpilih")
        add.clicked.connect(self._add); rem.clicked.connect(self._remove)

        box = QGroupBox("Ukuran kertas baru (disimpan lokal di komputer ini)")
        form = QFormLayout(box)
        form.addRow("Nama", self.name); form.addRow("Lebar", self.w); form.addRow("Tinggi", self.h)
        form.addRow(add)

        opts = QGroupBox("Tata letak")
        of = QFormLayout(opts)
        of.addRow("Orientasi", self.orient); of.addRow("Margin", self.margin); of.addRow("Skala", self.scale)

        note = QLabel("Ukuran ini tersimpan di client dan tidak mengubah server. Apakah driver printer "
                      "menerimanya belum diperiksa di sini; lihat Fase 3 di progres.md.")
        note.setWordWrap(True)

        left = QVBoxLayout()
        left.addWidget(QLabel("Ukuran kertas")); left.addWidget(self.papers, 1); left.addWidget(rem)
        left.addWidget(box); left.addWidget(opts); left.addWidget(self.info); left.addWidget(note)
        root = QHBoxLayout(self)
        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(340)
        root.addWidget(lw); root.addWidget(self.preview, 1)

        self.papers.currentRowChanged.connect(self._refresh)
        self.orient.currentIndexChanged.connect(self._refresh)
        self.margin.valueChanged.connect(self._refresh)
        self.scale.valueChanged.connect(self._refresh)
        self._reload()

    @staticmethod
    def _spin(lo: float, hi: float, val: float, suffix: str) -> QDoubleSpinBox:
        s = QDoubleSpinBox(); s.setRange(lo, hi); s.setValue(val); s.setSuffix(suffix); s.setDecimals(1)
        return s

    def _reload(self, select: str | None = None) -> None:
        custom = {p.name for p in self.store.custom()}
        self.papers.blockSignals(True)
        self.papers.clear()
        self._items = self.store.all()
        for p in self._items:
            self.papers.addItem(p.label() + ("  [khusus]" if p.name in custom else ""))
        row = next((i for i, p in enumerate(self._items) if p.name == select), 1 if len(self._items) > 1 else 0)
        self.papers.setCurrentRow(row)
        self.papers.blockSignals(False)
        self._refresh()

    def _refresh(self, *_a) -> None:
        row = self.papers.currentRow()
        if not (0 <= row < len(self._items)):
            self.preview.set_layout(None); return
        o = Orientation.LANDSCAPE if self.orient.currentIndex() else Orientation.PORTRAIT
        m = self.margin.value()
        try:
            lay = PageLayout(self._items[row], o, Margins(m, m, m, m), self.scale.value())
        except PaperError as exc:
            self.info.setText(f"Tidak valid: {exc}"); self.preview.set_layout(None); return
        self.info.setText("\n".join(lay.warnings()) or f"Area isi {lay.content_width_mm:g} × {lay.content_height_mm:g} mm")
        self.preview.set_layout(lay)

    def _add(self) -> None:
        try:
            p = self.store.add(self.name.text(), self.w.value(), self.h.value())
        except PaperError as exc:
            QMessageBox.warning(self, "Ukuran tidak valid", str(exc)); return
        self.name.clear(); self._reload(p.name)

    def _remove(self) -> None:
        row = self.papers.currentRow()
        if not (0 <= row < len(self._items)):
            return
        if self._items[row].builtin:
            QMessageBox.information(self, "Tidak bisa dihapus", "Ukuran bawaan tidak dapat dihapus."); return
        self.store.remove(self._items[row].name); self._reload()
