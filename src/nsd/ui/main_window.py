from __future__ import annotations

import platform
import sys

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from nsd import __version__
from nsd.bootstrap import bootstrap
from nsd.ui import icons, theme
from nsd.ui.client_page import ClientPage
from nsd.ui.dashboard_page import DashboardPage
from nsd.ui.diagnose_page import DiagnosePage
from nsd.ui.history_page import HistoryPage
from nsd.ui.error_page import ErrorPage
from nsd.ui.labels import case_tone
from nsd.ui.paper_page import PaperPage
from nsd.ui.printers_page import PrintersPage
from nsd.ui.queue_page import QueuePage
from nsd.ui.server_page import ServerPage
from nsd.ui.settings_page import SettingsPage


# (label menu, ikon). Urutan = urutan halaman pada stack.
NAV = (("Dashboard", "home"), ("Server", "server"), ("Client", "client"), ("Scan printer", "scan"),
       ("Kode error", "code"), ("Daftar printer", "printer"), ("Antrean cetak", "queue"), ("Kertas", "paper"),
       ("Log", "log"), ("Pengaturan", "settings"))
# Menu yang tampil per mode (indeks NAV). Belum memilih mode: hanya Dashboard (pilih mode) dan Pengaturan.
MENU_BY_ROLE = {None: {0, 9}, "server": {1, 3, 5, 6, 8, 9}, "client": {2, 3, 4, 7, 8, 9}}
GOTO = {"server": 1, "client": 2, "scan": 3, "errors": 4, "printers": 5, "queue": 6, "log": 8}


def _nav_icon(name: str) -> QIcon:
    t = theme.tokens()
    ic = QIcon()
    ic.addPixmap(icons.pixmap(name, t.side_text, 18), QIcon.Normal, QIcon.Off)
    ic.addPixmap(icons.pixmap(name, "#FFFFFF", 18), QIcon.Selected, QIcon.Off)
    ic.addPixmap(icons.pixmap(name, "#FFFFFF", 18), QIcon.Active, QIcon.Off)
    return ic


