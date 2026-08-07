"""Storyboard PDF export via ReportLab."""

from __future__ import annotations

import enum
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, LETTER
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from directo.gallery import Gallery, ImageRecord
from directo.observability import get_logger

log = get_logger("directo.printing")


class StoryboardLayout(str, enum.Enum):
    """Predefined storyboard layouts."""

    ONE_UP = "1up"        # 1 image per page — pitch / director review
    TWO_UP = "2up"        # 2 images per page
    FOUR_UP = "4up"       # 4 images per page
    CONTACT = "contact"   # 6x4 thumbnail grid


@dataclass
class StoryboardPanel:
    """A single panel to include in the export."""

    image_path: str
    shot_label: str = ""           # e.g. "SHOT 12A"
    caption: str = ""              # short description
    notes: str = ""                # markdown-ish, will be word-wrapped
    rating: int = 0


@dataclass
class StoryboardConfig:
    """Export configuration."""

    layout: StoryboardLayout = StoryboardLayout.TWO_UP
    page_size: str = "A4"          # "A4" | "A3" | "LETTER"
    project_title: str = ""
    include_metadata: bool = True  # show prompt/model/seed
    include_qr_to_gallery: bool = False
    dpi: int = 150
    margin_cm: float = 1.5
    page_number: bool = True


_PAGE_SIZES = {"A4": A4, "A3": A3, "LETTER": LETTER}


