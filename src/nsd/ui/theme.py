"""Tema aplikasi: token warna terang/gelap, palet Qt, dan satu stylesheet.

Semua warna UI berasal dari sini. Arah desain dan alasan tiap pilihan ada di DESIGN.md.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from nsd.models import Status

THEME_CHOICES = (("system", "Ikuti sistem"), ("light", "Terang"), ("dark", "Gelap"))
_MODES = {k for k, _ in THEME_CHOICES}


@dataclass(frozen=True)
class Tokens:
    name: str
    bg: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    sel_bg: str
    primary: str
    primary_hover: str
    primary_pressed: str
    on_primary: str
    danger: str
    danger_hover: str
    on_danger: str
    focus: str
    fail: str
    warn: str
    ok: str
    unknown: str
    side: str
    side_text: str
    side_muted: str
    side_hover: str
    side_sel: str
    canvas: str
    disabled_text: str
    disabled_bg: str
    disabled_border: str


LIGHT = Tokens(
    name="light", bg="#F4F2EC", surface="#FFFFFF", surface_alt="#ECE9DF", text="#1C2321", muted="#4A5450",
    border="#85806F", sel_bg="#CFE5E1", primary="#0F5A55", primary_hover="#0B4A46", primary_pressed="#083B38",
    on_primary="#FFFFFF", danger="#A32A1F", danger_hover="#8A2219", on_danger="#FFFFFF", focus="#0F5A55",
    fail="#A32A1F", warn="#7A4A00", ok="#1B6B3A", unknown="#4A5450",
    side="#10302D", side_text="#E6F0EE", side_muted="#A9C4BF", side_hover="#174440", side_sel="#1F6A64",
    canvas="#D9D5C8", disabled_text="#6C746F", disabled_bg="#E4E1D7", disabled_border="#B9B5A6",
)

DARK = Tokens(
    name="dark", bg="#141A19", surface="#1D2524", surface_alt="#27312F", text="#E8EDEB", muted="#AEB9B5",
    border="#74847F", sel_bg="#27423F", primary="#46B0A6", primary_hover="#66C4BB", primary_pressed="#34968D",
    on_primary="#07201D", danger="#FF8F84", danger_hover="#FFB0A8", on_danger="#2B0A06", focus="#46B0A6",
    fail="#FF8F84", warn="#F0B45A", ok="#7FD19A", unknown="#AEB9B5",
    side="#0B1E1C", side_text="#E6F0EE", side_muted="#9DB9B4", side_hover="#123432", side_sel="#1F6A64",
    canvas="#2E3836", disabled_text="#7F8C88", disabled_bg="#1A2120", disabled_border="#3C4845",
)

# (teks, latar, minimum). Teks biasa 4.5:1, batas komponen dan fokus 3:1 (R-25).
CONTRAST_PAIRS = (
    ("text", "bg", 4.5), ("text", "surface", 4.5), ("text", "surface_alt", 4.5), ("text", "sel_bg", 4.5),
    ("muted", "bg", 4.5), ("muted", "surface", 4.5), ("muted", "surface_alt", 4.5),
    ("on_primary", "primary", 4.5), ("on_primary", "primary_hover", 4.5), ("on_primary", "primary_pressed", 4.5),
    ("on_danger", "danger", 4.5), ("on_danger", "danger_hover", 4.5),
    ("fail", "surface", 4.5), ("fail", "bg", 4.5), ("fail", "sel_bg", 4.5),
    ("warn", "surface", 4.5), ("warn", "bg", 4.5), ("warn", "sel_bg", 4.5),
    ("ok", "surface", 4.5), ("ok", "bg", 4.5), ("ok", "sel_bg", 4.5),
    ("unknown", "surface", 4.5), ("unknown", "bg", 4.5), ("unknown", "sel_bg", 4.5),
    ("side_text", "side", 4.5), ("side_muted", "side", 4.5), ("side_text", "side_sel", 4.5),
    ("side_text", "side_hover", 4.5),
    ("border", "bg", 3.0), ("border", "surface", 3.0), ("focus", "bg", 3.0), ("focus", "surface", 3.0),
    ("primary", "bg", 3.0), ("primary", "surface", 3.0),
)

_state = {"tokens": LIGHT, "mode": "system", "applying": False}


def tokens() -> Tokens:
    return _state["tokens"]


def _channel(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def contrast_ratio(fg: str, bg: str) -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)

    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def status_color(status: Status) -> str:
    t = tokens()
    return {Status.FAIL: t.fail, Status.WARNING: t.warn, Status.PASS: t.ok, Status.UNKNOWN: t.unknown}[status]


def build_palette(t: Tokens) -> QPalette:
    p = QPalette()
    for role, value in (
        (QPalette.Window, t.bg), (QPalette.WindowText, t.text), (QPalette.Base, t.surface),
        (QPalette.AlternateBase, t.surface_alt), (QPalette.Text, t.text), (QPalette.Button, t.surface),
        (QPalette.ButtonText, t.text), (QPalette.Highlight, t.sel_bg), (QPalette.HighlightedText, t.text),
        (QPalette.PlaceholderText, t.muted), (QPalette.ToolTipBase, t.surface), (QPalette.ToolTipText, t.text),
        (QPalette.Link, t.primary), (QPalette.BrightText, t.text), (QPalette.Light, t.surface_alt),
        (QPalette.Midlight, t.surface_alt), (QPalette.Mid, t.border), (QPalette.Dark, t.border),
        (QPalette.Shadow, "#000000"),
    ):
        p.setColor(role, QColor(value))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(t.disabled_text))
    return p


def _indicator_images(t: Tokens) -> tuple[str, str]:
    """Gambar kotak centang (mati/hidup) per tema. Outline bawaan Fusion nyaris tak terlihat pada tema gelap."""
    folder = Path(tempfile.gettempdir()) / "nsd-ui" / t.name
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for checked in (False, True):
        img = QImage(18, 18, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        edge = QColor(t.primary if checked else t.border)
        p.setPen(QPen(edge, 1.5))
        p.setBrush(QColor(t.primary if checked else t.surface))
        p.drawRoundedRect(QRectF(1, 1, 16, 16), 4, 4)
        if checked:
            p.setPen(QPen(QColor(t.on_primary), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline([QPointF(4.8, 9.4), QPointF(7.8, 12.4), QPointF(13.2, 5.8)])
        p.end()
        path = folder / ("check_on.png" if checked else "check_off.png")
        img.save(str(path))
        paths.append(path.as_posix())
    return paths[0], paths[1]


def build_qss(t: Tokens) -> str:
    off, on = _indicator_images(t)
    return f"""
