"""Penilaian jalur ukuran kertas khusus di client (vision A.4.4, A.6 #2).

Fungsi murni: menerima kemampuan driver yang SUDAH dikumpulkan (nanti dari adapter Windows) dan
mengembalikan jalur yang masuk akal beserta batasannya. Tidak menjanjikan hasil: jalur bergantung
driver dan belum diuji di Windows asli (lihat progres.md, 'Belum terbukti').
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from nsd.paper.models import PaperSize


class Connection(str, Enum):
    SHARED = "shared"        # sambungan ke printer share \\server\printer
    LOCAL_NET = "local_net"  # antrean lokal di client -> port TCP/IP / IPP langsung ke printer
    LOCAL_USB = "local_usb"  # printer terpasang langsung di client
    UNKNOWN = "unknown"


class Availability(str, Enum):
    AVAILABLE = "available"          # prasyarat terpenuhi menurut data driver
    NEEDS_ADMIN = "needs_admin"      # bisa, tetapi perlu hak admin di client
    NOT_SUPPORTED = "not_supported"  # data driver menunjukkan tidak bisa
    UNKNOWN = "unknown"              # data driver tidak cukup; JANGAN diklaim bisa


@dataclass(frozen=True)
class DriverCaps:
    connection: Connection = Connection.UNKNOWN
    # DeviceCapabilities DC_MINEXTENT / DC_MAXEXTENT, mm (lebar, tinggi); None = tidak diketahui
    min_extent_mm: tuple[float, float] | None = None
    max_extent_mm: tuple[float, float] | None = None
    supports_user_size: bool | None = None   # driver menerima DMPAPER_USER / dmPaperWidth+Length
    client_is_admin: bool = False
    driver_is_v4: bool | None = None


class Strategy(str, Enum):
    PER_JOB = "per_job"                  # DEVMODE per dokumen; tanpa admin, tanpa server
    CLIENT_LOCAL_FORM = "client_form"    # formulir di spooler client (admin client)
    LOCAL_QUEUE = "local_queue"          # antrean lokal di client yang menunjuk ke printer/share
    SERVER_FORM = "server_form"          # formulir di server (admin SERVER), bukan jalur utama


@dataclass(frozen=True)
class StrategyOption:
    strategy: Strategy
    availability: Availability
    depends_on_server: bool
    needs_client_admin: bool
    verified_on_windows: bool
    reasons: tuple[str, ...]

    @property
    def usable(self) -> bool:
        return self.availability in (Availability.AVAILABLE, Availability.NEEDS_ADMIN)


def _fits(paper: PaperSize, caps: DriverCaps) -> tuple[bool | None, str]:
    """Orientasi-agnostik: bandingkan sisi pendek dengan pendek, sisi panjang dengan panjang."""
    if caps.min_extent_mm is None or caps.max_extent_mm is None:
        return None, "Rentang ukuran yang didukung driver tidak diketahui."
    mn, mx = sorted(caps.min_extent_mm), sorted(caps.max_extent_mm)
    short, long_ = paper.width_mm, paper.height_mm   # PaperSize sudah terurut pendek <= panjang
    if short < mn[0] or long_ < mn[1]:
        return False, f"Lebih kecil dari ukuran minimum driver ({mn[0]:g}×{mn[1]:g} mm)."
    if short > mx[0] or long_ > mx[1]:
        return False, f"Lebih besar dari ukuran maksimum driver ({mx[0]:g}×{mx[1]:g} mm)."
    return True, f"Dalam rentang driver ({mn[0]:g}×{mn[1]:g} – {mx[0]:g}×{mx[1]:g} mm)."


def assess(paper: PaperSize, caps: DriverCaps) -> list[StrategyOption]:
    """Kembalikan jalur terurut dari yang paling mandiri dari server."""
    fit, fit_msg = _fits(paper, caps)
    opts: list[StrategyOption] = []

    # 1) Per-dokumen
    if caps.supports_user_size is False or fit is False:
        av = Availability.NOT_SUPPORTED
        why = (fit_msg if fit is False else "Driver tidak menerima ukuran kustom per dokumen.",)
    elif caps.supports_user_size and fit:
        av, why = Availability.AVAILABLE, (fit_msg, "Tanpa hak admin dan tanpa mengubah server.")
    else:
        av = Availability.UNKNOWN
        why = (fit_msg if fit is None else "Dukungan ukuran kustom driver belum diketahui.",
               "Jangan diklaim bisa sebelum diuji dengan driver ini.")
    opts.append(StrategyOption(Strategy.PER_JOB, av, False, False, False, tuple(why)))

    # 2) Formulir di client
    if fit is False:
        av2, why2 = Availability.NOT_SUPPORTED, (fit_msg,)
    elif fit is None:
        av2, why2 = Availability.UNKNOWN, (fit_msg, "Tidak diklaim bisa sebelum rentang driver diketahui.")
    elif caps.connection is Connection.SHARED:
        av2 = Availability.UNKNOWN
        why2 = ("Untuk sambungan ke printer share, belum terbukti apakah formulir lokal client dipakai "
                "atau daftar formulir server yang berlaku.",)
    else:
        av2 = Availability.AVAILABLE if caps.client_is_admin else Availability.NEEDS_ADMIN
        why2 = ("Formulir ditambahkan ke spooler komputer client sendiri.", "Memerlukan hak admin di client.")
    opts.append(StrategyOption(Strategy.CLIENT_LOCAL_FORM, av2, False, True, False, tuple(why2)))

    # 3) Antrean lokal (tidak bergantung formulir server)
    if fit is False:
        av3, why3 = Availability.NOT_SUPPORTED, (fit_msg,)
    elif fit is None:
        av3, why3 = Availability.UNKNOWN, (fit_msg, "Tidak diklaim bisa sebelum rentang driver diketahui.")
    else:
        av3 = Availability.AVAILABLE if caps.client_is_admin else Availability.NEEDS_ADMIN
        why3 = ("Printer dipasang sebagai antrean lokal di client dengan driver/formulir milik client.",
                "Pengiriman tetap lewat share/jaringan; hanya pengaturan kertas yang mandiri.",
                "Memasang driver dapat dibatasi kebijakan Point and Print / hak admin.")
    opts.append(StrategyOption(Strategy.LOCAL_QUEUE, av3, caps.connection is Connection.SHARED, True, False, tuple(why3)))

    # 4) Server: hanya informasi, bukan jalur utama
    opts.append(StrategyOption(
        Strategy.SERVER_FORM, Availability.UNKNOWN, True, False, False,
        ("Membutuhkan hak admin di SERVER dan memengaruhi semua client.",
         "Tidak dilakukan tanpa konfirmasi eksplisit (vision A.4.4).")))
    return opts


def best(opts: list[StrategyOption]) -> StrategyOption | None:
    """Jalur pertama yang tersedia tanpa server; None bila tidak ada."""
    return next((o for o in opts if o.usable and not o.depends_on_server and o.strategy is not Strategy.SERVER_FORM), None)
