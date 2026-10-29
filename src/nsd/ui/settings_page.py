from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFormLayout, QSpinBox, QVBoxLayout, QWidget

from nsd.ui import theme
from nsd.ui.labels import ROLE_LABELS


class SettingsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        s = ctx.settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        body = QWidget()
        body.setMaximumWidth(720)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(theme.header("Pengaturan", "Perubahan tersimpan otomatis."))

        f = QFormLayout()
        f.setVerticalSpacing(12)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.addRow("Folder data", theme.label(str(ctx.data_dir), selectable=True))
        f.addRow("Level otomatisasi", theme.label("Diagnosis saja (dikunci pada Fase 1)"))

        role = QComboBox()
        for key, text in ROLE_LABELS.items():
            role.addItem(text, key)
        role.setCurrentIndex(max(0, role.findData(s.get("role"))))
        role.currentIndexChanged.connect(lambda _i: s.set("role", role.currentData()))
        f.addRow("Peran bawaan", role)

        mode = QComboBox()
        for key, text in theme.THEME_CHOICES:
            mode.addItem(text, key)
        mode.setCurrentIndex(max(0, mode.findData(s.get("theme"))))
        mode.currentIndexChanged.connect(lambda _i: self._set_theme(s, mode.currentData()))
        f.addRow("Tema", mode)

        red = QCheckBox("Samarkan data sensitif pada ekspor (disarankan)")
        red.setChecked(s.get("redact_exports"))
        red.toggled.connect(lambda v: s.set("redact_exports", bool(v)))
        f.addRow("Privasi", red)

        days = QSpinBox()
        days.setRange(1, 3650)
        days.setSuffix(" hari")
        days.setValue(s.get("retention_days"))
        days.valueChanged.connect(lambda v: s.set("retention_days", int(v)))
        f.addRow("Simpan riwayat", days)
        lay.addLayout(f)

        for w in ctx.warnings:
            lay.addWidget(theme.callout("Peringatan", w))
        outer.addWidget(body)
        outer.addStretch(1)

    @staticmethod
    def _set_theme(settings, value: str) -> None:
        settings.set("theme", value)
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, value)
