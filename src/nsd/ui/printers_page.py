from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
                               QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from nsd.application import printers
from nsd.ui import theme
from nsd.ui.dashboard_page import _cell
from nsd.ui.widgets.worker import run_async


class PrinterDetailDialog(QDialog):
    def __init__(self, p: printers.PrinterInfo, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(p.name)
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)
        top = QHBoxLayout()
        top.addWidget(theme.label(p.name, "section"), 1)
        top.addWidget(theme.chip(p.status_text, p.tone))
        lay.addLayout(top)
        tabs = QTabWidget()
        over, props = QWidget(), QWidget()
        for page, rows in ((over, (("Status", p.status_text), ("Driver", p.driver or "-"), ("Port", p.port or "-"))),
                           (props, (("Nama", p.name), ("Berbagi", f"Ya, sebagai {p.share_name}" if p.shared else "Tidak"),
                                    ("Driver", p.driver or "-"), ("Port", p.port or "-")))):
            f = QFormLayout(page)
            f.setContentsMargins(0, 16, 0, 0)
            f.setVerticalSpacing(10)
            for k, v in rows:
                f.addRow(theme.label(k, "caption"), theme.label(v, selectable=True))
        test = QPushButton("Cetak halaman uji…")
        test.clicked.connect(self._test_print)
        ol = over.layout()
        ol.addRow(test)
        tabs.addTab(over, "Ringkasan")
        tabs.addTab(props, "Properti")
        lay.addWidget(tabs, 1)
        close = QPushButton("Tutup")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

    def _test_print(self) -> None:
        from nsd.printing import RulerTestJob
        from nsd.ui.print_dialog import PrintLayoutDialog

        PrintLayoutDialog(RulerTestJob(), parent=self).exec()


class PrintersPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self._all = ctx, []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(14)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari printer")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.search.setAccessibleName("Cari printer")
        self.search.textChanged.connect(self._render)
        self.refresh_btn = QPushButton("Muat ulang")
        self.refresh_btn.clicked.connect(self.reload)
        lay.addWidget(theme.header("Daftar printer", "Printer yang terpasang di komputer ini.", self.search, self.refresh_btn))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nama printer", "Status", "Driver", "Port", ""])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda i: self._detail(i.row()))
        self.note = theme.label("", "empty")
        self.note.setAlignment(Qt.AlignCenter)
        self.views = QStackedWidget()
        self.views.addWidget(self.note)
        self.views.addWidget(self.table)
        lay.addWidget(self.views, 1)
        self.total = theme.label("", "caption")
        lay.addWidget(self.total)
        self.reload()

    def reload(self) -> None:
        self.refresh_btn.setEnabled(False)
        self.note.setText("Membaca daftar printer…")
        self.views.setCurrentIndex(0)
        ad = self.ctx.adapter
        run_async(self, lambda: printers.list_printers(ad), self._loaded, lambda m: self._loaded(printers.Listing([], False, m)))

    def _loaded(self, listing: printers.Listing) -> None:
        self.refresh_btn.setEnabled(True)
        self._all = listing.items
        if not listing.available:
            self.note.setText(f"Daftar printer tidak dapat dibaca. {listing.reason}")
            self.total.setText("")
            return
        self._render()

    def _render(self) -> None:
        q = self.search.text().strip().lower()
        rows = [p for p in self._all if q in p.name.lower() or q in p.driver.lower()]
        if not rows:
            self.note.setText("Tidak ada printer yang cocok dengan pencarian." if self._all else
                              "Belum ada printer terpasang di komputer ini.")
            self.views.setCurrentIndex(0)
            self.total.setText(f"Total: {len(self._all)} printer")
            return
        self.table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(p.name))
            self.table.setCellWidget(i, 1, _cell(theme.chip(p.status_text, p.tone)))
            self.table.setItem(i, 2, QTableWidgetItem(p.driver))
            self.table.setItem(i, 3, QTableWidgetItem(p.port))
            b = QPushButton("Detail")
            theme.set_role(b, "link")
            b.setAccessibleName(f"Detail {p.name}")
            b.clicked.connect(lambda _=False, p=p: PrinterDetailDialog(p, self).exec())
            self.table.setCellWidget(i, 4, _cell(b))
        self.table.resizeColumnToContents(0)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 80)
        self.views.setCurrentIndex(1)
        self.total.setText(f"Total: {len(self._all)} printer" + (f" ({len(rows)} ditampilkan)" if len(rows) != len(self._all) else ""))

    def _detail(self, row: int) -> None:
        name = self.table.item(row, 0)
        p = next((x for x in self._all if name and x.name == name.text()), None)
        if p:
            PrinterDetailDialog(p, self).exec()
