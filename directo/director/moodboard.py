"""Moodboard auto-generator.

Drop 5-10 reference images; the builder:

1. Extracts a unified palette (k-means on pixel colors).
2. Computes an aggregate embedding (averaging individual embeddings
   from :class:`directo.creative.references.ReferenceLibrary`).
3. Generates a mood description (LLM- or template-based).
4. Renders a single "mood anchor" image — a small collage with the
   palette and keywords baked in.

The resulting :class:`Moodboard` is meant to be saved as a "mood
anchor" of a project. When the project generates new images, this
anchor can be auto-injected into prompts to keep the tone consistent.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from directo.observability import get_logger

log = get_logger("directo.director.moodboard")


# =====================================================================
# Domain
# =====================================================================


@dataclass
class MoodAnchor:
    """A single piece of mood metadata extracted from a reference image."""

    image_path: str
    palette: list[str] = field(default_factory=list)   # hex colors
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class Moodboard:
    """A complete moodboard assembled from references."""

    id: str
    title: str = ""
    palette: list[str] = field(default_factory=list)      # dominant hex colors, sorted by prevalence
    keywords: list[str] = field(default_factory=list)     # aggregate keywords
    description: str = ""
    anchor_image_path: str | None = None                 # generated collage
    source_refs: list[str] = field(default_factory=list) # paths
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# =====================================================================
# Builder
# =====================================================================


class MoodboardBuilder:
    """Build a :class:`Moodboard` from a set of reference images.

    Optional ``embedder`` is any object with an ``embed(path) -> list[float]``
    method. If not provided, the builder skips embedding and the
    moodboard just has palette + keywords.
    """

    def __init__(self, embedder: Any | None = None) -> None:
        self._embedder = embedder

    # ----------------- Public API -----------------

    def build(
        self,
        image_paths: Iterable[str | Path],
        *,
        title: str = "",
        description: str = "",
        output_dir: str | Path | None = None,
        num_palette_colors: int = 6,
        num_keywords: int = 8,
    ) -> Moodboard:
        """Build a moodboard from a list of reference images.

        Steps:
        1. Extract per-image palette + dominant colors.
        2. Aggregate palettes (weighted by image weight).
        3. Average the embeddings (if an embedder is available).
        4. Generate keywords via simple heuristics.
        5. Render an anchor collage (PIL).
        """
        paths = [Path(p) for p in image_paths]
        if not paths:
            raise ValueError("at least one image is required")
        anchors: list[MoodAnchor] = []
        embeddings: list[list[float]] = []
        for p in paths:
            if not p.exists():
                log.warning(f"skip missing ref: {p}")
                continue
            palette = _extract_palette(p, k=num_palette_colors)
            keywords = _heuristic_keywords(p)
            anchors.append(MoodAnchor(
                image_path=str(p), palette=palette, keywords=keywords, weight=1.0,
            ))
            if self._embedder is not None:
                try:
                    embeddings.append(self._embedder.embed(str(p)))
                except Exception as exc:  # noqa: BLE001
                    log.warning(f"embed failed for {p}: {exc}")

        if not anchors:
            raise RuntimeError("no usable images to build moodboard")

        agg_palette = _aggregate_palettes(anchors, k=num_palette_colors)
        agg_keywords = _aggregate_keywords(anchors, top_n=num_keywords)
        agg_embedding = _average_embeddings(embeddings) if embeddings else None

        # Render the anchor collage
        anchor_path: str | None = None
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            anchor_path = str(output_dir / f"moodboard-{uuid.uuid4().hex[:8]}.png")
            _render_collage(anchors, agg_palette, agg_keywords, anchor_path)

        return Moodboard(
            id=f"mb-{uuid.uuid4().hex[:10]}",
            title=title,
            palette=agg_palette,
            keywords=agg_keywords,
            description=description or _compose_description(agg_keywords, agg_palette),
            anchor_image_path=anchor_path,
            source_refs=[a.image_path for a in anchors],
            embedding=agg_embedding,
        )


# =====================================================================
# Implementation details
# =====================================================================


def _extract_palette(image_path: Path, k: int = 6) -> list[str]:
    """Extract a palette of ``k`` hex colors via k-means on pixel colors."""
    from PIL import Image
    try:
        from sklearn.cluster import KMeans  # type: ignore
    except ImportError:
        return _extract_palette_simple(image_path, k)

    img = Image.open(image_path).convert("RGB").resize((128, 128))
    pixels = list(img.getdata())
    if len(pixels) < k:
        return _extract_palette_simple(image_path, k)
    km = KMeans(n_clusters=k, n_init=3, random_state=0)
    labels = km.fit_predict(pixels)
    centers = km.cluster_centers_.astype(int)
    # Count pixels per cluster label
    counts: dict[int, int] = {}
    for label in labels:
        counts[int(label)] = counts.get(int(label), 0) + 1
    # Pair each center index with its count (default 0)
    pairs = [(i, counts.get(i, 0)) for i in range(len(centers))]
    pairs.sort(key=lambda p: -p[1])
    return ["#{:02x}{:02x}{:02x}".format(*centers[i]) for i, _ in pairs]


def _extract_palette_simple(image_path: Path, k: int = 6) -> list[str]:
    """Fallback palette: quantize the image to k colors via PIL."""
    from PIL import Image
    img = Image.open(image_path).convert("RGB").resize((128, 128))
    q = img.quantize(colors=k, method=2)
    palette = q.getpalette() or []
    colors: list[str] = []
    for i in range(k):
        r, g, b = palette[i * 3 : i * 3 + 3]
        colors.append(f"#{r:02x}{g:02x}{b:02x}")
    return colors


def _aggregate_palettes(anchors: list[MoodAnchor], k: int = 6) -> list[str]:
    """Merge all per-image palettes into a single dominant-K palette."""
    from collections import Counter
    counter: Counter[str] = Counter()
    for a in anchors:
        for color in a.palette:
            counter[color] += 1
    return [c for c, _ in counter.most_common(k)]


def _aggregate_keywords(anchors: list[MoodAnchor], top_n: int = 8) -> list[str]:
    from collections import Counter
    counter: Counter[str] = Counter()
    for a in anchors:
        for kw in a.keywords:
            counter[kw.lower()] += 1
    return [k for k, _ in counter.most_common(top_n)]


def _average_embeddings(embeddings: list[list[float]]) -> list[float] | None:
    if not embeddings:
        return None
    dim = len(embeddings[0])
    sums = [0.0] * dim
    for emb in embeddings:
        for i, v in enumerate(emb):
            sums[i] += v
    avg = [s / len(embeddings) for s in sums]
    # L2 normalize
    norm = sum(x * x for x in avg) ** 0.5 or 1.0
    return [x / norm for x in avg]


def _heuristic_keywords(image_path: Path) -> list[str]:
    """Cheap heuristic keywords based on color distribution + filename."""
    from PIL import Image
    img = Image.open(image_path).convert("RGB").resize((64, 64))
    pixels = list(img.getdata())
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)
    kws: list[str] = []
    if r > g and r > b:
        kws.append("warm")
    elif b > r and b > g:
        kws.append("cool")
    if r > 180:
        kws.append("bright")
    elif r < 60:
        kws.append("dark")
    if g > 150:
        kws.append("natural")
    # Filename hints
    fname = image_path.stem.lower()
    for hint in ("sunset", "night", "winter", "summer", "forest", "city", "space", "underwater"):
        if hint in fname:
            kws.append(hint)
    if not kws:
        kws.append("neutral")
    return list(dict.fromkeys(kws))  # dedup preserving order


def _compose_description(keywords: list[str], palette: list[str]) -> str:
    """Build a short prose description of the moodboard."""
    if not keywords:
        return ""
    pal_str = ", ".join(palette[:4]) if palette else ""
    if pal_str:
        return (
            f"A mood anchored on {', '.join(keywords[:4])}. "
            f"Palette: {pal_str}."
        )
    return f"A mood anchored on {', '.join(keywords[:4])}."


def _render_collage(
    anchors: list[MoodAnchor],
    palette: list[str],
    keywords: list[str],
    output_path: str,
) -> None:
    """Render a small mood anchor image with palette + keywords."""
    from PIL import Image, ImageDraw, ImageFont

    # 6x4 grid of thumbs + bottom strip with palette
    cols, rows = 6, 4
    thumb_w, thumb_h = 200, 130
    canvas_w = cols * thumb_w
    canvas_h = rows * thumb_h + 100  # extra for palette + keywords
    img = Image.new("RGB", (canvas_w, canvas_h), color=(10, 10, 15))
    draw = ImageDraw.Draw(img)

    # Try to load a font
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18
        )
        small_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
        )
    except OSError:
        font = ImageFont.load_default()
        small_font = font

    # Paste thumbs
    for i, anchor in enumerate(anchors[: cols * rows]):
        col = i % cols
        row = i // cols
        try:
            src = Image.open(anchor.image_path).convert("RGB")
            src.thumbnail((thumb_w, thumb_h))
            img.paste(src, (col * thumb_w, row * thumb_h))
        except Exception:
            pass

    # Bottom strip: palette swatches
    strip_y = rows * thumb_h
    if palette:
        sw = canvas_w // max(1, len(palette))
        for i, color in enumerate(palette):
            try:
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                draw.rectangle([(i * sw, strip_y), ((i + 1) * sw, strip_y + 60)], fill=(r, g, b))
            except (ValueError, IndexError):
                pass

    # Keywords
    if keywords:
        kw_text = " · ".join(keywords)
        draw.text((20, strip_y + 70), kw_text, fill=(232, 232, 240), font=small_font)

    img.save(output_path, "PNG", quality=92)
    log.info(f"moodboard anchor rendered: {output_path}")
