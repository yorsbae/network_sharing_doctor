"""Tema, kontras, dan keadaan halaman (kosong/memuat/galat). Offscreen: BUKAN bukti tampilan di Windows."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False

SRC = Path(__file__).resolve().parents[2] / "src" / "nsd"


class ContrastTokens(unittest.TestCase):
    @unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
    def test_every_pair_meets_wcag_aa_in_both_themes(self):
        from nsd.ui.theme import CONTRAST_PAIRS, DARK, LIGHT, contrast_ratio
        for t in (LIGHT, DARK):
            for fg, bg, minimum in CONTRAST_PAIRS:
                ratio = contrast_ratio(getattr(t, fg), getattr(t, bg))
                self.assertGreaterEqual(ratio, minimum, f"{t.name}: {fg} di atas {bg} = {ratio:.2f}")

    def test_no_em_dash_in_source(self):
        hits = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if "—" in p.read_text(encoding="utf-8")]
        self.assertEqual(hits, [])


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class ThemeAndPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def ctx(self):
        from nsd.bootstrap import bootstrap
        return bootstrap(Path(self.tmp.name))

    def test_apply_theme_modes_and_invalid_value_falls_back(self):
        from nsd.ui import theme
        self.assertEqual(theme.apply_theme(self.app, "dark"), "dark")
        self.assertEqual(theme.apply_theme(self.app, "light"), "light")
        self.assertIn(theme.apply_theme(self.app, "bukan-tema"), ("light", "dark"))
        theme.apply_theme(self.app, "light")

    def test_theme_setting_has_default_and_persists(self):
        ctx = self.ctx()
        self.assertEqual(ctx.settings.get("theme"), "system")
        ctx.settings.set("theme", "dark")
        self.assertEqual(ctx.settings.get("theme"), "dark")

    def test_main_window_builds_and_every_nav_page_renders_in_both_themes(self):
        from nsd.ui import theme
        from nsd.ui.main_window import MainWindow
        win = MainWindow(self.ctx())
        self.assertEqual([win.nav.item(i).text() for i in range(win.nav.count())],
                         ["Beranda", "Diagnosa", "Kertas", "Riwayat", "Pengaturan"])
        for mode in ("light", "dark"):
            theme.apply_theme(self.app, mode)
            for i in range(win.nav.count()):
                win.nav.setCurrentRow(i)
                self.assertEqual(win.stack.currentIndex(), i)
                self.assertFalse(win.grab().isNull())
        theme.apply_theme(self.app, "light")

    def test_diagnose_starts_with_empty_state_and_honest_disabled_fix_button(self):
        from nsd.ui.diagnose_page import DiagnosePage
        page = DiagnosePage(self.ctx())
        self.assertEqual(page.results.currentIndex(), 0)
        self.assertIn("Belum ada hasil", page.empty.text())
        self.assertFalse(page.fix.isEnabled())
        self.assertIn("Fase 2", page.fix.text())
        self.assertFalse(page.export.isEnabled())

    def scan(self, host: str):
        """Jalankan scan lewat tombol (QThread asli, adapter palsu) dan tunggu sampai halaman selesai."""
        from nsd.application.scan_service import ScanService
        from nsd.ui.diagnose_page import DiagnosePage
        from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses
        ctx = self.ctx()
        ctx.scan_service = lambda: ScanService(FakeAdapter(healthy_responses()), ctx.cases, ctx.audit, net=FakeNet())
        page = DiagnosePage(ctx)
        page.host.setText(host)
        with mock.patch.object(QMessageBox, "critical") as crit:
            page.go.click()
            deadline = time.monotonic() + 20
            while page._thread is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
        self.assertIsNone(page._thread, "scan tidak selesai dalam 20 detik")
        crit.assert_not_called()
        return page

    def test_diagnose_scan_in_worker_thread_completes(self):
        """Regresi: koneksi SQLite dibuat di thread utama, scan GUI berjalan di QThread."""
        page = self.scan("SERVER01")
        self.assertIsNotNone(page.outcome)
        self.assertEqual(page.results.currentIndex(), 1)
        self.assertTrue(page.export.isEnabled())
        self.assertTrue(page.cp_id.isEnabled())
        self.assertTrue(page.go.isEnabled())
        self.assertFalse(page.bar.isVisible())

    def test_diagnose_invalid_input_is_reported_as_failed_check_not_crash(self):
        from nsd.models import Status
        page = self.scan("host; rm -rf /")
        check = next(c for c in page.outcome.checks if c.id == "target.input")
        self.assertIs(check.status, Status.FAIL)
        self.assertEqual(page.results.currentIndex(), 1)

    def test_every_result_row_carries_a_text_tag_not_only_a_color(self):
        page = self.scan("SERVER01")
        tags = set()
        for i in range(page.tree.topLevelItemCount()):
            top = page.tree.topLevelItem(i)
            tags |= {top.child(j).text(1) for j in range(top.childCount())}
        self.assertTrue(tags)
        self.assertTrue(all(t.startswith("[") and t.endswith("]") for t in tags), tags)

    def test_database_can_be_used_from_another_thread(self):
        from nsd.storage.database import open_database
        conn = open_database(Path(self.tmp.name) / "t.db")
        errors = []

        def work():
            try:
                conn.execute("SELECT 1").fetchone()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        th = threading.Thread(target=work)
        th.start()
        th.join()
        self.assertEqual(errors, [])

    def test_history_empty_state_rows_not_editable_and_clear_defaults_to_cancel(self):
        from PySide6.QtWidgets import QAbstractItemView
        from nsd.ui.history_page import HistoryPage
        ctx = self.ctx()
        page = HistoryPage(ctx)
        self.assertEqual(page.views.currentIndex(), 0)
        self.assertFalse(page.clear_btn.isEnabled())
        self.assertEqual(page.table.editTriggers(), QAbstractItemView.NoEditTriggers)

        executed = {}

        def fake_exec(box):
            executed["default"] = box.defaultButton().text()
            executed["escape"] = box.escapeButton().text()

        with mock.patch.object(QMessageBox, "exec", fake_exec), mock.patch.object(ctx.cases, "clear_history") as clr:
            page._clear()
        self.assertEqual(executed, {"default": "Batal", "escape": "Batal"})
        clr.assert_not_called()

    def test_settings_theme_change_is_saved_and_applied(self):
        from nsd.ui import theme
        from nsd.ui.settings_page import SettingsPage
        ctx = self.ctx()
        page = SettingsPage(ctx)
        combo = next(c for c in page.findChildren(QComboBox) if c.findData("dark") >= 0)
        combo.setCurrentIndex(combo.findData("dark"))
        self.assertEqual(ctx.settings.get("theme"), "dark")
        self.assertEqual(theme.tokens().name, "dark")
        theme.apply_theme(self.app, "light")


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class PrintPopup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make_pdf(self, pages: int = 2) -> str:
        from nsd.paper import PaperStore
        from nsd.printing import TextJob
        from nsd.printing.render import PDF_LABEL, make_ctx, print_job
        from nsd.paper import Margins, Orientation, PageLayout
        store = PaperStore(Path(self.tmp.name))
        a4 = next(p for p in store.all() if p.name == "A4")
        lay = PageLayout(a4, Orientation.PORTRAIT, Margins(10, 10, 10, 10), 100.0)
        out = str(Path(self.tmp.name) / "in.pdf")
        print_job(lay, TextJob("baris\n" * (60 * pages)), None, out, 1)
        return out

    def test_pdf_job_pages_and_preview(self):
        from nsd.paper import Margins, Orientation, PageLayout, PaperStore
        from nsd.printing import PdfJob, render_preview
        pdf = self.make_pdf(2)
        a4 = next(p for p in PaperStore(Path(self.tmp.name)).all() if p.name == "A4")
        lay = PageLayout(a4, Orientation.PORTRAIT, Margins(10, 10, 10, 10), 100.0)
        img, pages = render_preview(lay, PdfJob(pdf), 0, dpi=50)
        self.assertGreaterEqual(pages, 2)
        self.assertFalse(img.isNull())

    def test_text_job_prints_black_ink_even_in_dark_theme(self):
        from nsd.paper import Margins, Orientation, PageLayout, PaperStore
        from nsd.printing import TextJob, render_preview
        from nsd.ui import theme
        a4 = next(p for p in PaperStore(Path(self.tmp.name)).all() if p.name == "A4")
        lay = PageLayout(a4, Orientation.PORTRAIT, Margins(10, 10, 10, 10), 100.0)
        theme.apply_theme(self.app, "dark")
        try:
            img, _ = render_preview(lay, TextJob("MMMMMMMMMM\n" * 30), 0, dpi=80)
        finally:
            theme.apply_theme(self.app, "light")
        darkest = min(img.pixelColor(x, y).lightness() for x in range(0, img.width(), 2) for y in range(0, 400, 2))
        self.assertLess(darkest, 60)

    def test_pdf_job_rejects_non_pdf(self):
        from nsd.printing import PdfJob
        bad = Path(self.tmp.name) / "x.pdf"
        bad.write_text("bukan pdf")
        with self.assertRaises(ValueError):
            PdfJob(str(bad))

    def test_popup_prints_pdf_job_to_a_new_pdf_with_chosen_paper(self):
        from nsd.printing import PdfJob
        from nsd.paper import PaperStore
        from nsd.ui.print_dialog import PrintLayoutDialog
        pdf = self.make_pdf(1)
        store = PaperStore(Path(self.tmp.name))
        out = str(Path(self.tmp.name) / "out.pdf")
        d = PrintLayoutDialog(PdfJob(pdf), store)
        d.paper.setCurrentIndex(next(i for i, p in enumerate(d._papers) if p.name == "A5"))
        with mock.patch("nsd.ui.print_dialog.QFileDialog.getSaveFileName", return_value=(out, "")), \
                mock.patch("nsd.ui.print_dialog.QMessageBox.information"):
            d._print()
        self.assertEqual(d.last_printed[1], "A5")
        self.assertTrue(Path(out).stat().st_size > 0)

    def test_diagnose_print_button_opens_popup_with_redacted_report(self):
        import nsd.ui.print_dialog as pd
        from nsd.application.scan_service import ScanService
        from nsd.bootstrap import bootstrap
        from nsd.models import Role, ScanRequest, TargetType
        from nsd.ui.diagnose_page import DiagnosePage
        from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses
        out = ScanService(FakeAdapter(healthy_responses()), net=FakeNet()).run(
            ScanRequest(Role.CLIENT, TargetType.BOTH, "SERVER01", "EPSON", ""))
        seen = {}
        with mock.patch.object(pd.PrintLayoutDialog, "exec", lambda dlg: seen.update(text=dlg.job.text, title=dlg.windowTitle()) or 0):
            page = DiagnosePage(bootstrap(Path(self.tmp.name)))
            self.assertFalse(page.print_btn.isEnabled())
            page.outcome = out
            page.print_btn.setEnabled(True)
            page.print_btn.click()
        self.assertEqual(seen["title"], "Print Layout")
        self.assertNotIn("SERVER01", seen["text"])

    def test_ctrl_p_without_report_offers_pdf_picker(self):
        from nsd.ui.main_window import MainWindow
        from nsd.bootstrap import bootstrap
        win = MainWindow(bootstrap(Path(self.tmp.name)))
        with mock.patch("nsd.ui.main_window.QFileDialog.getOpenFileName", return_value=("", "")) as pick:
            win.print_current()
        pick.assert_called_once()


class Units(unittest.TestCase):
    def test_conversions(self):
        from nsd.paper.units import from_mm, to_mm
        self.assertEqual(to_mm(21, "cm"), 210)
        self.assertEqual(to_mm(8.5, "inch"), 215.9)
        self.assertAlmostEqual(from_mm(254, "inch"), 10)
        self.assertEqual(to_mm(210, "mm"), 210)


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class CustomPaperOnClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_size_fields_keep_the_physical_size_when_unit_changes(self):
        from nsd.ui.paper_fields import SizeFields
        f = SizeFields(210, 330)
        f.unit.setCurrentIndex(f.unit.findData("cm"))
        self.assertEqual(f.mm(), (210, 330))
        self.assertAlmostEqual(f.w.value(), 21.0)
        f.unit.setCurrentIndex(f.unit.findData("inch"))
        self.assertEqual(f.mm(), (210, 330))
        f.w.setValue(8.5); f.h.setValue(13)
        self.assertEqual(f.mm(), (215.9, 330.2))

    def test_paper_page_adds_custom_size_typed_in_inches_and_persists_in_mm(self):
        from nsd.paper import PaperStore
        from nsd.ui.paper_page import PaperPage
        store = PaperStore(Path(self.tmp.name))
        pg = PaperPage(store=store)
        pg.name.setText("Legal Kantor")
        pg.size.unit.setCurrentIndex(pg.size.unit.findData("inch"))
        pg.size.w.setValue(8.5); pg.size.h.setValue(14)
        pg._add()
        saved = next(p for p in PaperStore(Path(self.tmp.name)).custom() if p.name == "Legal Kantor")
        self.assertEqual((saved.width_mm, saved.height_mm), (215.9, 355.6))
        self.assertIn("Legal Kantor", " ".join(pg.papers.item(i).text() for i in range(pg.papers.count())))

    def test_popup_add_dialog_saves_custom_size_in_cm(self):
        from nsd.paper import PaperStore
        from nsd.ui.print_dialog import AddPaperDialog
        store = PaperStore(Path(self.tmp.name))
        d = AddPaperDialog(store)
        d.name.setText("Nota 21x33")
        d.size.unit.setCurrentIndex(d.size.unit.findData("cm"))
        d.size.w.setValue(21); d.size.h.setValue(33)
        d._save()
        self.assertEqual((d.added.width_mm, d.added.height_mm), (210, 330))

    def test_invalid_name_is_rejected_with_a_message_not_saved(self):
        from nsd.paper import PaperStore
        from nsd.ui.paper_page import PaperPage
        store = PaperStore(Path(self.tmp.name))
        pg = PaperPage(store=store)
        pg.name.setText("<script>")
        with mock.patch.object(QMessageBox, "warning") as warn:
            pg._add()
        warn.assert_called_once()
        self.assertEqual(store.custom(), [])


if __name__ == "__main__":
    unittest.main()