class StoryboardExporter:
    """Render a list of image paths (or Gallery records) into a PDF."""

    def __init__(self, config: StoryboardConfig | None = None) -> None:
        self.config = config or StoryboardConfig()
        self._register_default_fonts()

    def _register_default_fonts(self) -> None:
        """Try to register a Unicode font; fall back to Helvetica."""
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                try:
                    pdfmetrics.registerFont(TTFont("DirectoSans", path))
                    self._font = "DirectoSans"
                    self._font_bold = "DirectoSans"
                    return
                except Exception:  # noqa: BLE001
                    continue
        self._font = "Helvetica"
        self._font_bold = "Helvetica-Bold"

    # ----------------- Public API -----------------

    def export(
        self,
        panels: Iterable[StoryboardPanel | ImageRecord | str],
        output_path: str | Path,
        *,
        gallery: Gallery | None = None,
    ) -> Path:
        """Render ``panels`` to ``output_path``.

        Each panel can be:
        - a string (treated as a path)
        - an :class:`ImageRecord` (metadata is read from it; path is
          taken from the record)
        - a :class:`StoryboardPanel` (full control)

        If a :class:`Gallery` is passed and the panel is a path string,
        we look up the record to fill in metadata.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        norm_panels: list[StoryboardPanel] = []
        for item in panels:
            norm_panels.append(self._normalize(item, gallery))

        c = canvas.Canvas(str(output_path), pagesize=_PAGE_SIZES.get(
            self.config.page_size, A4
        ))
        self._draw_cover(c, norm_panels)

        layout_fn = {
            StoryboardLayout.ONE_UP: self._draw_1up,
            StoryboardLayout.TWO_UP: self._draw_2up,
            StoryboardLayout.FOUR_UP: self._draw_4up,
            StoryboardLayout.CONTACT: self._draw_contact,
        }[self.config.layout]
        layout_fn(c, norm_panels)

        c.save()
        log.bind(output=str(output_path)).info(
            f"storyboard exported ({len(norm_panels)} panels, layout={self.config.layout.value})"
        )
        return output_path

    # ----------------- Internals -----------------

    def _normalize(
        self, item: StoryboardPanel | ImageRecord | str, gallery: Gallery | None
    ) -> StoryboardPanel:
        if isinstance(item, StoryboardPanel):
            return item
        if isinstance(item, ImageRecord):
            return StoryboardPanel(
                image_path=item.path,
                shot_label=f"frame_{item.id[:6]}",
                caption=(item.prompt or "")[:200],
                notes=item.notes or "",
                rating=item.rating,
            )
        # str path
        rec = gallery.get_by_path(item) if gallery else None
        if rec:
            return StoryboardPanel(
                image_path=item,
                shot_label=f"frame_{rec.id[:6]}",
                caption=(rec.prompt or "")[:200],
                notes=rec.notes or "",
                rating=rec.rating,
            )
        return StoryboardPanel(image_path=item)

    def _draw_cover(self, c: canvas.Canvas, panels: list[StoryboardPanel]) -> None:
        page_w, page_h = c._pagesize
        c.setFillColor(colors.HexColor("#0a0a0f"))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#7c5cff"))
        c.setFont(self._font_bold, 32)
        title = self.config.project_title or "Directo Storyboard"
        c.drawCentredString(page_w / 2, page_h - 5 * cm, title)
        c.setFillColor(colors.HexColor("#9999aa"))
        c.setFont(self._font, 12)
        c.drawCentredString(
            page_w / 2, page_h - 6 * cm,
            f"{len(panels)} panels · layout {self.config.layout.value}",
        )
        c.showPage()

    def _draw_1up(self, c: canvas.Canvas, panels: list[StoryboardPanel]) -> None:
        page_w, page_h = c._pagesize
        m = self.config.margin_cm * cm
        for i, panel in enumerate(panels, 1):
            self._draw_panel(
                c, panel, m, m, page_w - 2 * m, page_h - 2 * m - 1 * cm,
                page_number=i, total=len(panels),
            )
            c.showPage()

    def _draw_2up(self, c: canvas.Canvas, panels: list[StoryboardPanel]) -> None:
        page_w, page_h = c._pagesize
        m = self.config.margin_cm * cm
        half_h = (page_h - 2 * m) / 2 - 0.5 * cm
        full_w = page_w - 2 * m
        for i in range(0, len(panels), 2):
            self._draw_panel(c, panels[i], m, m + half_h + 0.5 * cm, full_w, half_h,
                             page_number=i + 1, total=len(panels))
            if i + 1 < len(panels):
                self._draw_panel(c, panels[i + 1], m, m, full_w, half_h,
                                 page_number=i + 2, total=len(panels))
            c.showPage()

    def _draw_4up(self, c: canvas.Canvas, panels: list[StoryboardPanel]) -> None:
        page_w, page_h = c._pagesize
        m = self.config.margin_cm * cm
        half_w = (page_w - 2 * m) / 2 - 0.25 * cm
        half_h = (page_h - 2 * m) / 2 - 0.25 * cm
        for i in range(0, len(panels), 4):
            positions = [
                (m, m + half_h + 0.25 * cm, half_w, half_h),
                (m + half_w + 0.25 * cm, m + half_h + 0.25 * cm, half_w, half_h),
                (m, m, half_w, half_h),
                (m + half_w + 0.25 * cm, m, half_w, half_h),
            ]
            for j, (x, y, w, h) in enumerate(positions):
                idx = i + j
                if idx < len(panels):
                    self._draw_panel(c, panels[idx], x, y, w, h,
                                     page_number=idx + 1, total=len(panels))
            c.showPage()

    def _draw_contact(self, c: canvas.Canvas, panels: list[StoryboardPanel]) -> None:
        """6x4 thumbnail grid on each page."""
        page_w, page_h = c._pagesize
        m = self.config.margin_cm * cm
        cols, rows = 6, 4
        cell_w = (page_w - 2 * m) / cols - 0.2 * cm
        cell_h = (page_h - 2 * m) / rows - 0.2 * cm
        per_page = cols * rows
        for page_start in range(0, len(panels), per_page):
            for k in range(per_page):
                idx = page_start + k
                if idx >= len(panels):
                    break
                col, row = k % cols, k // cols
                x = m + col * (cell_w + 0.2 * cm)
                y = m + (rows - 1 - row) * (cell_h + 0.2 * cm)
                self._draw_thumb(c, panels[idx], x, y, cell_w, cell_h)
            c.showPage()

    def _draw_panel(
        self, c: canvas.Canvas, panel: StoryboardPanel,
        x: float, y: float, w: float, h: float,
        *, page_number: int, total: int,
    ) -> None:
        """Draw one image + caption box."""
        # Image takes 70% of vertical space; caption takes the rest.
        img_h = h * 0.7
        cap_h = h - img_h - 0.4 * cm
        try:
            c.drawImage(
                panel.image_path, x, y + cap_h, w, img_h,
                preserveAspectRatio=True, anchor="c", mask="auto",
            )
        except Exception as exc:  # noqa: BLE001
            c.setFillColor(colors.HexColor("#1a1a25"))
            c.rect(x, y + cap_h, w, img_h, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#f87171"))
            c.setFont(self._font, 10)
            c.drawString(x + 0.5 * cm, y + cap_h + img_h / 2, f"image error: {exc}")

        # Caption box
        c.setFillColor(colors.HexColor("#14141d"))
        c.rect(x, y, w, cap_h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#7c5cff"))
        c.setFont(self._font_bold, 11)
        label = panel.shot_label or f"frame {page_number}"
        c.drawString(x + 0.4 * cm, y + cap_h - 0.6 * cm, label)
        if panel.rating:
            stars = "★" * panel.rating + "☆" * (5 - panel.rating)
            c.setFillColor(colors.HexColor("#facc15"))
            c.drawRightString(x + w - 0.4 * cm, y + cap_h - 0.6 * cm, stars)

        c.setFillColor(colors.HexColor("#e8e8f0"))
        c.setFont(self._font, 9)
        text = c.beginText(x + 0.4 * cm, y + cap_h - 1.2 * cm)
        for line in textwrap.wrap(panel.caption or "", width=100):
            text.textLine(line)
        c.drawText(text)

        if panel.notes:
            c.setFillColor(colors.HexColor("#9999aa"))
            text = c.beginText(x + 0.4 * cm, y + 0.5 * cm)
            for line in textwrap.wrap("• " + panel.notes, width=100)[:4]:
                text.textLine(line)
            c.drawText(text)

        if self.config.page_number:
            c.setFillColor(colors.HexColor("#9999aa"))
            c.setFont(self._font, 7)
            c.drawRightString(x + w, y - 0.2 * cm, f"{page_number}/{total}")

    def _draw_thumb(
        self, c: canvas.Canvas, panel: StoryboardPanel,
        x: float, y: float, w: float, h: float,
    ) -> None:
        try:
            c.drawImage(panel.image_path, x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            c.setFillColor(colors.HexColor("#1a1a25"))
            c.rect(x, y, w, h, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#7c5cff"))
        c.setLineWidth(0.5)
        c.rect(x, y, w, h, fill=0, stroke=1)
        if panel.shot_label:
            c.setFillColor(colors.HexColor("#9999aa"))
            c.setFont(self._font, 6)
            c.drawString(x + 0.1 * cm, y + 0.1 * cm, panel.shot_label)
