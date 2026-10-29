from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QPushButton, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from nsd.application import printers
from nsd.ui import theme
from nsd.ui.dashboard_page import _cell
from nsd.ui.widgets.worker import run_async


def _size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} B"


class QueuePage(QWidget):
    """Antrean cetak, hanya dibaca. Memuat ulang tiap 10 detik selama halaman terlihat."""

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self._busy = ctx, False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(14)
        self.refresh_btn = QPushButton("Muat ulang")
        self.refresh_btn.clicked.connect(self.reload)
        lay.addWidget(theme.header("Antrean cetak", "Pekerjaan cetak yang sedang diproses. Halaman ini hanya membaca; "
                                   "menjeda atau membatalkan dilakukan dari pengaturan printer Windows.", self.refresh_btn))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Dokumen", "Printer", "Status", "Halaman", "Ukuran", "Masuk"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.note = theme.label("Membaca antrean…", "empty")
        self.note.setAlignment(Qt.AlignCenter)
        self.views = QStackedWidget()
        self.views.addWidget(self.note)
        self.views.addWidget(self.table)
        lay.addWidget(self.views, 1)
        self.total = theme.label("", "caption")
        lay.addWidget(self.total)
        self.timer = QTimer(self)
        self.timer.setInterval(10_000)
        self.timer.timeout.connect(self.reload)
        self.reload()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        self.timer.start()
        self.reload()

    def hideEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()
        super().hideEvent(e)

    def reload(self) -> None:
        if self._busy:
            return
        self._busy = True
        ad = self.ctx.adapter
        run_async(self, lambda: printers.list_jobs(ad), self._loaded,
                  lambda m: self._loaded(printers.Listing([], False, m)))

    def _loaded(self, listing: printers.Listing) -> None:
        self._busy = False
        if not listing.available:
            self.note.setText(f"Antrean tidak dapat dibaca. {listing.reason}")
            self.views.setCurrentIndex(0)
            self.total.setText("")
            return
        jobs = listing.items
        self.total.setText(f"Total: {len(jobs)} pekerjaan")
        if not jobs:
            self.note.setText("Antrean kosong. Pekerjaan cetak akan muncul di sini saat dikirim ke printer.")
            self.views.setCurrentIndex(0)
            return
        self.table.setRowCount(len(jobs))
        for i, j in enumerate(jobs):
            self.table.setItem(i, 0, QTableWidgetItem(j.document))
            self.table.setItem(i, 1, QTableWidgetItem(j.printer))
            self.table.setCellWidget(i, 2, _cell(theme.chip(j.status_text, j.tone)))
            self.table.setItem(i, 3, QTableWidgetItem(str(j.pages) if j.pages else "-"))
            self.table.setItem(i, 4, QTableWidgetItem(_size(j.size)))
            self.table.setItem(i, 5, QTableWidgetItem(j.submitted))
        self.table.resizeColumnToContents(1)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(5, 170)
        self.views.setCurrentIndex(1)
