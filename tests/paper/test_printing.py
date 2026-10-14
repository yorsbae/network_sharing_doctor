import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False


def media_box(path) -> tuple[float, float]:
    m = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", Path(path).read_bytes())
    assert m, "MediaBox tidak ditemukan"
    return float(m.group(1)), float(m.group(2))


def mm(pt: float) -> float:
    return pt / 72 * 25.4


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class PrintToPdf(unittest.TestCase):
    """Cetak ke PDF membuktikan jalur render + ukuran halaman. BUKAN bukti perilaku printer fisik/driver."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def lay(self, w=210, h=330, o=None, m=12, scale=100):
        from nsd.paper import Margins, Orientation, PageLayout, PaperSize
        return PageLayout(PaperSize("Uji", w, h), o or Orientation.PORTRAIT, Margins(m, m, m, m), scale)

    def test_custom_f4_page_size_in_pdf(self):
        from nsd.printing import RulerTestJob, print_job
        out = Path(self.tmp.name) / "a.pdf"
        self.assertEqual(print_job(self.lay(), RulerTestJob(), pdf_path=str(out)), 1)
        w, h = media_box(out)
        self.assertAlmostEqual(mm(w), 210, delta=1.0)
        self.assertAlmostEqual(mm(h), 330, delta=1.0)

    def test_landscape_swaps_pdf_size(self):
        from nsd.paper import Orientation
        from nsd.printing import RulerTestJob, print_job
        out = Path(self.tmp.name) / "l.pdf"
        print_job(self.lay(o=Orientation.LANDSCAPE), RulerTestJob(), pdf_path=str(out))
        w, h = media_box(out)
        self.assertAlmostEqual(mm(w), 330, delta=1.0)
        self.assertAlmostEqual(mm(h), 210, delta=1.0)

    def test_small_custom_size(self):
        from nsd.printing import RulerTestJob, print_job
        out = Path(self.tmp.name) / "n.pdf"
        print_job(self.lay(100, 150, m=5), RulerTestJob(), pdf_path=str(out))
        w, h = media_box(out)
        self.assertAlmostEqual(mm(w), 100, delta=1.0)
        self.assertAlmostEqual(mm(h), 150, delta=1.0)

    def test_text_paginates_and_smaller_paper_needs_more_pages(self):
        from nsd.printing import TextJob, print_job
        text = "\n".join(f"baris {i} " + "x" * 50 for i in range(150))
        big = print_job(self.lay(210, 330), TextJob(text), pdf_path=str(Path(self.tmp.name) / "b.pdf"))
        small = print_job(self.lay(148, 210), TextJob(text), pdf_path=str(Path(self.tmp.name) / "s.pdf"))
        self.assertGreater(big, 1)
        self.assertGreater(small, big)

    def test_scale_changes_page_count(self):
        from nsd.printing import TextJob, print_job
        text = "\n".join(f"baris {i}" for i in range(200))
        full = print_job(self.lay(scale=100), TextJob(text), pdf_path=str(Path(self.tmp.name) / "f.pdf"))
        half = print_job(self.lay(scale=50), TextJob(text), pdf_path=str(Path(self.tmp.name) / "h.pdf"))
        self.assertLess(half, full)

    def test_preview_matches_page_aspect(self):
        from nsd.printing import TextJob, render_preview
        img, pages = render_preview(self.lay(210, 330), TextJob("halo"), dpi=50)
        self.assertEqual(pages, 1)
        self.assertAlmostEqual(img.width() / img.height(), 210 / 330, places=2)

    def test_preview_clamps_page_index(self):
        from nsd.printing import TextJob, render_preview
        _, pages = render_preview(self.lay(), TextJob("a\n" * 400), index=999, dpi=40)
        self.assertGreater(pages, 1)

    def test_errors(self):
        from nsd.printing import PrintError, RulerTestJob, print_job
        with self.assertRaises(PrintError):
            print_job(self.lay(), RulerTestJob())                              # tanpa tujuan
        with self.assertRaises(PrintError):
            print_job(self.lay(), RulerTestJob(), printer_name="TIDAK-ADA")    # printer tak ada
        with self.assertRaises(PrintError):
            print_job(self.lay(), RulerTestJob(), pdf_path="/tidak/ada/dir/x.pdf")

    def test_prefs_roundtrip_and_corrupt(self):
        from nsd.paper import PaperStore
        st = PaperStore(Path(self.tmp.name))
        self.assertEqual(st.load_prefs(), {})
        st.save_prefs({"paper": "F4 (Folio)", "scale": 90})
        self.assertEqual(st.load_prefs()["paper"], "F4 (Folio)")
        st.prefs_path.write_text("{rusak", encoding="utf-8")
        self.assertEqual(st.load_prefs(), {})

    def test_dialog_prints_pdf_and_remembers_choices(self):
        from unittest import mock
        from nsd.paper import PaperStore
        from nsd.printing import TextJob
        from nsd.ui.print_dialog import PrintLayoutDialog
        store = PaperStore(Path(self.tmp.name))
        store.add("F4 Kantor", 210, 330)
        out = str(Path(self.tmp.name) / "d.pdf")
        d = PrintLayoutDialog(TextJob("isi laporan\n" * 10), store)
        d.paper.setCurrentIndex(next(i for i, p in enumerate(d._papers) if p.name == "F4 Kantor"))
        d.m["left"].setValue(20)
        with mock.patch("nsd.ui.print_dialog.QFileDialog.getSaveFileName", return_value=(out, "")), \
                mock.patch("nsd.ui.print_dialog.QMessageBox.information"):
            d._print()
        self.assertEqual(d.last_printed, ("Simpan sebagai PDF", "F4 Kantor", 1))
        w, h = media_box(out)
        self.assertAlmostEqual(mm(h), 330, delta=1.0)
        prefs = store.load_prefs()
        self.assertEqual(prefs["paper"], "F4 Kantor")
        self.assertEqual(prefs["margins"]["left"], 20)
        d2 = PrintLayoutDialog(TextJob("x"), store)                # dibuka lagi: pilihan diingat
        self.assertEqual(d2._papers[d2.paper.currentIndex()].name, "F4 Kantor")
        self.assertEqual(d2.m["left"].value(), 20)

    def test_dialog_invalid_margin_disables_print(self):
        from nsd.paper import PaperStore
        from nsd.printing import TextJob
        from nsd.ui.print_dialog import PrintLayoutDialog
        d = PrintLayoutDialog(TextJob("x"), PaperStore(Path(self.tmp.name)))
        d.m["left"].setValue(150); d.m["right"].setValue(150)       # A4 lebar 210 -> tak ada area isi
        self.assertFalse(d.go.isEnabled())
        self.assertIn("Tidak valid", d.note.text())

    def test_diagnose_page_print_button_opens_dialog_with_redacted_report(self):
        """Regresi: tombol Cetak pernah gagal karena salah memanggil settings.get()."""
        from unittest import mock
        import nsd.ui.print_dialog as pd
        from nsd.application.scan_service import ScanService
        from nsd.bootstrap import bootstrap
        from nsd.models import Role, ScanRequest, TargetType
        from nsd.ui.diagnose_page import DiagnosePage
        from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses
        out = ScanService(FakeAdapter(healthy_responses()), net=FakeNet()).run(
            ScanRequest(Role.CLIENT, TargetType.BOTH, "SERVER01", "EPSON", ""))
        seen = {}

        def fake_exec(dlg):
            seen["text"] = dlg.job.text
            seen["title"] = dlg.windowTitle()
            return 0

        with mock.patch.dict(os.environ, {"NSD_DATA_DIR": self.tmp.name}), \
                mock.patch.object(pd.PrintLayoutDialog, "exec", fake_exec):
            page = DiagnosePage(bootstrap())
            self.assertFalse(page.print_btn.isEnabled())          # belum ada hasil scan
            page.outcome = out
            page.print_btn.setEnabled(True)
            page.print_btn.click()
        self.assertEqual(seen["title"], "Print Layout")
        self.assertIn("LAPORAN DIAGNOSIS", seen["text"])
        self.assertNotIn("SERVER01", seen["text"])               # disamarkan secara default


if __name__ == "__main__":
    unittest.main()
