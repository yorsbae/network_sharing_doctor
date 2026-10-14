"""Ukuran kertas khusus & tata letak cetak di sisi client (vision A.4.4, A.4.5).

Prinsip: daftar ukuran kertas milik pengguna disimpan LOKAL di client, tidak bergantung pada server.
Modul ini murni logika (tanpa Windows/UI) sehingga dapat diuji di mana saja.
"""
from nsd.paper.models import Orientation, PaperError, PaperSize, PRESETS, find_preset
from nsd.paper.layout import Margins, PageLayout
from nsd.paper.capability import DriverCaps, Strategy, StrategyOption, assess
from nsd.paper.store import PaperStore

__all__ = ["Orientation", "PaperError", "PaperSize", "PRESETS", "find_preset", "Margins", "PageLayout",
           "DriverCaps", "Strategy", "StrategyOption", "assess", "PaperStore"]
