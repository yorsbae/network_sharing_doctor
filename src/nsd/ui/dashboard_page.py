from __future__ import annotations

import platform

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from nsd.ui import theme
from nsd.ui.labels import ROLE_LABELS


class DashboardPage(QWidget):
    start_scan = Signal()

    def __init__(self, ctx) -> None:
        super().__init__()
        elevated = ctx.adapter.is_elevated()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        body = QWidget()
        body.setMaximumWidth(720)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)

        lay.addWidget(theme.header(
            "Beranda", "Cari penyebab printer atau folder bersama yang gagal tersambung di jaringan lokal."))

        panel = QFrame()
        panel.setProperty("role", "panel")
        form = QFormLayout(panel)
        form.setContentsMargins(16, 14, 16, 14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for name, value in (
            ("Komputer", platform.node()),
            ("Sistem", f"{platform.system()} {platform.release()} (build {platform.version()})"),
            ("Peran bawaan", ROLE_LABELS.get(ctx.settings.get("role"), str(ctx.settings.get("role")))),
            ("Hak administrator", "Ya" if elevated else "Tidak"),
        ):
            form.addRow(theme.label(name, "caption"), theme.label(value, selectable=True))
        lay.addWidget(panel)

        if not elevated:
            lay.addWidget(theme.callout(
                "Berjalan tanpa hak administrator",
                "Pemeriksaan tertentu terbatas. Diagnosis tetap berjalan, dan hasil yang tidak dapat diperiksa "
                "ditandai 'Belum diperiksa'."))
        for w in ctx.warnings:
            lay.addWidget(theme.callout("Peringatan", w))

        row = QHBoxLayout()
        btn = QPushButton("Scan && Diagnosa")
        theme.set_role(btn, "primary")
        btn.setMinimumHeight(44)
        btn.setDefault(True)
        btn.clicked.connect(self.start_scan.emit)
        row.addWidget(btn)
        row.addWidget(theme.label("Fase 1: hanya membaca. Tidak ada pengaturan Windows yang diubah.", "caption"), 1)
        lay.addLayout(row)

        outer.addWidget(body)
        outer.addStretch(1)
