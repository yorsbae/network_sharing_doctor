from __future__ import annotations

import sys

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QMessageBox, QHBoxLayout, QListWidget, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)

from nsd import __version__
from nsd.bootstrap import bootstrap
from nsd.ui import theme
from nsd.ui.dashboard_page import DashboardPage
from nsd.ui.diagnose_page import DiagnosePage
from nsd.ui.history_page import HistoryPage
from nsd.ui.paper_page import PaperPage
from nsd.ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.setWindowTitle(f"Network Sharing Doctor {__version__}")
        self.resize(1040, 700)
        self.setMinimumSize(880, 560)
        self.nav, self.stack = QListWidget(), QStackedWidget()
        self.nav.setObjectName("nav")
        self.nav.setAccessibleName("Menu utama")
        dash, self.diagnose = DashboardPage(ctx), DiagnosePage(ctx)
        pages = [("Beranda", dash), ("Diagnosa", self.diagnose), ("Kertas", PaperPage(ctx)),
                 ("Riwayat", HistoryPage(ctx)), ("Pengaturan", SettingsPage(ctx))]
        for i, (name, w) in enumerate(pages):
            self.nav.addItem(name)
            self.nav.item(i).setToolTip(f"{name} (Ctrl+{i + 1})")
            self.stack.addWidget(w)
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))
        QShortcut(QKeySequence.Print, self, activated=self.print_current)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        dash.start_scan.connect(self._open_diagnose)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 14)
        sl.setSpacing(2)
        brand = theme.label("Network Sharing Doctor")
        brand.setObjectName("brand")
        version = theme.label(f"Versi {__version__}")
        version.setObjectName("brandVersion")
        sl.addWidget(brand)
        sl.addWidget(version)
        sl.addSpacing(16)
        sl.addWidget(self.nav, 1)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def print_current(self) -> None:
        """Ctrl+P: cetak laporan bila ada; selain itu tawarkan memilih berkas PDF."""
        if self.diagnose.outcome is not None:
            self.diagnose.print_report()
        else:
            self.print_pdf_file()

    def print_pdf_file(self, path: str | None = None) -> None:
        from nsd.printing import PdfJob
        from nsd.ui.print_dialog import PrintLayoutDialog

        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Pilih PDF yang akan dicetak", "", "PDF (*.pdf)")
        if not path:
            return
        try:
            job = PdfJob(path)
        except ValueError as exc:
            QMessageBox.warning(self, "PDF tidak dapat dibuka", str(exc))
            return
        PrintLayoutDialog(job, parent=self).exec()

    def _open_diagnose(self) -> None:
        self.nav.setCurrentRow(1)
        self.diagnose.host.setFocus()


def run_gui() -> int:
    app = QApplication(sys.argv)
    ctx = bootstrap()
    theme.apply_theme(app, ctx.settings.get("theme"))
    theme.follow_system_changes(app)
    win = MainWindow(ctx)
    win.show()
    return app.exec()
