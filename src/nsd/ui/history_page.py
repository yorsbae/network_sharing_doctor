from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from nsd.ui import theme
from nsd.ui.dashboard_page import _cell
from nsd.ui.labels import case_tone, fmt_time


class HistoryPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        days = ctx.settings.get("retention_days")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari target atau ID")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Cari log")
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(self._filter)
        self.refresh_btn = QPushButton("Muat ulang")
        self.refresh_btn.clicked.connect(self.reload)
        self.clear_btn = QPushButton("Hapus seluruh riwayat…")
        theme.set_role(self.clear_btn, "danger")
        self.clear_btn.clicked.connect(self._clear)
        lay.addWidget(theme.header("Log", f"Riwayat pemeriksaan di komputer ini, disimpan {days} hari lalu dihapus otomatis.",
                                   self.search, self.refresh_btn, self.clear_btn))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Waktu", "Peran", "Target", "Hasil"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 200)
        self.table.itemSelectionChanged.connect(self._show)
        self.detail = QPlainTextEdit(readOnly=True)
        self.detail.setPlaceholderText("Pilih satu kasus untuk melihat bukti pemeriksaannya.")
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setSizes([320, 200])

        self.empty = theme.label("Belum ada riwayat. Hasil scan tersimpan di sini.", "empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.views = QStackedWidget()
        self.views.addWidget(self.empty)
        self.views.addWidget(split)
        lay.addWidget(self.views, 1)
        self.reload()

    def reload(self) -> None:
        rows = self.ctx.cases.list_cases(200)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(("id", "started_at", "role", "target", "status")):
                text = str(r[key])
                if key == "status":
                    label, tone = case_tone(text)
                    self.table.setItem(i, j, QTableWidgetItem(""))
                    self.table.setCellWidget(i, j, _cell(theme.chip(label, tone)))
                    continue
                if key == "started_at":
                    text = fmt_time(text)
                elif key == "role":
                    text = text.capitalize()
                self.table.setItem(i, j, QTableWidgetItem(text))
        self.detail.clear()
        self._filter()
        self.views.setCurrentIndex(1 if rows else 0)
        self.clear_btn.setEnabled(bool(rows))

    def _filter(self) -> None:
        q = self.search.text().strip().lower()
        for i in range(self.table.rowCount()):
            hay = f"{self.table.item(i, 0).text()} {self.table.item(i, 3).text()}".lower()
            self.table.setRowHidden(i, bool(q) and q not in hay)

    def _show(self) -> None:
        sel = self.table.selectedItems()
        if not sel:
            return
        cid = self.table.item(sel[0].row(), 0).text()
        lines = [f"Kasus {cid}", ""]
        for c in self.ctx.cases.get_checks(cid):
            lines.append(f"[{c['status'].upper()}] {c['check_id']}: {c['detail']}")
        lines.append("")
        for p in self.ctx.cases.get_plans(cid):
            lines.append(f"Penyebab: {p['rule_id']} (keyakinan {p['confidence']}, {p['policy_decision']})")
        self.detail.setPlainText("\n".join(lines))

    def _clear(self) -> None:
        box = QMessageBox(QMessageBox.Warning, "Hapus riwayat",
                          "Hapus semua riwayat kasus dan log audit? Tindakan ini permanen.", QMessageBox.NoButton, self)
        confirm = box.addButton("Hapus riwayat", QMessageBox.DestructiveRole)
        cancel = box.addButton("Batal", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is confirm:
            self.ctx.cases.clear_history()
            self.reload()
