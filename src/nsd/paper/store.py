from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from nsd.paper.models import PRESETS, PaperError, PaperSize, find_preset

MAX_CUSTOM = 100


class PaperStore:
    """Daftar ukuran kertas buatan pengguna, disimpan lokal di client (JSON) — tanpa server."""

    def __init__(self, directory: Path) -> None:
        self.path = Path(directory) / "paper_sizes.json"
        self.load_errors: list[str] = []

    def _read(self) -> list[PaperSize]:
        self.load_errors = []
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw["custom"]
            if not isinstance(items, list):
                raise TypeError("'custom' bukan daftar")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.load_errors.append(f"paper_sizes.json rusak ({exc}); diabaikan, berkas tidak ditimpa.")
            return []
        out: list[PaperSize] = []
        for i, d in enumerate(items):
            try:
                out.append(PaperSize.from_dict(d))
            except PaperError as exc:
                self.load_errors.append(f"Entri #{i} dilewati: {exc}")
        return out

    def _write(self, items: list[PaperSize]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "custom": [p.to_dict() for p in items]}, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")   # tulis atomik
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # Preferensi cetak terakhir (printer, kertas, margin, ...), lokal di client
    @property
    def prefs_path(self) -> Path:
        return self.path.parent / "print_prefs.json"

    def load_prefs(self) -> dict:
        try:
            d = json.loads(self.prefs_path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save_prefs(self, prefs: dict) -> None:
        self.prefs_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.prefs_path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.prefs_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def custom(self) -> list[PaperSize]:
        return self._read()

    def all(self) -> list[PaperSize]:
        return list(PRESETS) + self._read()

    def add(self, name: str, width_mm: float, height_mm: float) -> PaperSize:
        p = PaperSize(name, width_mm, height_mm)
        if find_preset(p.name):
            raise PaperError(f"Nama '{p.name}' dipakai ukuran bawaan.")
        items = self._read()
        if self.load_errors and self.path.exists() and not items:
            raise PaperError("Berkas ukuran kertas rusak; perbaiki/hapus dulu agar data tidak tertimpa.")
        if any(i.name.lower() == p.name.lower() for i in items):
            raise PaperError(f"Ukuran '{p.name}' sudah ada.")
        if len(items) >= MAX_CUSTOM:
            raise PaperError(f"Maksimum {MAX_CUSTOM} ukuran khusus.")
        items.append(p)
        self._write(items)
        return p

    def remove(self, name: str) -> bool:
        items = self._read()
        keep = [i for i in items if i.name.lower() != name.strip().lower()]
        if len(keep) == len(items):
            return False
        self._write(keep)
        return True
