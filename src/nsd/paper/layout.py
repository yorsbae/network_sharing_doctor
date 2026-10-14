from __future__ import annotations

from dataclasses import dataclass, field

from nsd.paper.models import Orientation, PaperError, PaperSize


@dataclass(frozen=True)
class Margins:
    top: float = 10.0
    right: float = 10.0
    bottom: float = 10.0
    left: float = 10.0

    def __post_init__(self) -> None:
        for n in ("top", "right", "bottom", "left"):
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v < 0:
                raise PaperError(f"Margin {n} harus angka >= 0.")


@dataclass(frozen=True)
class PageLayout:
    """Tata letak halaman gaya 'Print Layout': kertas, orientasi, margin, skala, area cetak."""
    paper: PaperSize
    orientation: Orientation = Orientation.PORTRAIT
    margins: Margins = field(default_factory=Margins)
    scale_percent: float = 100.0
    # Area yang TIDAK bisa dicetak printer (dilaporkan driver). 0 = belum diketahui.
    hard_margin_mm: float = 0.0

    def __post_init__(self) -> None:
        if not (10 <= self.scale_percent <= 400):
            raise PaperError("Skala harus antara 10% dan 400%.")
        if self.hard_margin_mm < 0:
            raise PaperError("Margin fisik printer tidak boleh negatif.")
        if self.content_width_mm <= 0 or self.content_height_mm <= 0:
            raise PaperError("Margin terlalu besar: tidak ada area isi tersisa.")

    @property
    def page_mm(self) -> tuple[float, float]:
        return self.paper.oriented(self.orientation)

    @property
    def content_width_mm(self) -> float:
        w, _ = self.page_mm
        return w - self.margins.left - self.margins.right

    @property
    def content_height_mm(self) -> float:
        _, h = self.page_mm
        return h - self.margins.top - self.margins.bottom

    def warnings(self) -> list[str]:
        out: list[str] = []
        m = self.margins
        hm = self.hard_margin_mm
        if hm and min(m.top, m.right, m.bottom, m.left) < hm:
            out.append(f"Margin lebih kecil dari area tak-tercetak printer (~{hm:g} mm); tepi isi dapat terpotong.")
        return out

    def to_dict(self) -> dict:
        m = self.margins
        return {"paper": self.paper.to_dict(), "orientation": self.orientation.value,
                "margins_mm": {"top": m.top, "right": m.right, "bottom": m.bottom, "left": m.left},
                "scale_percent": self.scale_percent, "hard_margin_mm": self.hard_margin_mm}
