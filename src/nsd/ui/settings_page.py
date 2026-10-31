from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFormLayout, QMessageBox, QSpinBox, QVBoxLayout, QWidget

from nsd.ui import theme
from nsd.ui.widgets.cards import panel


class SettingsPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        s = ctx.settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        body = QWidget()
        body.setMaximumWidth(760)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(theme.header("Pengaturan", "Perubahan tersimpan otomatis."))

        f = QFormLayout()
        f.setVerticalSpacing(12)
        f.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f.addRow("Folder data", theme.label(str(ctx.data_dir), selectable=True))
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
        lay.addWidget(theme.label("Server atau Client dipilih lewat tombol Ganti mode di menu kiri. Autostart server ada "
                                  "di halaman Server.", "caption"))
        lay.addWidget(self._repair_section())

        for w in ctx.warnings:
            lay.addWidget(theme.callout("Peringatan", w))
        outer.addWidget(body)
        outer.addStretch(1)

    def _repair_section(self) -> QWidget:
        box, bl = panel()
        bl.addWidget(theme.label("Perbaikan otomatis", "section"))
        self.repair = QCheckBox("Izinkan perbaikan otomatis (dengan persetujuan tiap perbaikan)")
        self.repair.setChecked(bool(self.ctx.settings.get("execution_enabled")))

        def toggled(on: bool) -> None:
            self.ctx.settings.set("execution_enabled", bool(on))
            self.ctx.adapter.allow_mutation = bool(on)

        self.repair.toggled.connect(toggled)
        bl.addWidget(self.repair)
        bl.addWidget(theme.label("Saat ini hanya menyalakan layanan Windows yang berhenti. Perlu hak administrator, "
                                 "keadaan awal disimpan, hasil diverifikasi, dan semuanya dicatat di log audit.", "caption"))
        return box

    @staticmethod
    def _set_theme(settings, value: str) -> None:
        settings.set("theme", value)
        app = QApplication.instance()
        if app is not None:
            theme.apply_theme(app, value)
