from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QHBoxLayout, QListWidget, QMainWindow, QStackedWidget, QWidget

from nsd import __version__
from nsd.bootstrap import bootstrap
from nsd.ui.dashboard_page import DashboardPage
from nsd.ui.diagnose_page import DiagnosePage
from nsd.ui.history_page import HistoryPage
from nsd.ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.setWindowTitle(f"Network Sharing Doctor {__version__}")
        self.resize(1000, 680)
        self.nav, self.stack = QListWidget(), QStackedWidget()
        self.nav.setFixedWidth(160)
        dash = DashboardPage(ctx)
        pages = [("Beranda", dash), ("Diagnosa", DiagnosePage(ctx)), ("Riwayat", HistoryPage(ctx)),
                 ("Pengaturan", SettingsPage(ctx))]
        for name, w in pages:
            self.nav.addItem(name); self.stack.addWidget(w)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        dash.start_scan.connect(lambda: self.nav.setCurrentRow(1))
        root = QWidget(); lay = QHBoxLayout(root)
        lay.addWidget(self.nav); lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)


def run_gui() -> int:
    app = QApplication(sys.argv)
    win = MainWindow(bootstrap())
    win.show()
    return app.exec()
