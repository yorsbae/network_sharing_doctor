from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QComboBox, QMessageBox, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
                               QPushButton, QWidget)

from nsd.application import client_connect, discovery, printers, server_setup
from nsd.security.allowlist import ValidationError, validate_host, validate_share
from nsd.ui import theme
from nsd.ui.widgets.cards import fit_list, panel, scroll_body
from nsd.ui.widgets.worker import run_async
from nsd.windows.powershell import RealWindowsAdapter

_KINDS = (("printer", "Printer"), ("folder", "Folder"))


class ClientPage(QWidget):
    """Komputer ini memakai printer/folder di komputer lain: pilih server, pilih printer, periksa koneksi."""

    check_requested = Signal(str, str, str)       # host, share, jenis ('printer' | 'folder')

    def __init__(self, ctx) -> None:
        super().__init__()
        self.ctx, self._stop, self._finding, self._listing = ctx, threading.Event(), False, False
        lay = scroll_body(self)
        lay.addWidget(theme.header(
            "Client", "Komputer ini memakai printer atau folder yang dibagikan komputer lain (server). "
                      "Tiga langkah: pilih server, pilih printer atau folder, lalu periksa dan pasang."))

        # Langkah 1
        box1, l1 = panel()
        l1.addWidget(theme.label("1. Pilih server", "section"))
        row = QHBoxLayout()
        self.host = QLineEdit(str(ctx.settings.get("last_server") or ""))
        self.host.setPlaceholderText("Nama komputer atau alamat IP server")
        self.host.setAccessibleName("Nama atau alamat IP server")
        self.host.setClearButtonEnabled(True)
        self.find = QPushButton("Cari server di jaringan")
        self.find.clicked.connect(self._find_clicked)
        row.addWidget(self.host, 1)
        row.addWidget(self.find)
        l1.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        l1.addWidget(self.bar)
        self.find_status = theme.label("", "caption")
        l1.addWidget(self.find_status)
        self.found = QListWidget()
        self.found.setAccessibleName("Komputer yang ditemukan")
        self.found.setVisible(False)
        self.found.currentItemChanged.connect(self._server_picked)
        l1.addWidget(self.found)
        l1.addWidget(theme.label(
            "Pencarian hanya memeriksa layanan berbagi (port 445) di jaringan lokal komputer ini, tidak mengubah apa pun, "
            "dan hanya berjalan saat Anda menekannya. Tahu nama atau alamat IP servernya? Ketik langsung di kolom.", "caption"))
        lay.addWidget(box1)

        # Langkah 2
        box2, l2 = panel()
        l2.addWidget(theme.label("2. Pilih printer atau folder", "section"))
        row = QHBoxLayout()
        self.kind = QComboBox()
        for key, text in _KINDS:
            self.kind.addItem(text, key)
        self.kind.setAccessibleName("Jenis yang diakses")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.share = QLineEdit()
        self.share.setPlaceholderText("Nama share printer")
        self.share.setAccessibleName("Nama share")
        self.share.setClearButtonEnabled(True)
        self.list_btn = QPushButton("Lihat printer di server")
        self.list_btn.clicked.connect(self._list_printers)
        row.addWidget(self.kind)
        row.addWidget(self.share, 1)
        row.addWidget(self.list_btn)
        l2.addLayout(row)
        self.list_status = theme.label("", "caption")
        l2.addWidget(self.list_status)
        self.shares = QListWidget()
        self.shares.setAccessibleName("Printer yang dibagikan server")
        self.shares.setVisible(False)
        self.shares.currentItemChanged.connect(self._share_picked)
        l2.addWidget(self.shares)
        self.kind_hint = theme.label("", "caption")
        l2.addWidget(self.kind_hint)
        lay.addWidget(box2)

        # Langkah 3
        box3, l3 = panel()
        l3.addWidget(theme.label("3. Periksa dan pasang", "section"))
        self.address = theme.label("-", "section", selectable=True)
        l3.addWidget(self.address)
        self.need = theme.label("", "caption")
        l3.addWidget(self.need)
        row = QHBoxLayout()
        self.check_btn = QPushButton("Periksa koneksi")
        theme.set_role(self.check_btn, "primary")
        self.check_btn.clicked.connect(self._check)
        self.install_btn = QPushButton("Pasang printer ini")
        self.install_btn.clicked.connect(self._install)
        self.copy_btn = QPushButton("Salin alamat")
        self.copy_btn.clicked.connect(self._copy)
        row.addWidget(self.check_btn)
        row.addWidget(self.install_btn)
        row.addWidget(self.copy_btn)
        row.addStretch(1)
        l3.addLayout(row)
        self.install_hint = theme.label("", "caption")
        l3.addWidget(self.install_hint)
        self.install_result = theme.label("", "caption", selectable=True)
        self.install_result.setVisible(False)
        l3.addWidget(self.install_result)
        lay.addWidget(box3)
        lay.addStretch(1)

        self.host.textChanged.connect(self._update)
        self.share.textChanged.connect(self._update)
        self.host.returnPressed.connect(self._list_printers)
        self._kind_changed()

    # ---- keadaan ----
    @property
    def kind_key(self) -> str:
        return self.kind.currentData()

    def set_server(self, host: str) -> None:
        self.host.setText(host)

    def _kind_changed(self) -> None:
        printer = self.kind_key == "printer"
        self.share.setPlaceholderText("Nama share printer" if printer else "Nama share folder")
        self.list_btn.setEnabled(printer and not self._listing)
        self.shares.setVisible(printer and self.shares.count() > 0)
        self.kind_hint.setText("" if printer else
                               "Daftar folder tidak dapat dibaca dari client. Ketik nama share yang diberikan pemilik server.")
        self.kind_hint.setVisible(not printer)
        self._update()

    def _valid(self) -> tuple[str, str, str]:
        """(host, share, pesan galat). Pesan kosong bila keduanya valid."""
        h, s = self.host.text().strip(), self.share.text().strip()
        if not h:
            return h, s, "Isi nama atau alamat IP server dulu."
        try:
            validate_host(h)
        except ValidationError as exc:
            return h, s, str(exc)
        if not s:
            return h, s, "Pilih atau ketik nama share."
        try:
            validate_share(s)
        except ValidationError as exc:
            return h, s, str(exc)
        return h, s, ""

    def _update(self) -> None:
        h, s, err = self._valid()
        self.address.setText(f"\\\\{h}\\{s}" if not err else "-")
        self.need.setText(err)
        self.need.setVisible(bool(err))
        self.check_btn.setEnabled(not err)
        self.copy_btn.setEnabled(not err)
        printer = self.kind_key == "printer"
        self.install_btn.setVisible(printer)
        self.install_btn.setEnabled(not err and printer and not getattr(self, "_installing", False))
        self.install_hint.setText("" if err or not printer else
                                  "Periksa koneksi dulu bila ragu. Pasang printer ini menambahkannya ke komputer ini "
                                  "tanpa perlu administrator.")
        self.install_hint.setVisible(bool(self.install_hint.text()))

    # ---- langkah 1: cari server ----
    def _find_clicked(self) -> None:
        if self._finding:
            self._stop.set()
            self.find.setEnabled(False)
            self.find_status.setText("Membatalkan pencarian…")
            return
        self._finding = True
        self._stop = stop = threading.Event()
        self.find.setText("Batalkan pencarian")
        self.bar.setVisible(True)
        self.found.setVisible(False)
        self.found.clear()
        self.find_status.setText("Mencari komputer dengan layanan berbagi di jaringan lokal…")
        run_async(self, lambda: discovery.discover(server_setup.local_ipv4_addresses(), should_stop=stop.is_set),
                  self._found, self._find_failed)

    def _find_done(self) -> None:
        self._finding = False
        self.find.setText("Cari server di jaringan")
        self.find.setEnabled(True)
        self.bar.setVisible(False)

    def _find_failed(self, msg: str) -> None:
        self._find_done()
        self.find_status.setText("Pencarian gagal dijalankan. Ketik nama atau alamat IP server secara manual.")

    def _found(self, res: discovery.DiscoveryResult) -> None:
        self._find_done()
        self.found.blockSignals(True)
        for s in res.servers:
            it = QListWidgetItem(s.label)
            it.setData(Qt.UserRole, s.host)
            self.found.addItem(it)
        self.found.blockSignals(False)
        fit_list(self.found)
        self.found.setVisible(bool(res.servers))
        if res.cancelled:
            self.find_status.setText("Pencarian dibatalkan.")
        elif res.servers:
            n = len(res.servers)
            self.find_status.setText(f"Ditemukan {n} komputer dengan layanan berbagi. Pilih servernya dari daftar.")
            if n == 1 and not self.host.text().strip():
                self.found.setCurrentRow(0)
        else:
            self.find_status.setText(res.note)

    def _server_picked(self, item, _prev=None) -> None:
        if item is not None:
            self.host.setText(item.data(Qt.UserRole))

    # ---- langkah 2: lihat printer ----
    def _list_printers(self) -> None:
        if self._listing or self.kind_key != "printer":
            return
        host = self.host.text().strip()
        try:
            validate_host(host)
        except ValidationError as exc:
            self.list_status.setText(str(exc) if host else "Isi nama atau alamat IP server dulu.")
            return
        self._listing = True
        self.list_btn.setEnabled(False)
        self.list_status.setText("Membaca daftar printer dari server…")
        ad = self.ctx.adapter
        run_async(self, lambda: printers.list_remote_printers(ad, host), self._listed, self._list_failed)

    def _list_failed(self, msg: str) -> None:
        self._listing = False
        self.list_btn.setEnabled(self.kind_key == "printer")
        self.list_status.setText("Daftar printer gagal dibaca. Ketik nama share secara manual.")

    def _listed(self, lst: printers.Listing) -> None:
        self._listing = False
        self.list_btn.setEnabled(self.kind_key == "printer")
        self.shares.blockSignals(True)
        self.shares.clear()
        for p in lst.items:
            it = QListWidgetItem(f"{p.share_name}  ({p.name}, {p.status_text})")
            it.setData(Qt.UserRole, p.share_name)
            self.shares.addItem(it)
        self.shares.blockSignals(False)
        fit_list(self.shares)
        self.shares.setVisible(bool(lst.items))
        if not lst.available:
            self.list_status.setText(lst.reason + " Anda tetap bisa mengetik nama share secara manual.")
        elif not lst.items:
            self.list_status.setText("Server terjangkau, tetapi tidak ada printer yang dibagikan. Minta pemilik server "
                                     "membuka halaman Server dan membagikan printernya.")
        else:
            self.list_status.setText(f"{len(lst.items)} printer dibagikan. Pilih salah satu.")
            if len(lst.items) == 1 and not self.share.text().strip():
                self.shares.setCurrentRow(0)

    def _share_picked(self, item, _prev=None) -> None:
        if item is not None:
            self.share.setText(item.data(Qt.UserRole))

    # ---- langkah 3 ----
    def _copy(self) -> None:
        if self.copy_btn.isEnabled():
            QGuiApplication.clipboard().setText(self.address.text())

    def _install(self) -> None:
        h, s, err = self._valid()
        if err or self.kind_key != "printer" or getattr(self, "_installing", False):
            return
        if QMessageBox.question(self, "Pasang printer", f"Tambahkan printer \\\\{h}\\{s} ke komputer ini? Driver diambil dari "
                                "server dan hanya untuk akun Windows ini.", QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        self._installing = True
        self.install_btn.setEnabled(False)
        self.install_result.setVisible(True)
        self.install_result.setText("Memasang printer, bisa sampai satu menit saat driver diunduh.")
        self.ctx.settings.set("last_server", h)
        adapter, audit = RealWindowsAdapter(allow_mutation=True), self.ctx.audit   # izin hanya setelah klik Ya
        run_async(self, lambda: client_connect.connect_printer(adapter, h, s, audit), self._installed, self._install_failed)

    def _installed(self, res: client_connect.ConnectResult) -> None:
        self._installing = False
        self._update()
        label = {"verified": "Berhasil", "unverified": "Belum terbukti", "failed": "Gagal", "refused": "Ditolak"}[res.outcome]
        extra = " Bila gagal, klik Periksa koneksi untuk melihat penyebabnya." if res.outcome in ("failed", "unverified") else ""
        self.install_result.setText(f"{label}: {res.message}{extra}")

    def _install_failed(self, msg: str) -> None:
        self._installing = False
        self._update()
        self.install_result.setText("Gagal menjalankan pemasangan. Tidak ada klaim berhasil.")

    def _check(self) -> None:
        h, s, err = self._valid()
        if err:
            return
        self.ctx.settings.set("last_server", h)
        self.check_requested.emit(h, s, self.kind_key)
