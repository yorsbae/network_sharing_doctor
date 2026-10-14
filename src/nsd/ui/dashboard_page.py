from __future__ import annotations

import platform

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    start_scan = Signal()

    def __init__(self, ctx) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<h2>Network Sharing Doctor</h2>"))
        elevated = ctx.adapter.is_elevated()
        lay.addWidget(QLabel(f"Komputer: {platform.node()}"))
        lay.addWidget(QLabel(f"Sistem: {platform.system()} {platform.release()} (build {platform.version()})"))
        lay.addWidget(QLabel(f"Peran bawaan: {ctx.settings.get('role')}"))
        lay.addWidget(QLabel(f"Hak administrator: {'ya' if elevated else 'tidak'}"))
        if not elevated:
            note = QLabel("Berjalan tanpa hak administrator: pemeriksaan tertentu terbatas. "
                          "Diagnosis tetap berjalan dan hasil yang tidak dapat diperiksa ditandai 'Belum diperiksa'.")
            note.setWordWrap(True)
            lay.addWidget(note)
        for w in ctx.warnings:
            lay.addWidget(QLabel("⚠ " + w))
        mode = QLabel("Mode: Fase 1 — hanya membaca. Aplikasi ini tidak mengubah pengaturan Windows.")
        mode.setWordWrap(True)
        lay.addWidget(mode)
        btn = QPushButton("Scan && Diagnosa")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self.start_scan.emit)
        lay.addWidget(btn)
        lay.addStretch(1)
