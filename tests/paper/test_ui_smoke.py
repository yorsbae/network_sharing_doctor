import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class PaperPageSmoke(unittest.TestCase):
    """Hanya memastikan halaman dapat dibuat & dirender offscreen. BUKAN bukti tampilan di Windows."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_add_remove_and_preview(self):
        from nsd.paper import PaperStore
        from nsd.ui.paper_page import PaperPage
        with tempfile.TemporaryDirectory() as d:
            pg = PaperPage(store=PaperStore(Path(d)))
            base = pg.papers.count()
            pg.name.setText("F4 Kantor"); pg.w.setValue(210); pg.h.setValue(330); pg._add()
            self.assertEqual(pg.papers.count(), base + 1)
            self.assertIsNotNone(pg.preview.layout_)
            pg.margin.setValue(12)
            self.assertIn("186", pg.info.text())
            self.assertFalse(pg.grab().isNull())
            pg._remove()
            self.assertEqual(pg.papers.count(), base)

    def test_margin_too_large_shows_error_not_crash(self):
        from nsd.paper import PaperStore
        from nsd.ui.paper_page import PaperPage
        with tempfile.TemporaryDirectory() as d:
            pg = PaperPage(store=PaperStore(Path(d)))
            pg.margin.setValue(150)   # A4 lebar 210 -> tidak ada area isi
            self.assertIn("Tidak valid", pg.info.text())
            self.assertIsNone(pg.preview.layout_)


if __name__ == "__main__":
    unittest.main()
