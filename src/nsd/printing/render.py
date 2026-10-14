from __future__ import annotations

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo

from nsd.paper import Orientation, PageLayout
from nsd.printing.jobs import REF_DPI, PrintJob, RenderCtx

PDF_LABEL = "Simpan sebagai PDF"


class PrintError(RuntimeError):
    pass


def available_printers() -> list[str]:
    try:
        return list(QPrinterInfo.availablePrinterNames())
    except Exception:  # noqa: BLE001 - tanpa layanan cetak, anggap kosong
        return []


def make_ctx(layout: PageLayout) -> RenderCtx:
    s = layout.scale_percent / 100.0
    return RenderCtx(width=layout.content_width_mm / 25.4 * REF_DPI / s,
                     height=layout.content_height_mm / 25.4 * REF_DPI / s,
                     px_per_mm=REF_DPI / 25.4 / s, layout=layout)


def paint_page(painter: QPainter, dpi: float, layout: PageLayout, job: PrintJob, ctx: RenderCtx, index: int) -> None:
    """Satu-satunya jalur gambar. Titik asal painter = pojok kiri-atas KERTAS (bukan margin)."""
    ppm = dpi / 25.4
    painter.save()
    painter.translate(layout.margins.left * ppm, layout.margins.top * ppm)
    k = dpi / REF_DPI * layout.scale_percent / 100.0
    painter.scale(k, k)
    painter.setRenderHint(QPainter.Antialiasing)
    job.paint(painter, ctx, index)
    painter.restore()


def render_preview(layout: PageLayout, job: PrintJob, index: int = 0, dpi: float = 80.0) -> tuple[QImage, int]:
    ctx = make_ctx(layout)
    pages = job.prepare(ctx)
    index = max(0, min(index, pages - 1))
    w, h = layout.page_mm
    img = QImage(round(w / 25.4 * dpi), round(h / 25.4 * dpi), QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    try:
        paint_page(p, dpi, layout, job, ctx, index)
    finally:
        p.end()
    return img, pages


def _configure(printer: QPrinter, layout: PageLayout, copies: int) -> None:
    p = layout.paper
    size = QPageSize(QSizeF(p.width_mm, p.height_mm), QPageSize.Millimeter, p.name, QPageSize.ExactMatch)
    pl = QPageLayout(size, QPageLayout.Landscape if layout.orientation is Orientation.LANDSCAPE
                     else QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
    if not printer.setPageLayout(pl):
        raise PrintError(f"Printer menolak ukuran {p.width_mm:g}×{p.height_mm:g} mm.")
    printer.setFullPage(True)           # margin diatur sendiri oleh tata letak
    printer.setCopyCount(max(1, copies))


def print_job(layout: PageLayout, job: PrintJob, printer_name: str | None = None,
              pdf_path: str | None = None, copies: int = 1) -> int:
    """Cetak ke printer bernama, atau ke PDF bila pdf_path diberikan. Mengembalikan jumlah halaman."""
    if not pdf_path and not printer_name:
        raise PrintError("Pilih printer atau tujuan PDF.")
    printer = QPrinter(QPrinter.HighResolution)
    if pdf_path:
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(pdf_path)
    else:
        if printer_name not in available_printers():
            raise PrintError(f"Printer '{printer_name}' tidak ditemukan.")
        printer.setPrinterName(printer_name)
    printer.setDocName(job.title)
    _configure(printer, layout, copies)
    ctx = make_ctx(layout)
    pages = job.prepare(ctx)
    painter = QPainter()
    if not painter.begin(printer):
        raise PrintError("Tidak dapat memulai pencetakan (printer tidak siap atau tujuan tidak bisa ditulis).")
    try:
        dpi = float(printer.resolution())
        for i in range(pages):
            if i:
                printer.newPage()
            paint_page(painter, dpi, layout, job, ctx, i)
    finally:
        painter.end()
    return pages


def printer_hard_margin_mm(printer_name: str) -> float:
    """Area tak-tercetak terbesar yang dilaporkan printer; 0 bila tidak diketahui."""
    try:
        pr = QPrinter(QPrinterInfo.printerInfo(printer_name))
        pl = pr.pageLayout(); pl.setUnits(QPageLayout.Millimeter)
        m = pl.minimumMargins()
        return round(max(m.left(), m.top(), m.right(), m.bottom()), 1)
    except Exception:  # noqa: BLE001
        return 0.0
