from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSizeF, Qt
from PySide6.QtGui import QAbstractTextDocumentLayout, QColor, QFont, QPainter, QPalette, QPen, QTextDocument

from nsd.paper import PageLayout

REF_DPI = 96.0   # satuan logis pekerjaan cetak: 1 unit = 1/96 inci, tidak bergantung perangkat


@dataclass(frozen=True)
class RenderCtx:
    width: float          # lebar area isi (unit logis)
    height: float         # tinggi area isi (unit logis)
    px_per_mm: float      # unit logis per mm NYATA (memperhitungkan skala)
    layout: PageLayout


class PrintJob:
    title = "Dokumen"

    def prepare(self, ctx: RenderCtx) -> int:
        """Tata letak untuk area isi ini; kembalikan jumlah halaman (>= 1)."""
        raise NotImplementedError

    def paint(self, painter: QPainter, ctx: RenderCtx, index: int) -> None:
        raise NotImplementedError


class TextJob(PrintJob):
    """Teks biasa (mis. laporan diagnosis), huruf monospace, paginasi otomatis."""

    def __init__(self, text: str, title: str = "Laporan", pt: float = 9.0) -> None:
        self.text, self.title, self.pt = text, title, pt
        self._doc: QTextDocument | None = None

    def prepare(self, ctx: RenderCtx) -> int:
        doc = QTextDocument()
        f = QFont("Courier New"); f.setStyleHint(QFont.Monospace)
        f.setPixelSize(max(4, round(self.pt * REF_DPI / 72)))
        doc.setDefaultFont(f)
        doc.setDocumentMargin(0)
        doc.setPlainText(self.text)
        doc.setPageSize(QSizeF(ctx.width, ctx.height))
        self._doc = doc
        return max(1, doc.pageCount())

    def paint(self, painter: QPainter, ctx: RenderCtx, index: int) -> None:
        assert self._doc is not None, "prepare() belum dipanggil"
        painter.save()
        painter.setClipRect(QRectF(0, 0, ctx.width, ctx.height))
        painter.translate(0, -index * ctx.height)
        paint_ctx = QAbstractTextDocumentLayout.PaintContext()
        paint_ctx.palette.setColor(QPalette.Text, QColor("black"))     # tinta hitam di kertas putih, apa pun temanya
        paint_ctx.clip = QRectF(0, index * ctx.height, ctx.width, ctx.height)
        self._doc.documentLayout().draw(painter, paint_ctx)
        painter.restore()


class RulerTestJob(PrintJob):
    """Halaman uji: tepi kertas, area isi, dan penggaris 10 mm. Untuk memeriksa ukuran & margin sebenarnya."""
    title = "Halaman uji ukuran kertas"

    def prepare(self, ctx: RenderCtx) -> int:
        return 1

    def paint(self, painter: QPainter, ctx: RenderCtx, index: int) -> None:
        lay, k = ctx.layout, ctx.px_per_mm
        m = lay.margins
        pw, ph = lay.page_mm
        painter.save()
        painter.setPen(QPen(QColor("#b91c1c"), max(1.0, k * 0.3), Qt.DashLine))      # tepi kertas
        painter.drawRect(QRectF(-m.left * k, -m.top * k, pw * k, ph * k))
        painter.setPen(QPen(QColor("black"), max(1.0, k * 0.2)))                      # area isi
        painter.drawRect(QRectF(0, 0, ctx.width, ctx.height))
        small = QFont("Arial"); small.setPixelSize(max(6, round(2.8 * k)))
        painter.setFont(small)
        n = int(ctx.width // (10 * k))
        for i in range(n + 1):                                                         # penggaris atas
            x = i * 10 * k
            painter.drawLine(x, 0, x, 4 * k if i % 5 else 7 * k)
            if i % 5 == 0 and i:
                painter.drawText(QRectF(x + 0.5 * k, 7.5 * k, 12 * k, 4 * k), f"{i}")
        for j in range(int(ctx.height // (10 * k)) + 1):                               # penggaris kiri
            y = j * 10 * k
            painter.drawLine(0, y, 4 * k if j % 5 else 7 * k, y)
            if j % 5 == 0 and j:
                painter.drawText(QRectF(7.5 * k, y + 0.5 * k, 12 * k, 4 * k), f"{j}")
        big = QFont("Arial"); big.setPixelSize(max(8, round(4.2 * k))); big.setBold(True)
        painter.setFont(big)
        info = (f"{lay.paper.name}\n{pw:g} x {ph:g} mm "
                f"({'lanskap' if lay.orientation.value == 'landscape' else 'potret'})\n"
                f"Margin {m.top:g}/{m.right:g}/{m.bottom:g}/{m.left:g} mm, skala {lay.scale_percent:g}%\n"
                f"Area isi {lay.content_width_mm:g} x {lay.content_height_mm:g} mm")
        painter.drawText(QRectF(14 * k, 14 * k, ctx.width - 20 * k, 30 * k), Qt.TextWordWrap, info)
        painter.setFont(small)
        painter.drawText(QRectF(14 * k, 46 * k, ctx.width - 20 * k, 20 * k), Qt.TextWordWrap,
                         "Garis putus merah = tepi kertas. Angka pada penggaris = sentimeter; jarak antar tanda besar = 50 mm. "
                         "Bila garis merah terpotong, printer tidak menerima ukuran ini apa adanya.")
        painter.restore()


class PdfJob(PrintJob):
    """Berkas PDF (mis. hasil cetak dari browser). Tiap halaman dimuat pas ke area isi, rasio dijaga."""
    _RENDER_DPI = 200

    def __init__(self, path: str, title: str | None = None) -> None:
        from pathlib import Path

        from PySide6.QtPdf import QPdfDocument

        self.path = str(path)
        self.title = title or Path(path).stem
        self._doc = QPdfDocument()
        if self._doc.load(self.path) != QPdfDocument.Error.None_:
            raise ValueError(f"PDF tidak dapat dibuka: {self.path}")

    def prepare(self, ctx: RenderCtx) -> int:
        return max(1, self._doc.pageCount())

    def paint(self, painter: QPainter, ctx: RenderCtx, index: int) -> None:
        from PySide6.QtCore import QSize

        if not 0 <= index < self._doc.pageCount():
            return
        pt = self._doc.pagePointSize(index)
        if pt.width() <= 0 or pt.height() <= 0:
            return
        fit = min(ctx.width / pt.width(), ctx.height / pt.height())
        w, h = pt.width() * fit, pt.height() * fit
        px = QSize(max(1, round(pt.width() / 72 * self._RENDER_DPI)), max(1, round(pt.height() / 72 * self._RENDER_DPI)))
        painter.drawImage(QRectF((ctx.width - w) / 2, 0, w, h), self._doc.render(index, px))
