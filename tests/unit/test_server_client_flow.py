import unittest

from nsd.application import discovery, server_setup
from nsd.windows.powershell import OpResult
from tests.fixtures.fakes import FakeAdapter, healthy_responses, ok, svc


def printers(shared=True, status="Normal", name="EPSON L3210", share="EPSON"):
    return ok([{"Name": name, "Driver": "EPSON", "Port": "USB001", "Shared": shared,
                "ShareName": share if shared else "", "Status": status}])


def readiness(responses=None, addresses=("192.168.1.10",)):
    r = healthy_responses()
    r.update(responses or {})
    return server_setup.check_readiness(FakeAdapter(r), addresses=lambda: list(addresses))


class ServerReadiness(unittest.TestCase):
    def test_healthy_server_is_ready_and_gives_addresses_for_clients(self):
        r = readiness()
        self.assertTrue(r.ready)
        self.assertEqual(r.verdict, ("Siap dipakai client", "ok"))
        self.assertEqual(r.info.computer_name, "PC-KASIR")
        self.assertEqual(r.info.addresses, ["192.168.1.10"])
        self.assertEqual([p.unc for p in r.info.printers], ["\\\\PC-KASIR\\EPSON"])

    def test_stopped_spooler_blocks_with_a_manual_howto(self):
        r = readiness({"get_service": lambda service: svc(service, "Stopped" if service == "Spooler" else "Running")})
        step = next(s for s in r.steps if s.key == "spooler")
        self.assertEqual((step.tone, step.status), ("fail", "Berhenti"))
        self.assertIn("services.msc", step.howto)
        self.assertFalse(r.ready)
        self.assertEqual(r.verdict[1], "fail")

    def test_no_printer_installed_and_printer_not_shared_are_different_failures(self):
        none = next(s for s in readiness({"list_local_printers": ok([])}).steps if s.key == "printers")
        unshared = next(s for s in readiness({"list_local_printers": printers(shared=False)}).steps if s.key == "printers")
        self.assertEqual(none.status, "Tidak ada printer")
        self.assertEqual(unshared.status, "Belum dibagikan")
        self.assertIn("Share this printer", unshared.howto)

    def test_public_profile_is_a_warning_not_a_failure(self):
        r = readiness({"net_profile": ok([{"Category": "Public", "IPv4": "Internet"}])})
        self.assertEqual(next(s for s in r.steps if s.key == "profile").tone, "warn")
        self.assertEqual(r.verdict[1], "warn")

    def test_disabled_firewall_rules_fail_without_suggesting_to_turn_the_firewall_off(self):
        r = readiness({"firewall_sharing": ok([{"Enabled": "False", "Direction": "Inbound", "Action": "Allow"}])})
        step = next(s for s in r.steps if s.key == "firewall")
        self.assertEqual(step.tone, "fail")
        self.assertIn("Jangan mematikan firewall", step.howto)

    def test_unreadable_system_is_unknown_never_ready(self):
        r = server_setup.check_readiness(FakeAdapter({}), addresses=lambda: [])
        self.assertTrue(all(s.tone == "unknown" for s in r.steps))
        self.assertEqual(r.verdict, ("Belum diperiksa", "unknown"))
        self.assertFalse(r.ready)

    def test_unhealthy_printer_status_is_a_warning(self):
        r = readiness({"list_local_printers": printers(status="PaperOut")})
        self.assertEqual(next(s for s in r.steps if s.key == "printers").tone, "warn")

    def test_only_read_operations_are_used(self):
        a = FakeAdapter(healthy_responses())
        server_setup.check_readiness(a, addresses=lambda: [])
        self.assertTrue({op for op, _ in a.calls} <= {"os_info", "get_service", "net_profile", "firewall_sharing",
                                                      "list_local_printers"})

    def test_client_instructions_contain_unc_and_ip_fallback_and_are_empty_without_shares(self):
        text = server_setup.client_instructions(readiness().info)
        self.assertIn("\\\\PC-KASIR\\EPSON", text)
        self.assertIn("\\\\192.168.1.10\\EPSON", text)
        self.assertIn("Windows + R", text)
        self.assertEqual(server_setup.client_instructions(readiness({"list_local_printers": ok([])}).info), "")

    def test_local_addresses_skip_loopback_and_link_local_and_put_route_first(self):
        got = server_setup.local_ipv4_addresses(
            names=lambda: ["127.0.0.1", "169.254.3.4", "192.168.1.20", "10.0.0.7", "::1", "bukan-ip"],
            route=lambda: "10.0.0.7")
        self.assertEqual(got, ["10.0.0.7", "192.168.1.20"])


