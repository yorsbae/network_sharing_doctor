"""Alur Server dan Client di UI. Offscreen: BUKAN bukti tampilan di Windows."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except ImportError:  # pragma: no cover
    HAVE_QT = False

from tests.fixtures.fakes import FakeAdapter, FakeNet, healthy_responses, ok, svc


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class ServerClientPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._dispose_widgets)

    def _dispose_widgets(self):
        """Halaman dan jendela yang dibuat tes ikut dibuang; kalau tidak, ganti tema di tes lain jadi lambat."""
        from PySide6.QtCore import QCoreApplication, QEvent
        for w in QApplication.topLevelWidgets():
            w.close()
            w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def ctx(self, responses=None):
        from nsd.bootstrap import bootstrap
        ctx = bootstrap(Path(self.tmp.name))
        ctx.adapter = FakeAdapter(healthy_responses() if responses is None else responses)
        return ctx

    def wait(self, cond, what="kondisi", seconds=20):
        end = time.monotonic() + seconds
        while not cond() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(cond(), f"tidak tercapai: {what}")

    # ---- Server ----
    def test_server_page_shows_readiness_address_and_copies_guide_for_clients(self):
        from nsd.ui.server_page import ServerPage
        page = ServerPage(self.ctx())
        with mock.patch("nsd.application.server_setup.local_ipv4_addresses", return_value=["192.168.1.10"]):
            page.refresh()
            self.wait(lambda: page.readiness is not None, "kesiapan terbaca")
        self.assertTrue(page.readiness.ready)
        self.assertEqual(page.steps_lay.count(), 5)
        self.assertIn("Siap dipakai client", [page.verdict_row.itemAt(i).widget().text() for i in range(page.verdict_row.count())])
        self.assertTrue(page.copy_guide.isEnabled())
        page.copy_guide.click()
        clip = QGuiApplication.clipboard().text()
        self.assertIn("\\\\PC-KASIR\\EPSON", clip)
        self.assertIn("\\\\192.168.1.10\\EPSON", clip)
        self.assertIn("tersalin", page.note.text())
        self.assertTrue(page.refresh_btn.isEnabled())

    def test_server_page_is_honest_when_nothing_can_be_read_and_never_offers_a_guide(self):
        from nsd.ui.server_page import ServerPage
        page = ServerPage(self.ctx({}))
        page.refresh()
        self.wait(lambda: page.readiness is not None)
        self.assertEqual(page.readiness.verdict, ("Belum diperiksa", "unknown"))
        self.assertFalse(page.copy_guide.isEnabled())
        self.assertIn("Belum ada printer yang dibagikan", page.addr_lay.itemAt(0).widget().text())

    def test_server_page_failing_step_explains_how_to_fix_it(self):
        from nsd.ui.server_page import ServerPage
        page = ServerPage(self.ctx({**healthy_responses(),
                                    "get_service": lambda service: svc(service, "Stopped" if service == "Spooler" else "Running")}))
        page.refresh()
        self.wait(lambda: page.readiness is not None)
        texts = " ".join(w.text() for w in page.findChildren(type(page.state)))
        self.assertIn("Print Spooler berjalan", texts)
        self.assertIn("Berhenti", texts)
        self.assertIn("Bisa disiapkan otomatis", texts)
        self.assertNotIn("Yang bisa dilakukan", texts)          # tidak lagi menyuruh keluar aplikasi
        self.assertFalse(page.prepare_btn.isHidden())
        self.assertEqual(page.readiness.verdict[1], "fail")

    def test_server_page_scan_button_emits_signal(self):
        from nsd.ui.server_page import ServerPage
        page, got = ServerPage(self.ctx()), []
        page.scan_self.connect(lambda: got.append(1))
        page.scan_btn.click()
        self.assertEqual(got, [1])

    # ---- Client ----
    def test_client_page_guides_step_by_step_and_blocks_check_until_input_is_valid(self):
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        self.assertFalse(page.check_btn.isEnabled())
        self.assertIn("server", page.need.text())
        page.host.setText("PC-KASIR")
        self.assertFalse(page.check_btn.isEnabled())
        self.assertIn("share", page.need.text())
        page.share.setText("EPSON")
        self.assertTrue(page.check_btn.isEnabled())
        self.assertEqual(page.address.text(), "\\\\PC-KASIR\\EPSON")
        self.assertIn("Pasang printer ini", page.install_hint.text())      # tidak lagi menyuruh Windows + R
        page.host.setText("host; rm -rf /")
        self.assertFalse(page.check_btn.isEnabled())
        self.assertEqual(page.address.text(), "-")

    def test_client_check_emits_target_and_remembers_the_server(self):
        from nsd.ui.client_page import ClientPage
        ctx = self.ctx()
        page, got = ClientPage(ctx), []
        page.check_requested.connect(lambda h, s, t: got.append((h, s, t)))
        page.host.setText("PC-KASIR")
        page.share.setText("EPSON")
        page.check_btn.click()
        self.assertEqual(got, [("PC-KASIR", "EPSON", "printer")])
        self.assertEqual(ctx.settings.get("last_server"), "PC-KASIR")
        again = ClientPage(ctx)                          # halaman baru mengingat server terakhir
        self.assertEqual(again.host.text(), "PC-KASIR")

    def test_client_folder_kind_needs_a_typed_share_and_hides_printer_listing(self):
        from nsd.ui.client_page import ClientPage
        page, got = ClientPage(self.ctx()), []
        page.check_requested.connect(lambda h, s, t: got.append((h, s, t)))
        page.kind.setCurrentIndex(1)
        self.assertFalse(page.list_btn.isEnabled())
        self.assertIn("Ketik nama share", page.kind_hint.text())
        page.host.setText("192.168.1.9")
        page.share.setText("DATA")
        self.assertEqual(page.install_hint.text(), "")
        page.check_btn.click()
        self.assertEqual(got, [("192.168.1.9", "DATA", "folder")])

    def test_client_discovery_lists_servers_and_picking_one_fills_the_host(self):
        from nsd.application import discovery
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        res = discovery.DiscoveryResult([discovery.FoundServer("192.168.1.9", "PC-KASIR"), discovery.FoundServer("192.168.1.30")],
                                        253, ["192.168.1.0/24"])
        with mock.patch("nsd.application.discovery.discover", return_value=res), \
             mock.patch("nsd.application.server_setup.local_ipv4_addresses", return_value=["192.168.1.20"]):
            page.find.click()
            self.wait(lambda: not page._finding, "pencarian selesai")
        self.assertEqual(page.found.count(), 2)
        self.assertIn("Ditemukan 2", page.find_status.text())
        self.assertEqual(page.find.text(), "Cari server di jaringan")
        self.assertFalse(page.bar.isVisible())
        page.found.setCurrentRow(1)
        self.assertEqual(page.host.text(), "192.168.1.30")
        page.found.setCurrentRow(0)
        self.assertEqual(page.host.text(), "PC-KASIR")

    def test_client_discovery_with_nothing_found_explains_and_keeps_manual_entry(self):
        from nsd.application import discovery
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        res = discovery.DiscoveryResult([], 253, ["192.168.1.0/24"], note="Tidak ada komputer. Ketik secara manual.")
        with mock.patch("nsd.application.discovery.discover", return_value=res):
            page.find.click()
            self.wait(lambda: not page._finding)
        self.assertFalse(page.found.isVisible())
        self.assertIn("manual", page.find_status.text())
        self.assertTrue(page.host.isEnabled())

    def test_client_lists_shared_printers_and_picking_fills_the_share(self):
        from nsd.diagnostics.base import NetProbe
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        page.host.setText("PC-KASIR")
        with mock.patch.object(NetProbe, "tcp_connect", return_value=(True, "connected")):
            page.list_btn.click()
            self.wait(lambda: not page._listing, "daftar printer terbaca")
        self.assertEqual(page.shares.count(), 1)
        self.assertIn("1 printer dibagikan", page.list_status.text())
        self.assertEqual(page.share.text(), "EPSON")           # satu-satunya printer dipilih otomatis
        self.assertTrue(page.check_btn.isEnabled())

    def test_client_unreachable_server_gives_a_specific_message_not_a_timeout(self):
        from nsd.diagnostics.base import NetProbe
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        page.host.setText("PC-KASIR")
        with mock.patch.object(NetProbe, "tcp_connect", return_value=(False, "timeout")):
            page.list_btn.click()
            self.wait(lambda: not page._listing)
        self.assertIn("port SMB (445)", page.list_status.text())
        self.assertIn("manual", page.list_status.text())
        self.assertFalse(page.shares.isVisible())

    def test_client_unknown_name_says_so(self):
        from nsd.diagnostics.base import NetProbe
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        page.host.setText("PC-SALAH")
        with mock.patch.object(NetProbe, "tcp_connect", return_value=(False, "error:gaierror")):
            page.list_btn.click()
            self.wait(lambda: not page._listing)
        self.assertIn("tidak ditemukan", page.list_status.text())

    # ---- Dashboard, Scan, jendela utama ----
    def test_dashboard_prompts_for_a_role_then_remembers_it_and_opens_the_page(self):
        from nsd.ui.main_window import GOTO, MainWindow
        ctx = self.ctx()
        win = MainWindow(ctx)
        self.assertIn("Mulai di sini", win.dash.role_title.text())
        win.dash.a_server.click()
        self.assertEqual((ctx.settings.get("role"), ctx.settings.get("role_chosen")), ("server", True))
        self.assertEqual(win.nav.currentRow(), GOTO["server"])
        self.assertIn("Server", win.dash.role_title.text())
        win.nav.setCurrentRow(0)
        win.dash.a_client.click()
        self.assertEqual(ctx.settings.get("role"), "client")
        self.assertEqual(win.nav.currentRow(), GOTO["client"])
        self.assertIn("Client", win.dash.role_title.text())

    def test_client_check_opens_scan_prefilled_and_runs_it(self):
        from nsd.application.scan_service import ScanService
        from nsd.models import Role
        from nsd.ui.main_window import GOTO, MainWindow
        ctx = self.ctx()
        ctx.scan_service = lambda: ScanService(ctx.adapter, ctx.cases, ctx.audit, net=FakeNet())
        win = MainWindow(ctx)
        win.nav.setCurrentRow(GOTO["client"])
        win.client.host.setText("SERVER01")
        win.client.share.setText("EPSON")
        win.client.check_btn.click()
        self.wait(lambda: win.diagnose._thread is None and win.diagnose.outcome is not None, "scan selesai")
        self.assertEqual(win.nav.currentRow(), GOTO["scan"])
        req = win.diagnose.outcome.request
        self.assertEqual((req.role, req.target_type.value, req.host, req.share), (Role.CLIENT, "printer", "SERVER01", "EPSON"))
        self.assertEqual(win.diagnose.mode, "client")

    def test_scan_page_has_no_role_picker_and_follows_the_mode(self):
        from nsd.ui.main_window import GOTO, MainWindow
        win = MainWindow(self.ctx())
        d = win.diagnose
        self.assertFalse(hasattr(d, "role"))
        d.set_mode("client")
        self.assertFalse(d.host_box.isHidden())
        d.find_btn.click()
        self.assertEqual(win.nav.currentRow(), GOTO["client"])
        d.set_mode("server")                            # server: komputer ini, kolom server disembunyikan
        self.assertEqual(d.host.text(), "localhost")
        self.assertTrue(d.host_box.isHidden())
        self.assertIn("komputer ini", d.mode_note.text())
        d.set_mode("client")                            # kembali ke client: localhost bukan target yang masuk akal
        self.assertEqual(d.host.text(), "")
        d.host.setText("SERVER01")
        d.set_mode("client")
        self.assertEqual(d.host.text(), "SERVER01")     # isian pengguna tidak ditimpa

    def test_server_page_scan_button_scans_this_computer_as_server(self):
        from nsd.application.scan_service import ScanService
        from nsd.models import Role
        from nsd.ui.main_window import GOTO, MainWindow
        ctx = self.ctx()
        ctx.scan_service = lambda: ScanService(ctx.adapter, ctx.cases, ctx.audit, net=FakeNet())
        win = MainWindow(ctx)
        win.server.scan_btn.click()
        self.wait(lambda: win.diagnose._thread is None and win.diagnose.outcome is not None)
        self.assertEqual(win.nav.currentRow(), GOTO["scan"])
        self.assertIs(win.diagnose.outcome.request.role, Role.SERVER)

    def _visible(self, win):
        return [win.nav.item(i).text() for i in range(win.nav.count()) if not win.nav.item(i).isHidden()]

    def test_menu_follows_the_mode_and_hides_the_other_role(self):
        from nsd.ui.main_window import GOTO, MainWindow
        ctx = self.ctx()
        win = MainWindow(ctx)
        self.assertEqual(self._visible(win), ["Dashboard", "Pengaturan"])          # belum memilih mode
        self.assertFalse(win.mode_btn.isVisibleTo(win))
        win.dash.a_server.click()
        vis = self._visible(win)
        self.assertIn("Server", vis)
        self.assertNotIn("Client", vis)
        self.assertIn("Scan printer", vis)
        self.assertTrue(win.diagnose.host_box.isHidden())
        self.assertNotIn("Dashboard", vis)
        self.assertEqual(win.nav.currentRow(), GOTO["server"])
        self.assertEqual(win.mode_label.text(), "Mode: Server")
        win._change_mode()                                                          # ganti mode lewat satu tombol
        self.assertEqual(win.nav.currentRow(), 0)
        win.dash.a_client.click()
        vis = self._visible(win)
        self.assertIn("Client", vis)
        self.assertNotIn("Server", vis)
        self.assertNotIn("Daftar printer", vis)
        self.assertEqual(win.nav.currentRow(), GOTO["client"])
        win.close()

    def test_mode_is_remembered_across_restarts_and_settings_has_no_second_role_control(self):
        from nsd.ui.main_window import GOTO, MainWindow
        ctx = self.ctx()
        ctx.settings.set("role", "client")
        ctx.settings.set("role_chosen", True)
        win = MainWindow(ctx)
        self.assertEqual(win.nav.currentRow(), GOTO["client"])
        self.assertNotIn("Server", self._visible(win))
        settings = win.stack.widget(win.stack.count() - 1)
        self.assertFalse(hasattr(settings, "role"))
        win.close()

    def test_scrolling_pages_never_overflow_horizontally_at_the_minimum_window_size(self):
        from PySide6.QtWidgets import QScrollArea
        from nsd.ui.main_window import GOTO, MainWindow
        win = MainWindow(self.ctx())
        win.resize(980, 600)
        win.show()
        for key in ("server", "client"):
            win.nav.setCurrentRow(GOTO[key])
            self.wait(lambda: True)
            self.app.processEvents()
            area = win.stack.currentWidget().findChild(QScrollArea)
            self.assertEqual(area.horizontalScrollBar().maximum(), 0, key)
        win.nav.setCurrentRow(0)
        self.app.processEvents()
        area = win.dash.findChild(QScrollArea)
        self.assertEqual(area.horizontalScrollBar().maximum(), 0, "dashboard")
        nav = win.nav
        self.assertEqual(nav.verticalScrollBar().maximum(), 0, "semua menu muat tanpa menggulir pada tinggi 600")
        win.close()

    def test_every_new_page_renders_in_both_themes_at_the_minimum_window_size(self):
        from nsd.ui import theme
        from nsd.ui.main_window import GOTO, MainWindow
        win = MainWindow(self.ctx())
        win.resize(980, 600)
        for mode in ("light", "dark"):
            theme.apply_theme(self.app, mode)
            for key in ("server", "client"):
                win.nav.setCurrentRow(GOTO[key])
                self.app.processEvents()
                self.assertFalse(win.grab().isNull())
        theme.apply_theme(self.app, "light")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class ServerControlUi(ServerClientPages):
    """Tombol Jalankan server, autostart, dan log aktivitas di halaman Server."""

    def _page(self):
        from nsd.ui.server_page import ServerPage
        ctx = self.ctx(healthy_responses())
        ctx.data_dir = Path(self.tmp.name)
        return ServerPage(ctx), ctx

    def test_button_toggles_and_log_renders(self):
        from nsd.application import activity_service, server_control
        page, ctx = self._page()
        page._update_run_state()
        self.assertEqual(page.run_btn.text(), "Jalankan server")
        with mock.patch.object(server_control, "start", return_value="Server dijalankan di latar belakang.") as st:
            page._toggle_server()
            st.assert_called_once()
        activity_service.ActivityWatcher(FakeAdapter(), ctx.data_dir).emit(
            "job_new", printer="EPSON", document="faktur.pdf", client="PC-KASIR")
        page._render_log()
        self.assertIn("faktur.pdf", page.log_view.toPlainText())
        with mock.patch.object(server_control, "is_running", return_value=True):
            page._update_run_state()
            self.assertEqual(page.run_btn.text(), "Hentikan server")
            with mock.patch.object(server_control, "stop", return_value="ok") as sp:
                page._toggle_server()
                sp.assert_called_once()

    def test_autostart_checkbox_disabled_outside_packaged_windows(self):
        page, _ = self._page()
        self.assertFalse(page.autostart_cb.isEnabled())


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class PrepareDialogUi(ServerClientPages):
    def test_dialog_needs_admin_then_applies(self):
        from nsd.application import server_prepare as sp
        from nsd.ui import prepare_dialog as pd
        from tests.unit.test_server_prepare import Machine
        from nsd.application.server_setup import check_readiness
        m = Machine(elevated=False)
        ctx = self.ctx()
        ctx.adapter = m
        acts = sp.plan(check_readiness(m, addresses=lambda: []))
        dlg = pd.PrepareDialog(ctx, acts)
        self.assertFalse(dlg.apply_btn.isEnabled())                  # belum admin: tombol mati, alasan ada di tooltip
        self.assertIn("administrator", dlg.apply_btn.toolTip())
        m.elevated = True
        dlg._refresh_admin()
        self.assertTrue(dlg.apply_btn.isEnabled())
        self.assertFalse([cb for cb, a in dlg.checks if not a.default_on and cb.isChecked()])
        dlg._done([sp.ActionResult(acts[0], "verified", "Layanan berjalan.")])
        self.assertIn("Berhasil: ", dlg.log.toPlainText())
        self.assertTrue(dlg.applied_any)


@unittest.skipUnless(HAVE_QT, "PySide6 tidak terpasang")
class ClientInstallUi(ServerClientPages):
    def test_install_needs_confirmation_and_reports_honestly(self):
        from PySide6.QtWidgets import QMessageBox
        from nsd.application import client_connect
        from nsd.ui.client_page import ClientPage
        page = ClientPage(self.ctx())
        page.host.setText("SERVER01")
        page.share.setText("EPSON")
        self.assertTrue(page.install_btn.isEnabled())
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No), \
                mock.patch.object(client_connect, "connect_printer") as cp:
            page._install()
            cp.assert_not_called()
        page._installed(client_connect.ConnectResult("unverified", "Perintah terkirim."))
        self.assertIn("Belum terbukti", page.install_result.text())
        page.kind.setCurrentIndex(1)                                                # folder: tidak ada tombol pasang
        self.assertFalse(page.install_btn.isEnabled())
