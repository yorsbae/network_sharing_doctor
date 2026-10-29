"""Satuan input ukuran kertas. Penyimpanan selalu dalam milimeter."""
from __future__ import annotations

UNITS: tuple[tuple[str, str, float], ...] = (("mm", "mm", 1.0), ("cm", "cm", 10.0), ("inch", "inci", 25.4))
_FACTOR = {key: f for key, _label, f in UNITS}


def to_mm(value: float, unit: str) -> float:
    return round(value * _FACTOR[unit], 2)


def from_mm(value_mm: float, unit: str) -> float:
    return value_mm / _FACTOR[unit]
