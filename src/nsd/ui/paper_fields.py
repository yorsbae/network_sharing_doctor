"""Isian lebar x tinggi dengan pilihan satuan (mm, cm, inci). Nilai keluar selalu dalam mm."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget

from nsd.paper.models import MAX_MM, MIN_MM
from nsd.paper.units import UNITS, from_mm, to_mm


class SizeFields(QWidget):
    def __init__(self, width_mm: float = 210, height_mm: float = 330) -> None:
        super().__init__()
        self.w, self.h = QDoubleSpinBox(), QDoubleSpinBox()
        self.unit = QComboBox()
        for key, label, _f in UNITS:
            self.unit.addItem(label, key)
        self.w.setAccessibleName("Lebar")
        self.h.setAccessibleName("Tinggi")
        self.unit.setAccessibleName("Satuan")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.w, 1)
        row.addWidget(QLabel("x"))
        row.addWidget(self.h, 1)
        row.addWidget(self.unit)
        self._key = "mm"
        self._mm = [width_mm, height_mm]      # nilai tepat; kotak angka hanya tampilan yang dibulatkan
        self._configure("mm")
        self.w.setValue(width_mm)
        self.h.setValue(height_mm)
        self.w.valueChanged.connect(lambda v: self._edited(0, v))
        self.h.valueChanged.connect(lambda v: self._edited(1, v))
        self.unit.currentIndexChanged.connect(self._unit_changed)

    def _edited(self, i: int, value: float) -> None:
        self._mm[i] = to_mm(value, self._key)

    def _configure(self, key: str) -> None:
        dec = 1 if key == "mm" else 2
        for s in (self.w, self.h):
            s.setDecimals(dec)
            s.setRange(from_mm(MIN_MM, key), from_mm(MAX_MM, key))
            s.setSingleStep(1 if key == "mm" else 0.1)
            s.setSuffix(f" {self.unit.currentText()}")

    def _unit_changed(self) -> None:
        keep = tuple(self._mm)
        self._key = self.unit.currentData()
        for s in (self.w, self.h):
            s.blockSignals(True)
        self._configure(self._key)
        self.w.setValue(from_mm(keep[0], self._key))
        self.h.setValue(from_mm(keep[1], self._key))
        for s in (self.w, self.h):
            s.blockSignals(False)
        self._mm = list(keep)

    def mm(self) -> tuple[float, float]:
        return self._mm[0], self._mm[1]