QMainWindow, QDialog {{ background: {t.bg}; }}
QStackedWidget {{ background: {t.bg}; }}
QLabel {{ color: {t.text}; background: transparent; }}
QLabel[role="title"] {{ font-size: 22px; font-weight: 600; }}
QLabel[role="subtitle"] {{ color: {t.muted}; font-size: 14px; }}
QLabel[role="section"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="caption"] {{ color: {t.muted}; font-size: 12px; }}
QLabel[role="empty"] {{ color: {t.muted}; font-size: 14px; padding: 24px; }}
QLabel[role="canvas"] {{ background: {t.canvas}; }}
QToolTip {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; padding: 4px 6px; }}

QFrame#sidebar {{ background: {t.side}; }}
QLabel#brand {{ color: {t.side_text}; font-size: 16px; font-weight: 600; }}
QLabel#brandVersion {{ color: {t.side_muted}; font-size: 12px; }}
QListWidget#nav {{ background: transparent; border: 2px solid transparent; border-radius: 8px; outline: 0;
    color: {t.side_text}; font-size: 14px; }}
QListWidget#nav::item {{ padding: 10px 14px; margin: 2px 0; border-radius: 6px; color: {t.side_text}; }}
QListWidget#nav::item:hover {{ background: {t.side_hover}; }}
QListWidget#nav::item:selected {{ background: {t.side_sel}; color: {t.side_text}; border: 0; }}
QListWidget#nav:focus {{ border: 2px solid {t.side_muted}; }}

QFrame[role="panel"] {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; }}
QFrame[role="callout"] {{ background: {t.surface_alt}; border: 1px solid {t.border}; border-radius: 10px; }}
QFrame[role="panel"] QLabel, QFrame[role="callout"] QLabel {{ border: 0; }}

QPushButton {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; border-radius: 6px;
    padding: 7px 16px; min-height: 20px; }}
QPushButton:hover {{ background: {t.surface_alt}; }}
QPushButton:pressed {{ background: {t.sel_bg}; }}
QPushButton:focus {{ border: 2px solid {t.focus}; padding: 6px 15px; }}
QPushButton:disabled {{ color: {t.disabled_text}; background: {t.disabled_bg}; border-color: {t.disabled_border}; }}
QPushButton[role="primary"] {{ background: {t.primary}; color: {t.on_primary}; border: 1px solid {t.primary};
    font-weight: 600; padding: 9px 22px; }}
QPushButton[role="primary"]:hover {{ background: {t.primary_hover}; border-color: {t.primary_hover}; }}
QPushButton[role="primary"]:pressed {{ background: {t.primary_pressed}; border-color: {t.primary_pressed}; }}
QPushButton[role="primary"]:focus {{ border: 2px solid {t.text}; padding: 8px 21px; }}
QPushButton[role="primary"]:disabled {{ color: {t.disabled_text}; background: {t.disabled_bg};
    border-color: {t.disabled_border}; }}