class MainWindow(QMainWindow):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("Network Sharing Doctor")
        self.resize(1180, 760)
        self.setMinimumSize(980, 600)
        self.nav, self.stack = QListWidget(), QStackedWidget()
        self.nav.setObjectName("nav")
        self.nav.setAccessibleName("Menu utama")
        self.nav.setIconSize(QSize(18, 18))
        self.dash, self.diagnose = DashboardPage(ctx), DiagnosePage(ctx)
        self.history = HistoryPage(ctx)
        self.errors = ErrorPage(ctx)
        self.server, self.client = ServerPage(ctx), ClientPage(ctx)
        pages = [self.dash, self.server, self.client, self.diagnose, self.errors, PrintersPage(ctx), QueuePage(ctx),
                 PaperPage(ctx), self.history, SettingsPage(ctx)]
        for i, ((name, _ic), w) in enumerate(zip(NAV, pages)):
            self.nav.addItem(name)
            self.stack.addWidget(w)
            key = str((i + 1) % 10)            # Ctrl+1 sampai Ctrl+9, lalu Ctrl+0 untuk menu ke-10
            self.nav.item(i).setToolTip(f"{name} (Ctrl+{key})")
            QShortcut(QKeySequence(f"Ctrl+{key}"), self, activated=lambda i=i: self.nav.setCurrentRow(i))
        QShortcut(QKeySequence.Print, self, activated=self.print_current)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.dash.start_scan.connect(self._scan_this_computer)
        self.dash.open_scan.connect(self._open_diagnose)
        self.dash.goto.connect(self._goto)
        self.diagnose.scanned.connect(self._after_scan)
        self.errors.scan_with.connect(self._scan_with_code)
        self.server.scan_self.connect(self._scan_this_computer)
        self.client.check_requested.connect(self._check_server)
        self.diagnose.find_server.connect(lambda: self.nav.setCurrentRow(GOTO["client"]))

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 20, 14, 14)
        sl.setSpacing(2)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        tile = QFrame()
        tile.setFixedSize(38, 38)
        tile.setStyleSheet("background:%s;border-radius:10px;" % theme.tokens().side_sel)
        tl = QVBoxLayout(tile)
        tl.setContentsMargins(0, 0, 0, 0)
        self._brand_icon = QLabel()
        self._brand_icon.setAlignment(Qt.AlignCenter)
        tl.addWidget(self._brand_icon)
        names = QVBoxLayout()
        names.setSpacing(0)
        brand = theme.label("Network Sharing Doctor", wrap=True)
        brand.setObjectName("brand")
        version = theme.label("Diagnosa dan perbaikan berbagi jaringan", wrap=True)
        version.setObjectName("brandVersion")
        names.addWidget(brand)
        names.addWidget(version)
        brand_row.addWidget(tile)
        brand_row.addLayout(names, 1)
        sl.addLayout(brand_row)
        sl.addSpacing(18)
        sl.addWidget(self.nav, 1)
        div = QFrame()
        div.setObjectName("sideDivider")
        sl.addWidget(div)
        sl.addSpacing(8)
        cap = theme.label("Status sistem", wrap=False)
        cap.setObjectName("sideMeta")
        self.side_status = theme.label("", wrap=False)
        self.side_status.setObjectName("sideStatus")
        meta = theme.label(f"{platform.system()} {platform.release()}  v{__version__}", wrap=True)
        meta.setObjectName("sideMeta")
        for w in (cap, self.side_status, meta):
            sl.addWidget(w)
        sl.addSpacing(8)
        self.mode_label = theme.label("", wrap=False)
        self.mode_label.setObjectName("sideStatus")
        self.mode_btn = QPushButton("Ganti mode")
        self.mode_btn.setAccessibleName("Ganti mode komputer antara Server dan Client")
        self.mode_btn.clicked.connect(self._change_mode)
        sl.addWidget(self.mode_label)
        sl.addWidget(self.mode_btn)

        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(side)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.installEventFilter(self)
        theme.notifier.changed.connect(self._restyle)
        self._restyle()
        self._refresh_side_status()
        self._apply_role(open_role_page=True)

    # ---- mode komputer: satu-satunya tempat memilih/mengganti peran ----
    def _role(self) -> str | None:
        if not self.ctx.settings.get("role_chosen"):
            return None
        return "server" if self.ctx.settings.get("role") == "server" else "client"

    def _apply_role(self, open_role_page: bool = False) -> None:
        role = self._role()
        allowed = MENU_BY_ROLE[role]
        for i in range(self.nav.count()):
            self.nav.item(i).setHidden(i not in allowed)
        self.mode_label.setText({"server": "Mode: Server", "client": "Mode: Client"}.get(role, "Mode: belum dipilih"))
        self.mode_btn.setVisible(role is not None)
        if role:
            self.diagnose.set_mode(role)
        if open_role_page and role:
            self.nav.setCurrentRow(GOTO[role])
        elif self.nav.currentRow() not in allowed:
            self.nav.setCurrentRow(GOTO[role] if role else 0)

    def _goto(self, key: str) -> None:
        self._apply_role()
        self.nav.setCurrentRow(GOTO[key])

    def _change_mode(self) -> None:
        """Tampilkan lagi pilihan mode (Dashboard); menu lain menyesuaikan setelah mode dipilih."""
        self.nav.item(0).setHidden(False)
        self.nav.setCurrentRow(0)

    def eventFilter(self, obj, ev):  # noqa: N802
        """Cincin fokus menu hanya saat navigasi keyboard; klik mouse dan fokus awal tidak memunculkannya."""
        if obj is self.nav and ev.type() in (QEvent.FocusIn, QEvent.FocusOut):
            kb = ev.type() == QEvent.FocusIn and ev.reason() in (
                Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)
            self.nav.setProperty("kbfocus", kb)
            self.nav.style().unpolish(self.nav)
            self.nav.style().polish(self.nav)
        return super().eventFilter(obj, ev)

    def _restyle(self) -> None:
        for i, (_n, ic) in enumerate(NAV):
            self.nav.item(i).setIcon(_nav_icon(ic))
        self._brand_icon.setPixmap(icons.pixmap("printer", "#FFFFFF", 22))

    def _refresh_side_status(self) -> None:
        rows = self.ctx.cases.list_cases(1)
        text = case_tone(rows[0]["status"])[0] if rows else "Belum di-scan"
        self.side_status.setText(text)

    def _after_scan(self) -> None:
        self._refresh_side_status()
        self.dash.refresh()
        self.history.reload()

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

    def _scan_with_code(self, code: str) -> None:
        self.nav.setCurrentRow(GOTO["scan"])
        self.diagnose.error.setText(code)
        self.diagnose.host.setFocus()

    def _scan_this_computer(self) -> None:
        self.nav.setCurrentRow(GOTO["scan"])
        self.diagnose.scan_this_computer()

    def _check_server(self, host: str, share: str, ttype: str) -> None:
        self.nav.setCurrentRow(GOTO["scan"])
        self.diagnose.check_server(host, share, ttype)

    def _open_diagnose(self) -> None:
        self.nav.setCurrentRow(GOTO["scan"])
        self.diagnose.host.setFocus()


def run_gui() -> int:
    app = QApplication(sys.argv)
    ctx = bootstrap()
    theme.apply_theme(app, ctx.settings.get("theme"))
    theme.follow_system_changes(app)
    win = MainWindow(ctx)
    win.show()
    return app.exec()
