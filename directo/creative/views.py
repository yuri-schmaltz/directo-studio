"""Multi-view gallery renderer.

Turns a list of :class:`ImageRecord` into a self-contained HTML
page. Four layouts:

- :attr:`ViewLayout.GRID`    — uniform thumbnails, equal aspect, easy scan
- :attr:`ViewLayout.MASONRY` — Pinterest-style, preserves aspect ratio
- :attr:`ViewLayout.LIST`    — compact, dense, good for "I have 2000 images"
- :attr:`ViewLayout.TIMELINE` — chronological, good for "what did I do this week"

The output is a single HTML file with embedded CSS. Images are
referenced by ``file://`` URL or relative path — the page is meant to
be opened locally or served by a tiny static server.

Why HTML and not PNG/PDF? Because the gallery is interactive
(filter, search, rate). The renderer emits vanilla JS for that, no
build step, no framework.
"""

from __future__ import annotations

import base64
import enum
import html
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from directo.gallery import Gallery, ImageRecord
from directo.observability import get_logger

log = get_logger("directo.views")


class ViewLayout(str, enum.Enum):
    GRID = "grid"
    MASONRY = "masonry"
    LIST = "list"
    TIMELINE = "timeline"


@dataclass
class GalleryViewConfig:
    """Configuration for a rendered gallery view."""

    layout: ViewLayout = ViewLayout.GRID
    title: str = "Directo Gallery"
    project: str | None = None
    columns: int = 4
    show_metadata: bool = True
    show_prompt: bool = True
    show_seed: bool = True
    show_tags: bool = True
    show_rating: bool = True
    embed_thumbnails: bool = False  # embed base64 (heavy!) or reference paths
    thumbnail_max_px: int = 256
    accent: str = "#7c5cff"
    bg: str = "#0a0a0f"
    text: str = "#e8e8f0"
    include_filters: bool = True


# Lightweight client-side filter logic. No external deps.
_FILTER_JS = r"""
const cards = document.querySelectorAll('.card');
const search = document.getElementById('search');
const ratingFilter = document.getElementById('rating-filter');
const favOnly = document.getElementById('fav-only');

function applyFilters() {
  const q = (search.value || '').toLowerCase().trim();
  const minR = parseInt(ratingFilter.value || '0', 10);
  const fav = favOnly.checked;
  let shown = 0;
  cards.forEach(c => {
    const txt = c.dataset.search || '';
    const r = parseInt(c.dataset.rating || '0', 10);
    const f = c.dataset.fav === '1';
    const ok = (!q || txt.includes(q)) && r >= minR && (!fav || f);
    c.style.display = ok ? '' : 'none';
    if (ok) shown++;
  });
  document.getElementById('counter').textContent = shown + ' of ' + cards.length;
}

[search, ratingFilter, favOnly].forEach(el => el && el.addEventListener('input', applyFilters));
applyFilters();
"""