QPushButton[role="danger"] {{ background: {t.surface}; color: {t.fail}; border: 1px solid {t.fail}; }}
QPushButton[role="danger"]:hover {{ background: {t.danger}; color: {t.on_danger}; border-color: {t.danger}; }}
QPushButton[role="danger"]:focus {{ border: 2px solid {t.fail}; }}
QPushButton[role="danger"]:disabled {{ color: {t.disabled_text}; background: {t.disabled_bg};
    border-color: {t.disabled_border}; }}

QLineEdit, QPlainTextEdit, QTextBrowser {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
    border-radius: 6px; padding: 6px 8px; selection-background-color: {t.sel_bg}; selection-color: {t.text}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus {{ border: 2px solid {t.focus}; padding: 5px 7px; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ padding: 4px 6px; min-height: 22px; }}

QTreeWidget, QTableWidget, QListWidget {{ background: {t.surface}; alternate-background-color: {t.surface_alt};
    color: {t.text}; border: 1px solid {t.border}; border-radius: 6px; gridline-color: {t.surface_alt}; }}
QTreeWidget:focus, QTableWidget:focus, QListWidget:focus {{ border: 2px solid {t.focus}; }}
QTreeWidget::item, QTableWidget::item {{ padding: 4px 2px; }}
QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
    background: {t.sel_bg}; color: {t.text}; border-top: 1px solid {t.focus}; border-bottom: 1px solid {t.focus}; }}
QHeaderView::section {{ background: {t.surface_alt}; color: {t.text}; padding: 6px 8px; border: 0;
    border-bottom: 1px solid {t.border}; font-weight: 600; }}
QSplitter::handle {{ background: transparent; }}

QCheckBox {{ border: 2px solid transparent; border-radius: 4px; padding: 2px; spacing: 8px; }}
QCheckBox:focus {{ border: 2px solid {t.focus}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; image: url("{off}"); }}
QCheckBox::indicator:checked {{ image: url("{on}"); }}

QGroupBox {{ border: 1px solid {t.border}; border-radius: 10px; margin-top: 14px; padding: 14px 10px 10px 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {t.text}; font-weight: 600; }}

QProgressBar {{ background: {t.surface_alt}; border: 1px solid {t.border}; border-radius: 5px; max-height: 10px; }}
QProgressBar::chunk {{ background: {t.primary}; border-radius: 4px; }}
"""


def _apply_font(app: QApplication) -> None:
    f = QFont()
    f.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Noto Sans", "Sans Serif"])
    f.setPointSize(10)
    app.setFont(f)


def resolve_mode(mode: str) -> str:
    if mode in ("light", "dark"):
        return mode
    return "dark" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"


def apply_theme(app: QApplication, mode: str = "system") -> str:
    """Terapkan tema. `mode`: system | light | dark (nilai lain dianggap system). Mengembalikan 'light' atau 'dark'."""
    mode = mode if mode in _MODES else "system"
    _state["mode"] = mode
    if _state["applying"]:
        return _state["tokens"].name
    _state["applying"] = True
    try:
        hints = app.styleHints()
        if hasattr(hints, "setColorScheme"):
            hints.setColorScheme({"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(mode, Qt.ColorScheme.Unknown))
        t = DARK if resolve_mode(mode) == "dark" else LIGHT
        _state["tokens"] = t
        app.setStyle("Fusion")
        _apply_font(app)
        app.setPalette(build_palette(t))
        app.setStyleSheet(build_qss(t))
    finally:
        _state["applying"] = False
    return t.name


def follow_system_changes(app: QApplication) -> None:
    """Saat mode 'Ikuti sistem', pasang ulang tema begitu skema warna sistem berubah."""
    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda *_: _state["mode"] == "system" and apply_theme(app, "system"))


def set_role(widget: QWidget, role: str) -> QWidget:
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    return widget


def label(text: str, role: str | None = None, wrap: bool = True, selectable: bool = False) -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(wrap)
    if role:
        lb.setProperty("role", role)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    return lb


def header(title: str, subtitle: str | None = None) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(label(title, "title"))
    if subtitle:
        lay.addWidget(label(subtitle, "subtitle"))
    return box


def callout(title: str, body: str) -> QFrame:
    """Kotak catatan. Judul berupa kata ('Peringatan', dst.), bukan warna, yang membedakan jenisnya."""
    frame = QFrame()
    frame.setProperty("role", "callout")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(4)
    lay.addWidget(label(title, "section"))
    lay.addWidget(label(body))
    return frame