class Discovery(unittest.TestCase):
    def test_subnet_hosts_only_for_private_ipv4_and_excludes_self(self):
        hosts = discovery.subnet_hosts("192.168.1.20")
        self.assertEqual(len(hosts), 253)
        self.assertNotIn("192.168.1.20", hosts)
        self.assertEqual(discovery.subnet_hosts("8.8.8.8"), [])
        self.assertEqual(discovery.subnet_hosts("127.0.0.1"), [])
        self.assertEqual(discovery.subnet_hosts("169.254.1.1"), [])
        self.assertEqual(discovery.subnet_hosts("::1"), [])
        self.assertEqual(discovery.subnet_hosts("bukan-ip"), [])

    def test_finds_hosts_with_open_smb_port_names_them_and_sorts_by_address(self):
        probed = []

        def probe(host, timeout):
            probed.append(host)
            return host in ("192.168.1.9", "192.168.1.100")

        res = discovery.discover(["192.168.1.20"], probe=probe, namer=lambda ip: {"192.168.1.9": "PC-KASIR"}.get(ip, ""))
        self.assertEqual([(s.address, s.name) for s in res.servers], [("192.168.1.9", "PC-KASIR"), ("192.168.1.100", "")])
        self.assertEqual(res.servers[0].label, "PC-KASIR (192.168.1.9)")
        self.assertEqual(res.servers[1].host, "192.168.1.100")
        self.assertEqual(res.scanned, 253)
        self.assertEqual(res.subnets, ["192.168.1.0/24"])
        self.assertNotIn("192.168.1.20", probed)

    def test_never_scans_outside_the_local_private_subnet(self):
        probed = []
        discovery.discover(["10.1.2.3", "8.8.8.8"], probe=lambda h, t: probed.append(h) or False, namer=lambda ip: "")
        self.assertTrue(probed)
        self.assertTrue(all(h.startswith("10.1.2.") for h in probed))

    def test_no_private_address_gives_an_actionable_note_and_scans_nothing(self):
        called = []
        res = discovery.discover(["8.8.8.8"], probe=lambda h, t: called.append(h) or True)
        self.assertEqual((res.servers, called), ([], []))
        self.assertIn("manual", res.note)

    def test_empty_result_explains_what_to_check(self):
        res = discovery.discover(["192.168.1.20"], probe=lambda h, t: False)
        self.assertIn("port 445", res.note)
        self.assertIn("manual", res.note)

    def test_stop_request_cancels_without_a_misleading_empty_note(self):
        res = discovery.discover(["192.168.1.20"], probe=lambda h, t: False, should_stop=lambda: True)
        self.assertTrue(res.cancelled)
        self.assertEqual(res.note, "")

    def test_a_failing_probe_or_namer_does_not_break_discovery(self):
        def probe(host, timeout):
            if host == "192.168.1.5":
                raise RuntimeError("boom")
            return host == "192.168.1.6"

        def namer(ip):
            raise OSError("no ptr")

        res = discovery.discover(["192.168.1.20"], probe=probe, namer=namer)
        self.assertEqual([s.address for s in res.servers], ["192.168.1.6"])

    def test_progress_reaches_the_total(self):
        seen = []
        discovery.discover(["192.168.1.20"], probe=lambda h, t: False, progress=lambda d, t: seen.append((d, t)))
        self.assertEqual(seen[-1], (253, 253))


if __name__ == "__main__":
    unittest.main()
