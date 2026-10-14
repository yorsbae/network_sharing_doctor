from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox, QWidget


class SettingsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        s = ctx.settings
        f = QFormLayout(self)
        f.addRow("Folder data", QLabel(str(ctx.data_dir)))
        pol = QLabel("Diagnosis saja (dikunci pada Fase 1)"); f.addRow("Level otomatisasi", pol)
        role = QComboBox(); role.addItems(["client", "server"]); role.setCurrentText(s.get("role"))
        role.currentTextChanged.connect(lambda v: s.set("role", v)); f.addRow("Peran bawaan", role)
        red = QCheckBox("Samarkan data sensitif pada ekspor (disarankan)"); red.setChecked(s.get("redact_exports"))
        red.toggled.connect(lambda v: s.set("redact_exports", bool(v))); f.addRow("Privasi", red)
        days = QSpinBox(); days.setRange(1, 3650); days.setValue(s.get("retention_days"))
        days.valueChanged.connect(lambda v: s.set("retention_days", int(v))); f.addRow("Simpan riwayat (hari)", days)
        for w in ctx.warnings:
            f.addRow("⚠", QLabel(w))
