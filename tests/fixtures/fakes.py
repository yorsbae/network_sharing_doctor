"""Adapter & probe palsu untuk menguji skenario tanpa menyentuh Windows asli."""
from __future__ import annotations

from nsd.windows.powershell import OpResult

OS = {"Caption": "Microsoft Windows 11 Pro", "Version": "10.0.22631", "Build": "22631",
      "ComputerName": "PC-KASIR", "PartOfDomain": False, "Domain": "WORKGROUP"}


class FakeAdapter:
    """responses: operasi -> OpResult | callable(**params)->OpResult. Operasi tak terdaftar = unsupported."""

    def __init__(self, responses=None, elevated=False):
        self.responses = responses or {}
        self.elevated = elevated
        self.calls: list[tuple[str, dict]] = []

    def is_windows(self): return True
    def is_elevated(self): return self.elevated

    def run(self, operation, **params):
        self.calls.append((operation, params))
        r = self.responses.get(operation)
        if r is None:
            return OpResult(False, error="tidak didukung (fake)", unsupported=True)
        return r(**params) if callable(r) else r


class FakeNet:
    def __init__(self, resolve=None, open_ports=(445, 135), resolve_error=False):
        self._resolve = resolve or ["192.168.1.10"]
        self.open_ports = set(open_ports)
        self.resolve_error = resolve_error
        self.connects: list[tuple[str, int]] = []

    def resolve(self, host):
        if self.resolve_error:
            raise OSError("no such host")
        return list(self._resolve)

    def tcp_connect(self, host, port, timeout=3.0):
        self.connects.append((host, port))
        return (True, "connected") if port in self.open_ports else (False, "timeout")


def ok(data): return OpResult(True, data=data)


def svc(name, state="Running", start="Automatic"):
    return ok({"Name": name, "Status": state, "StartType": start})


def healthy_responses():
    return {
        "os_info": ok(OS),
        "get_service": lambda service: svc(service),
        "net_profile": ok([{"Category": "Private", "IPv4": "Internet"}]),
        "firewall_sharing": ok([{"Enabled": "True", "Direction": "Inbound", "Action": "Allow", "Profile": "Private"}]),
        "smb_client_config": ok({"EnableInsecureGuestLogons": False}),
        "smb_server_config": ok({"EnableSMB1Protocol": False, "EnableSMB2Protocol": True}),
        "list_local_printers": ok([{"Name": "EPSON L3210", "Driver": "EPSON", "Port": "USB001", "Shared": True,
                                    "ShareName": "EPSON", "Status": "Normal"}]),
        "list_remote_printers": ok([{"Name": "EPSON L3210", "Driver": "EPSON", "Port": "USB001", "Shared": True,
                                     "ShareName": "EPSON", "Status": "Normal"}]),
        "list_local_shares": ok([{"Name": "DATA", "Special": False}]),
        "test_unc": ok({"Ok": True, "ErrorType": None, "HResult": 0, "Message": None}),
        "recent_print_errors": ok(None),
    }
