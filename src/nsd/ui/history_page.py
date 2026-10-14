from __future__ import annotations

from PySide6.QtWidgets import (QHBoxLayout, QMessageBox, QPushButton, QPlainTextEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)


class HistoryPage(QWidget):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        b1 = QPushButton("Muat ulang"); b1.clicked.connect(self.reload)
        b2 = QPushButton("Hapus seluruh riwayat…"); b2.clicked.connect(self._clear)
        row.addWidget(b1); row.addWidget(b2); row.addStretch(1)
        lay.addLayout(row)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Waktu (UTC)", "Peran", "Target", "Hasil"])
        self.table.itemSelectionChanged.connect(self._show)
        self.detail = QPlainTextEdit(readOnly=True)
        lay.addWidget(self.table, 2); lay.addWidget(self.detail, 1)
        self.reload()

    def reload(self) -> None:
        rows = self.ctx.cases.list_cases(200)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, key in enumerate(("id", "started_at", "role", "target", "status")):
                self.table.setItem(i, j, QTableWidgetItem(str(r[key])))
        self.detail.clear()

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
        if QMessageBox.question(self, "Hapus riwayat", "Hapus semua riwayat kasus dan log audit? Tindakan ini permanen.") \
                == QMessageBox.Yes:
            self.ctx.cases.clear_history(); self.reload()
