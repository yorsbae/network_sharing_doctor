from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

MIN_MM = 10.0       # batas wajar aplikasi; batas sebenarnya ditentukan driver (lihat capability.py)
MAX_MM = 2000.0
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-×x()]{0,62}$")


class PaperError(ValueError):
    """Input ukuran kertas tidak valid."""


class Orientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


@dataclass(frozen=True)
class PaperSize:
    """Ukuran kertas dalam milimeter, selalu disimpan sebagai potret (lebar <= tinggi)."""
    name: str
    width_mm: float
    height_mm: float
    builtin: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME_RE.match(self.name.strip()):
            raise PaperError("Nama ukuran tidak valid (huruf, angka, spasi, . _ - ( ) saja; maks. 63 karakter).")
        for label, v in (("Lebar", self.width_mm), ("Tinggi", self.height_mm)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
                raise PaperError(f"{label} harus berupa angka.")
            if not (MIN_MM <= v <= MAX_MM):
                raise PaperError(f"{label} harus antara {MIN_MM:g} dan {MAX_MM:g} mm (diterima {v}).")
        if self.width_mm > self.height_mm:
            w, h = self.height_mm, self.width_mm
            object.__setattr__(self, "width_mm", w)
            object.__setattr__(self, "height_mm", h)
        object.__setattr__(self, "name", self.name.strip())

    # DEVMODE (dmPaperWidth/dmPaperLength) memakai satuan 1/10 mm
    @property
    def devmode_units(self) -> tuple[int, int]:
        return round(self.width_mm * 10), round(self.height_mm * 10)

    @property
    def inches(self) -> tuple[float, float]:
        return self.width_mm / 25.4, self.height_mm / 25.4

    def oriented(self, o: Orientation) -> tuple[float, float]:
        return (self.height_mm, self.width_mm) if o is Orientation.LANDSCAPE else (self.width_mm, self.height_mm)

    def label(self) -> str:
        return f"{self.name} ({self.width_mm:g} × {self.height_mm:g} mm)"

    def to_dict(self) -> dict:
        return {"name": self.name, "width_mm": self.width_mm, "height_mm": self.height_mm}

    @staticmethod
    def from_dict(d: dict) -> "PaperSize":
        if not isinstance(d, dict):
            raise PaperError("Entri bukan objek.")
        return PaperSize(d.get("name", ""), d.get("width_mm"), d.get("height_mm"))


PRESETS: tuple[PaperSize, ...] = (
    PaperSize("A3", 297, 420, True),
    PaperSize("A4", 210, 297, True),
    PaperSize("A5", 148, 210, True),
    PaperSize("F4 (Folio)", 210, 330, True),   # kebutuhan contoh di vision A.4.4
    PaperSize("Letter", 215.9, 279.4, True),
    PaperSize("Legal", 215.9, 355.6, True),
)


def find_preset(name: str) -> PaperSize | None:
    n = name.strip().lower()
    return next((p for p in PRESETS if p.name.lower() == n), None)
