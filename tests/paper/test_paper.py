import json
import tempfile
import unittest
from pathlib import Path

from nsd.paper import (DriverCaps, Margins, Orientation, PageLayout, PaperError, PaperSize, PaperStore,
                       Strategy, assess, find_preset)
from nsd.paper.capability import Availability, Connection, best


class ModelTests(unittest.TestCase):
    def test_f4_devmode_units(self):
        self.assertEqual(find_preset("f4 (folio)").devmode_units, (2100, 3300))

    def test_normalised_to_portrait(self):
        p = PaperSize("Lebar", 330, 210)
        self.assertEqual((p.width_mm, p.height_mm), (210, 330))

    def test_landscape_swaps(self):
        self.assertEqual(find_preset("A4").oriented(Orientation.LANDSCAPE), (297, 210))

    def test_rejects_bad_values(self):
        for args in [("", 100, 100), ("X", 5, 100), ("X", 100, 5000), ("X", float("nan"), 100),
                     ("X", True, 100), ("X", "100", 100), ("../x", 100, 100), ("a;b", 100, 100)]:
            with self.assertRaises(PaperError, msg=args):
                PaperSize(*args)

    def test_inches(self):
        w, h = find_preset("Letter").inches
        self.assertAlmostEqual(w, 8.5, places=2)
        self.assertAlmostEqual(h, 11.0, places=2)


class LayoutTests(unittest.TestCase):
    def test_content_area(self):
        lay = PageLayout(find_preset("A4"), margins=Margins(10, 15, 10, 25))
        self.assertEqual((lay.content_width_mm, lay.content_height_mm), (170, 277))

    def test_landscape_content(self):
        lay = PageLayout(find_preset("A4"), Orientation.LANDSCAPE, Margins(10, 10, 10, 10))
        self.assertEqual((lay.content_width_mm, lay.content_height_mm), (277, 190))

    def test_margin_too_large(self):
        with self.assertRaises(PaperError):
            PageLayout(find_preset("A5"), margins=Margins(10, 80, 10, 80))

    def test_bad_scale_and_margin(self):
        with self.assertRaises(PaperError):
            PageLayout(find_preset("A4"), scale_percent=5)
        with self.assertRaises(PaperError):
            Margins(-1, 0, 0, 0)

    def test_hard_margin_warning(self):
        lay = PageLayout(find_preset("A4"), margins=Margins(2, 10, 10, 10), hard_margin_mm=4.2)
        self.assertEqual(len(lay.warnings()), 1)
        self.assertEqual(PageLayout(find_preset("A4")).warnings(), [])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PaperStore(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_list_remove_persist(self):
        self.store.add("Nota Kecil", 100, 150)
        self.assertEqual([p.name for p in PaperStore(Path(self.tmp.name)).custom()], ["Nota Kecil"])
        self.assertIn("Nota Kecil", [p.name for p in self.store.all()])
        self.assertTrue(self.store.remove("nota kecil"))
        self.assertFalse(self.store.remove("nota kecil"))

    def test_duplicate_and_builtin_rejected(self):
        self.store.add("X1", 100, 150)
        with self.assertRaises(PaperError):
            self.store.add("x1", 100, 150)
        with self.assertRaises(PaperError):
            self.store.add("A4", 100, 150)

    def test_corrupt_file_ignored_and_not_overwritten(self):
        self.store.path.write_text("{bukan json", encoding="utf-8")
        self.assertEqual(self.store.custom(), [])
        self.assertTrue(self.store.load_errors)
        with self.assertRaises(PaperError):
            self.store.add("Baru", 100, 150)
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), "{bukan json")

    def test_bad_entry_skipped_good_kept(self):
        self.store.path.write_text(json.dumps({"custom": [
            {"name": "Ok", "width_mm": 100, "height_mm": 200},
            {"name": "Buruk", "width_mm": -5, "height_mm": 200}, "bukan-objek"]}), encoding="utf-8")
        self.assertEqual([p.name for p in self.store.custom()], ["Ok"])
        self.assertEqual(len(self.store.load_errors), 2)


class CapabilityTests(unittest.TestCase):
    F4 = PaperSize("F4", 210, 330)

    def by(self, opts, s):
        return next(o for o in opts if o.strategy is s)

    def test_per_job_available_when_driver_reports_support(self):
        caps = DriverCaps(Connection.SHARED, (76, 127), (216, 356), True)
        o = self.by(assess(self.F4, caps), Strategy.PER_JOB)
        self.assertEqual(o.availability, Availability.AVAILABLE)
        self.assertFalse(o.depends_on_server or o.needs_client_admin)
        self.assertEqual(best(assess(self.F4, caps)).strategy, Strategy.PER_JOB)

    def test_unknown_caps_never_claimed_available(self):
        opts = assess(self.F4, DriverCaps())
        self.assertEqual(self.by(opts, Strategy.PER_JOB).availability, Availability.UNKNOWN)
        self.assertIsNone(best(opts))
        self.assertTrue(all(not o.verified_on_windows for o in opts))

    def test_too_large_not_supported_everywhere(self):
        caps = DriverCaps(Connection.LOCAL_USB, (76, 127), (210, 297), True, client_is_admin=True)
        opts = assess(self.F4, caps)
        for s in (Strategy.PER_JOB, Strategy.CLIENT_LOCAL_FORM, Strategy.LOCAL_QUEUE):
            self.assertEqual(self.by(opts, s).availability, Availability.NOT_SUPPORTED)
        self.assertIsNone(best(opts))

    def test_too_small(self):
        caps = DriverCaps(min_extent_mm=(76, 127), max_extent_mm=(216, 356), supports_user_size=True)
        o = self.by(assess(PaperSize("Kecil", 20, 30), caps), Strategy.PER_JOB)
        self.assertEqual(o.availability, Availability.NOT_SUPPORTED)

    def test_driver_without_user_size_falls_back_to_local_queue_needing_admin(self):
        caps = DriverCaps(Connection.SHARED, (76, 127), (216, 356), False)
        opts = assess(self.F4, caps)
        self.assertEqual(self.by(opts, Strategy.PER_JOB).availability, Availability.NOT_SUPPORTED)
        self.assertEqual(self.by(opts, Strategy.LOCAL_QUEUE).availability, Availability.NEEDS_ADMIN)

    def test_shared_client_form_is_unknown_not_claimed(self):
        caps = DriverCaps(Connection.SHARED, (76, 127), (216, 356), True, client_is_admin=True)
        self.assertEqual(self.by(assess(self.F4, caps), Strategy.CLIENT_LOCAL_FORM).availability,
                         Availability.UNKNOWN)

    def test_server_form_never_best(self):
        opts = assess(self.F4, DriverCaps(Connection.SHARED, (76, 127), (216, 356), True, True))
        self.assertTrue(self.by(opts, Strategy.SERVER_FORM).depends_on_server)
        self.assertNotEqual(best(opts).strategy, Strategy.SERVER_FORM)


if __name__ == "__main__":
    unittest.main()
