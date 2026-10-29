from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QPushButton, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from nsd.application import printers
from nsd.models import Status
from nsd.ui import theme
from nsd.ui.labels import fmt_time
from nsd.ui.widgets.cards import StatCard, action_button, panel
from nsd.ui.widgets.worker import run_async

_NETWORK_LAYERS = {"Jaringan", "Resolusi nama", "Layanan dan protokol", "Firewall", "Sharing", "Autentikasi dan izin"}
_ORDER = {"fail": 0, "warning": 1, "unknown": 2, "pass": 3}
_TONE = {"fail": "fail", "warning": "warn", "unknown": "unknown", "pass": "ok"}
_TEXT = {"fail": "Gagal", "warning": "Perhatian", "unknown": "Belum diperiksa", "pass": "Lulus"}


class DashboardPage(QWidget):
    start_scan = Signal()     # pindai komputer ini sekarang
    open_scan = Signal()      # buka halaman Scan printer (isi target sendiri)
    goto = Signal(str)        # 'printers' | 'queue' | 'log'

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self._loaded_at = ctx, 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(18)

        self.last_scan = theme.label("", "caption", wrap=False)
        self.scan_btn = QPushButton("Scan sekarang")
        theme.set_role(self.scan_btn, "primary")
        self.scan_btn.clicked.connect(self.start_scan.emit)
        lay.addWidget(theme.header("Dashboard", "Ringkasan printer, spooler, dan hasil pemeriksaan terakhir.",
                                   self.last_scan, self.scan_btn))

        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_printers = StatCard("printer", "Status printer")
        self.c_spooler = StatCard("spooler", "Print spooler")
        self.c_network = StatCard("network", "Berbagi jaringan")
        self.c_total = StatCard("queue", "Antrean cetak")
        for i, c in enumerate((self.c_printers, self.c_spooler, self.c_network, self.c_total)):
            grid.addWidget(c, 0, i)
            grid.setColumnStretch(i, 1)
        lay.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(14)
        results, rl = panel()
        rl.addWidget(theme.label("Hasil pemeriksaan terakhir", "section"))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Komponen", "Status"])
        self._style_table(self.table)
        self.empty = theme.label("Belum ada hasil. Klik Scan sekarang untuk memeriksa printer di komputer ini.", "empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.views = QStackedWidget()
        self.views.addWidget(self.empty)
        self.views.addWidget(self.table)
        rl.addWidget(self.views, 1)
        row.addWidget(results, 3)

        actions, al = panel()
        al.addWidget(theme.label("Aksi cepat", "section"))
        self.a_scan = action_button("scan", "Scan printer", "Periksa target tertentu")
        self.a_list = action_button("printer", "Daftar printer", "Lihat printer yang terpasang")
        self.a_queue = action_button("queue", "Antrean cetak", "Lihat pekerjaan yang menunggu")
        self.a_log = action_button("log", "Log", "Riwayat pemeriksaan")
        self.a_scan.clicked.connect(self.open_scan.emit)
        self.a_list.clicked.connect(lambda: self.goto.emit("printers"))
        self.a_queue.clicked.connect(lambda: self.goto.emit("queue"))
        self.a_log.clicked.connect(lambda: self.goto.emit("log"))
        for b in (self.a_scan, self.a_list, self.a_queue, self.a_log):
            al.addWidget(b)
        al.addStretch(1)
        row.addWidget(actions, 2)
        lay.addLayout(row, 1)

        if not ctx.adapter.is_elevated():
            lay.addWidget(theme.callout(
                "Berjalan tanpa hak administrator",
                "Sebagian pemeriksaan terbatas. Diagnosis tetap berjalan; yang tidak dapat diperiksa ditandai "
                "Belum diperiksa."))
        for w in ctx.warnings:
            lay.addWidget(theme.callout("Peringatan", w))
        self.refresh()

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if time.monotonic() - self._loaded_at > 30:       # jangan menjalankan PowerShell tiap pindah menu
            self.refresh()

    @staticmethod
    def _style_table(t: QTableWidget) -> None:
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.setShowGrid(False)
        t.verticalHeader().setDefaultSectionSize(42)
        t.setFrameShape(t.Shape.NoFrame)
        t.verticalHeader().setVisible(False)
        h = t.horizontalHeader()
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.Fixed)
        t.setColumnWidth(1, 150)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def refresh(self) -> None:
        """Muat ulang kartu (data langsung, di thread latar) dan hasil scan terakhir (dari riwayat)."""
        self._loaded_at = time.monotonic()
        self._load_last_scan()
        ad = self.ctx.adapter

        def fetch():
            return printers.list_printers(ad), printers.spooler_state(ad), printers.list_jobs(ad)

        run_async(self, fetch, self._apply_live, lambda _m: self._apply_live(None))

    def _apply_live(self, data) -> None:
        if data is None:
            for c in (self.c_printers, self.c_spooler, self.c_total):
                c.set("Belum diperiksa", "Gagal membaca data", "unknown")
            return
        pl, (sp_text, sp_tone), jl = data
        if not pl.available:
            self.c_printers.set("Belum diperiksa", pl.reason, "unknown")
            self.c_total.set("Belum diperiksa", "", "unknown")
        else:
            ok = sum(1 for p in pl.items if p.tone == "ok")
            n = len(pl.items)
            tone = "unknown" if n == 0 else "ok" if ok == n else "warn"
            self.c_printers.set(f"{ok} / {n} siap" if n else "Tidak ada",
                                "" if ok == n else f"{n - ok} perlu dicek", tone)
        self.c_spooler.set(sp_text, "", sp_tone)
        if jl.available:
            n = len(jl.items)
            self.c_total.set(f"{n} pekerjaan" if n else "Kosong", f"{len(pl.items)} printer terpasang" if pl.available else "",
                             "warn" if any(j.tone in ("fail", "warn") for j in jl.items) else "ok" if pl.available else "unknown")

    def _load_last_scan(self) -> None:
        rows = self.ctx.cases.list_cases(1)
        if not rows:
            self.last_scan.setText("Belum pernah di-scan")
            self.views.setCurrentIndex(0)
            self.c_network.set("Belum di-scan", "", "unknown")
            return
        case = rows[0]
        self.last_scan.setText(f"Scan terakhir {fmt_time(case['started_at'])}")
        checks = sorted(self.ctx.cases.get_checks(case["id"]), key=lambda c: _ORDER.get(c["status"], 9))
        net_bad = [c for c in checks if c["layer"] in _NETWORK_LAYERS and c["status"] in ("fail", "warning")]
        worst = "fail" if any(c["status"] == "fail" for c in net_bad) else "warn"
        self.c_network.set(f"{len(net_bad)} masalah", "Dari scan terakhir", worst if net_bad else "ok")
        shown = checks[:7]
        self.table.setRowCount(len(shown))
        for i, c in enumerate(shown):
            item = QTableWidgetItem(c["title"])
            item.setToolTip(c["detail"])
            self.table.setItem(i, 0, item)
            self.table.setCellWidget(i, 1, _cell(theme.chip(_TEXT.get(c["status"], c["status"]), _TONE.get(c["status"], "unknown"))))
        self.views.setCurrentIndex(1)


def _cell(w: QWidget) -> QWidget:
    """Bungkus chip agar rata kiri dan tidak melar memenuhi sel."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(6, 0, 6, 0)
    lay.addWidget(w)
    lay.addStretch(1)
    return box
