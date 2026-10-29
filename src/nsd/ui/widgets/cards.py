"""Komponen kartu yang dipakai beberapa halaman."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from nsd.ui import icons, theme


def panel(inner_margins=(18, 16, 18, 16), spacing=10) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setProperty("role", "panel")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(*inner_margins)
    lay.setSpacing(spacing)
    return f, lay


class StatCard(QFrame):
    """Satu angka/keadaan nyata: ubin ikon bernada, judul kecil, nilai, keterangan."""

    def __init__(self, icon_name: str, title: str) -> None:
        super().__init__()
        self.setProperty("role", "panel")
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)
        self.tile = QFrame()
        self.tile.setProperty("role", "tile")
        self.tile.setFixedSize(46, 46)
        tl = QVBoxLayout(self.tile)
        tl.setContentsMargins(0, 0, 0, 0)
        self.icon = icons.IconLabel(icon_name, "unknown", 24)
        tl.addWidget(self.icon, 0, Qt.AlignCenter)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = theme.label(title, "caption", wrap=False)
        self.value = theme.label("-", "stat", wrap=False)
        self.sub = theme.label("", "caption")
        for w in (self.title, self.value, self.sub):
            col.addWidget(w)
        row.addWidget(self.tile)
        row.addLayout(col, 1)
        self.set("-", "", "unknown")

    def set(self, value: str, sub: str = "", tone: str = "unknown") -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        theme.set_tone(self.tile, tone)
        self.icon.set_icon(self.icon._name, tone if tone in ("ok", "warn", "fail") else "unknown")
        self.setAccessibleName(f"{self.title.text()}: {value}. {sub}")


def action_button(icon_name: str, title: str, hint: str) -> QPushButton:
    """Baris aksi cepat: judul + keterangan. Ikon mengikuti tema."""
    b = QPushButton(f"{title}\n{hint}")
    b.setProperty("role", "action")
    b.setIconSize(QSize(20, 20))
    b.setCursor(Qt.PointingHandCursor)

    def paint() -> None:
        b.setIcon(icons.icon(icon_name, theme.tokens().primary, 20))

    theme.notifier.changed.connect(paint)
    paint()
    return b