class GalleryView:
    """Render an :class:`ImageRecord` collection as an HTML page."""

    def __init__(self, config: GalleryViewConfig | None = None) -> None:
        self.config = config or GalleryViewConfig()

    # ----------------- Public API -----------------

    def render(
        self,
        images: Iterable[ImageRecord],
        output: str | Path,
        *,
        layout: ViewLayout | None = None,
        gallery: Gallery | None = None,
    ) -> Path:
        """Render ``images`` into a self-contained HTML file at ``output``."""
        records = list(images)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if layout is not None:
            self.config.layout = layout

        # Filter by project if config sets one
        if self.config.project:
            records = [r for r in records if r.project == self.config.project]

        # Sort by created_at desc for grid/list; keep insertion order for timeline
        if self.config.layout != ViewLayout.TIMELINE:
            records = sorted(records, key=lambda r: r.created_at, reverse=True)

        html_body = self._build_html(records)
        output.write_text(html_body, encoding="utf-8")
        log.bind(
            output=str(output), layout=self.config.layout.value, n=len(records)
        ).info("gallery view rendered")
        return output

    # ----------------- Internals -----------------

    def _build_html(self, records: list[ImageRecord]) -> str:
        c = self.config
        layout = c.layout.value

        cards = "\n".join(self._card(r) for r in records)

        filters = ""
        if c.include_filters:
            filters = f"""
            <div class="filters">
              <input id="search" type="search" placeholder="Search prompt, model, notes…">
              <label>Min rating
                <select id="rating-filter">
                  <option value="0">any</option>
                  <option value="1">★+</option>
                  <option value="2">★★+</option>
                  <option value="3">★★★+</option>
                  <option value="4">★★★★+</option>
                  <option value="5">★★★★★</option>
                </select>
              </label>
              <label><input type="checkbox" id="fav-only"> favorites only</label>
              <span id="counter" class="counter"></span>
            </div>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(c.title)}</title>
<style>
  :root {{
    --bg: {c.bg};
    --text: {c.text};
    --accent: {c.accent};
    --border: #2a2a38;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem 1rem;
    line-height: 1.5;
  }}
  header {{
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
  }}
  h1 {{
    font-size: 1.8rem;
    background: linear-gradient(135deg, var(--accent), #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}
  .filters {{
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    margin: 1.5rem auto;
    max-width: 1200px;
  }}
  .filters input, .filters select {{
    background: #1a1a25;
    color: var(--text);
    border: 1px solid var(--border);
    padding: 0.4rem 0.7rem;
    border-radius: 6px;
    font-size: 0.9rem;
  }}
  .filters input[type="search"] {{ flex: 1; min-width: 200px; }}
  .counter {{ margin-left: auto; color: #9999aa; font-size: 0.85rem; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat({c.columns}, 1fr);
    gap: 1rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .masonry {{
    column-count: {c.columns};
    column-gap: 1rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .masonry .card {{ break-inside: avoid; margin-bottom: 1rem; }}
  .list {{
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }}
  .list .card {{
    display: flex;
    gap: 1rem;
    align-items: center;
  }}
  .list .card img {{
    width: 96px;
    height: 96px;
    object-fit: cover;
    flex-shrink: 0;
  }}
  .list .meta {{ flex: 1; }}
  .timeline {{
    max-width: 800px;
    margin: 0 auto;
    position: relative;
  }}
  .timeline::before {{
    content: "";
    position: absolute;
    left: 80px;
    top: 0; bottom: 0;
    width: 2px;
    background: var(--border);
  }}
  .timeline .card {{
    display: flex;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
    align-items: flex-start;
  }}
  .timeline .ts {{
    width: 60px;
    text-align: right;
    color: #9999aa;
    font-size: 0.8rem;
    flex-shrink: 0;
    padding-top: 0.3rem;
  }}
  .timeline .thumb-wrap {{
    position: relative;
    z-index: 1;
  }}
  .timeline .thumb-wrap::before {{
    content: "";
    position: absolute;
    left: -16px;
    top: 50%;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--accent);
    transform: translateY(-50%);
  }}
  .timeline .card img {{
    width: 160px;
    height: 160px;
    object-fit: cover;
  }}

  .card {{
    background: #14141d;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    transition: transform 0.15s, border-color 0.15s;
  }}
  .card:hover {{
    transform: translateY(-2px);
    border-color: var(--accent);
  }}
  .card img {{
    width: 100%;
    height: auto;
    display: block;
    background: #1a1a25;
  }}
  .meta {{
    padding: 0.6rem 0.8rem;
    font-size: 0.85rem;
  }}
  .meta .prompt {{
    color: var(--text);
    margin-bottom: 0.4rem;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }}
  .meta .row {{
    color: #9999aa;
    font-size: 0.75rem;
    margin-top: 0.2rem;
  }}
  .stars {{ color: #facc15; letter-spacing: 1px; }}
  .fav {{ color: var(--accent); margin-right: 0.3rem; }}
  .tag {{
    display: inline-block;
    background: rgba(124, 92, 255, 0.15);
    color: var(--accent);
    padding: 0.1rem 0.5rem;
    border-radius: 8px;
    font-size: 0.7rem;
    margin-right: 0.2rem;
  }}
</style>
</head>
<body>
  <header>
    <h1>{html.escape(c.title)}</h1>
    <p style="color: #9999aa; font-size: 0.9rem; margin-top: 0.3rem;">
      {len(records)} images · {layout} layout
      {f" · project <code>{html.escape(c.project)}</code>" if c.project else ""}
    </p>
  </header>

  {filters}

  <div class="{layout}">
    {cards}
  </div>

  <script>{_FILTER_JS}</script>
</body>
</html>"""

    def _card(self, r: ImageRecord) -> str:
        c = self.config
        # Searchable text = all the user-visible metadata concatenated
        search_text = " ".join(filter(None, [
            r.prompt, r.negative_prompt or "", r.notes,
            r.model or "", r.sampler or "", " ".join(r.tags),
        ])).lower()

        img_src = self._img_src(r)

        stars = ""
        if c.show_rating and r.rating:
            stars = "★" * r.rating + "☆" * (5 - r.rating)
            stars = f'<div class="stars">{stars}</div>'

        fav = '<span class="fav">★</span>' if r.favorite and c.show_rating else ""

        meta_parts: list[str] = []
        if c.show_prompt and r.prompt:
            meta_parts.append(f'<div class="prompt">{html.escape(r.prompt[:300])}</div>')
        if c.show_rating:
            meta_parts.append(stars)
        if c.show_seed and r.seed is not None:
            meta_parts.append(f'<div class="row">seed: {r.seed} · model: {html.escape(r.model or "—")}</div>')
        elif c.show_metadata and r.model:
            meta_parts.append(f'<div class="row">{html.escape(r.model)} · {r.sampler or ""} {r.steps or ""} steps</div>')
        if c.show_tags and r.tags:
            tag_html = " ".join(f'<span class="tag">{html.escape(t)}</span>' for t in r.tags[:6])
            meta_parts.append(f'<div class="row" style="margin-top: 0.4rem;">{tag_html}</div>')

        meta = "\n".join(p for p in meta_parts if p)
        meta_html = f'<div class="meta">{fav}{meta}</div>' if meta else ""

        return f"""
    <div class="card"
         data-rating="{r.rating}"
         data-fav="{int(r.favorite)}"
         data-search="{html.escape(search_text)}">
      <img src="{html.escape(img_src)}" alt="{html.escape(r.prompt[:60])}" loading="lazy">
      {meta_html}
    </div>"""

    def _img_src(self, r: ImageRecord) -> str:
        if not r.path:
            return ""
        if self.config.embed_thumbnails:
            try:
                from PIL import Image
                with Image.open(r.path) as im:
                    im.thumbnail((self.config.thumbnail_max_px, self.config.thumbnail_max_px))
                    import io
                    buf = io.BytesIO()
                    mime, _ = mimetypes.guess_type(r.path)
                    mime = mime or "image/png"
                    fmt = mime.split("/")[1].upper().replace("JPEG", "JPEG")
                    im.save(buf, format=fmt, quality=80)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    return f"data:{mime};base64,{b64}"
            except Exception as exc:  # noqa: BLE001
                log.warning(f"thumbnail embed failed for {r.path}: {exc}")
        # file:// URL — works when the HTML is opened from the same machine
        return f"file://{r.path}"
