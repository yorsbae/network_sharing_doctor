from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from nsd.application import error_lookup
from nsd.rules.loader import load_rules
from nsd.ui import theme
from nsd.ui.widgets.cards import panel


class ErrorPage(QWidget):
    """Cari kode error (mis. 0x0000011B): penjelasan, langkah, dan apakah ada perbaikan otomatis. Dari katalog aturan."""

    scan_with = Signal(str)       # kode ternormalisasi -> halaman Scan printer

    def __init__(self, ctx) -> None:
        super().__init__()
        self.rules = load_rules().rules
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(14)
        lay.addWidget(theme.header("Kode error", "Tempel kode error atau kata kunci. Penjelasan ini petunjuk, bukan diagnosis; "
                                   "scan dengan kode itu memeriksa bukti yang sebenarnya."))
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Mis. 0x0000011B, 0x80070035, atau spooler")
        self.query.setAccessibleName("Kode error atau kata kunci")
        self.query.setClearButtonEnabled(True)
        self.query.returnPressed.connect(self.search)
        self.btn = QPushButton("Cari")
        theme.set_role(self.btn, "primary")
        self.btn.clicked.connect(self.search)
        row.addWidget(self.query, 1)
        row.addWidget(self.btn)
        lay.addLayout(row)

        codes = error_lookup.known_codes(self.rules)
        grid = QGridLayout()
        grid.setSpacing(4)
        lay.addWidget(theme.label("Kode yang ada di katalog", "caption"))
        for i, c in enumerate(codes):
            b = QPushButton(c)
            theme.set_role(b, "link")
            b.clicked.connect(lambda _=False, c=c: self._pick(c))
            grid.addWidget(b, i // 4, i % 4)
        lay.addLayout(grid)

        self.out = QVBoxLayout()
        self.out.setSpacing(10)
        holder = QWidget()
        holder.setLayout(self.out)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)
        self._message("Masukkan kode untuk melihat artinya dan apa yang bisa dilakukan.")

    def _pick(self, code: str) -> None:
        self.query.setText(code)
        self.search()

    def _clear(self) -> None:
        while self.out.count():
            w = self.out.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _message(self, text: str) -> None:
        self._clear()
        lb = theme.label(text, "empty")
        lb.setAlignment(Qt.AlignCenter)
        self.out.addWidget(lb)
        self.out.addStretch(1)

    def search(self) -> None:
        res = error_lookup.lookup(self.rules, self.query.text())
        self.result = res
        if not res.query:
            return self._message("Masukkan kode atau kata kunci terlebih dahulu.")
        self._clear()
        if not res.entries:
            msg = (f"Kode {res.code} belum ada di katalog, jadi belum ada penjelasan yang bisa dipastikan. "
                   "Scan tetap memakai kode ini untuk memprioritaskan bukti." if res.code else
                   "Tidak ada yang cocok. Coba kode error (0x...) atau kata lain.")
            self.out.addWidget(theme.label(msg, "empty"))
        for e in res.entries:
            box, bl = panel()
            top = QHBoxLayout()
            top.addWidget(theme.label(e.title, "section"), 1)
            for c in e.codes[:3]:
                top.addWidget(theme.chip(c, "unknown"))
            bl.addLayout(top)
            if e.explanation:
                bl.addWidget(theme.label(e.explanation, selectable=True))
            for s in e.steps:
                bl.addWidget(theme.label("Yang bisa dilakukan: " + s, selectable=True))
            bl.addWidget(theme.label(e.auto_text or "Perbaikan otomatis: tidak ada untuk kode ini. Langkahnya manual "
                                     "karena perubahan yang diperlukan dapat melemahkan keamanan atau butuh keputusan administrator.",
                                     "caption"))
            if e.escalation:
                bl.addWidget(theme.label("Jika belum berhasil: " + e.escalation, "caption"))
            self.out.addWidget(box)
        if res.code:
            b = QPushButton(f"Periksa dengan kode {res.code}")
            theme.set_role(b, "primary")
            b.clicked.connect(lambda: self.scan_with.emit(res.code))
            row = QHBoxLayout()
            row.addWidget(b)
            row.addStretch(1)
            self.out.addLayout(row)
        self.out.addStretch(1)
