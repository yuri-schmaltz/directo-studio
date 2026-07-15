"""Phase 1 demo — the creative primitives.

Demonstrates the four new modules:

- ``VariantStore`` + ``VariantSet`` — the 4-options pattern.
- ``ReferenceLibrary`` — style/character/composition references
  with similarity search.
- ``ImageHistory`` — per-job history with restore.
- ``GalleryView`` — multi-view HTML renderer (grid / masonry / list /
  timeline).

Run:
    python examples/demo_phase1.py
"""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

# Make the parent package importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from directo import (
    Gallery,
    ImageRecord,
    configure_logging,
    get_logger,
)
from directo.creative import (
    GalleryView,
    GenerationStrategy,
    ImageHistory,
    ReferenceKind,
    ReferenceLibrary,
    Variant,
    VariantLock,
    VariantSet,
    VariantStore,
    ViewLayout,
    plan_seeds,
)
from directo.printing import StoryboardConfig, StoryboardExporter, StoryboardLayout


def make_placeholder_png(path: Path, label: str, color: tuple[int, int, int]) -> None:
    img = Image.new("RGB", (640, 360), color=color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
        )
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 20), label[:40], fill=(255, 255, 255), font=font)
    draw.rectangle([(0, 0), (639, 359)], outline=(255, 255, 255), width=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def main() -> None:
    configure_logging(level="INFO", json_output=False)
    log = get_logger("directo.demo")
    log.info("=" * 70)
    log.info("Directo Phase 1 — Creative Foundation Demo")
    log.info("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gallery_db = tmp / "gallery.db"
        history_db = tmp / "history.db"
        refs_db = tmp / "refs.db"
        variants_db = tmp / "variants.db"
        img_dir = tmp / "images"
        img_dir.mkdir()

        # ============================================================
        # 1. Build a small gallery of generated images
        # ============================================================
        log.info("\n[1/5] Building sample gallery (10 images across 2 projects)")
        gallery = Gallery(gallery_db, image_root=img_dir)
        for i in range(10):
            color = (
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200),
            )
            path = img_dir / f"shot_{i:02d}.png"
            make_placeholder_png(path, f"shot {i}", color)
            gallery.add(ImageRecord(
                path=str(path),
                project="demo_film" if i < 6 else "demo_short",
                prompt=f"a cinematic {random.choice(['establishing', 'close-up', 'wide'])} shot, frame {i}",
                model="flux-dev",
                seed=1000 + i,
                rating=random.randint(0, 5),
                color_tag=random.choice([None, None, "blue", "green", "yellow"]),
                tags=random.sample(["hero", "establishing", "close-up", "wide", "tracking"], k=2),
            ))
        log.info(f"gallery has {gallery.count()} images, stats: {gallery.stats()}")

        # ============================================================
        # 2. Variant sets — the 4-options pattern
        # ============================================================
        log.info("\n[2/5] Variant sets — 4-options pattern")
        vstore = VariantStore(variants_db)
        all_images = gallery.search(limit=100)
        vs1 = VariantSet(
            id="vs-scene01",
            decision_key="scene_01_main_shot",
            project="demo_film",
            prompt_template="a dragon perches on a cliff at dawn, cinematic",
            strategy=GenerationStrategy.SEED_VARIATION,
            variants=[
                Variant(index=0, image_id=all_images[0].id, seed=1000),
                Variant(index=1, image_id=all_images[1].id, seed=1001),
                Variant(index=2, image_id=all_images[2].id, seed=1002),
                Variant(index=3, image_id=all_images[3].id, seed=1003),
            ],
        )
        vstore.create(vs1)
        log.info(f"created '{vs1.decision_key}' with 4 variants, planned seeds: {plan_seeds(1000, 4)}")

        # Lock variant 2 as the winner
        vs1.lock_variant(2, locked_by="director")
        vstore.save(vs1)
        log.info(f"locked variant 2 as the chosen shot (by director)")

        # Open variant set (no decision yet)
        vs2 = VariantSet(
            id="vs-scene02",
            decision_key="scene_02_alt_angle",
            project="demo_film",
            prompt_template="low angle dragon shot, dramatic",
            variants=[
                Variant(index=0, image_id=all_images[4].id, seed=1004),
                Variant(index=1, image_id=all_images[5].id, seed=1005),
            ],
        )
        vstore.create(vs2)
        log.info(f"created '{vs2.decision_key}' (still open, awaiting decision)")

        log.info(f"variant stats: {vstore.stats(project='demo_film')}")

        # ============================================================
        # 3. Reference library with similarity search
        # ============================================================
        log.info("\n[3/5] Reference library — style & character references")
        refs_dir = img_dir / "refs"
        refs_dir.mkdir()
        # 5 reference images with very different colors
        refs_meta = [
            ("warm_sunset.png", (220, 100, 50), ReferenceKind.STYLE, "warm sunset"),
            ("cold_winter.png", (50, 100, 220), ReferenceKind.STYLE, "cold winter"),
            ("hero_face.png", (180, 150, 120), ReferenceKind.CHARACTER, "hero"),
            ("villa_face.png", (140, 110, 90), ReferenceKind.CHARACTER, "villa"),
            ("low_angle.png", (100, 100, 100), ReferenceKind.COMPOSITION, "low angle"),
        ]
        for fname, color, kind, title in refs_meta:
            p = refs_dir / fname
            make_placeholder_png(p, title, color)

        lib = ReferenceLibrary(refs_db, storage_dir=refs_dir)
        for fname, color, kind, title in refs_meta:
            lib.add(refs_dir / fname, kind=kind, title=title, tags=[title.split()[0]])
        log.info(f"library has {lib.count()} refs, stats: {lib.stats()}")

        # Search by an image similar to "warm_sunset" (similar red-ish color)
        query_img = refs_dir / "query_warm.png"
        make_placeholder_png(query_img, "warm", (210, 110, 60))
        matches = lib.find_similar_to_image(str(query_img), top_k=3)
        log.info(f"search for warm tones — top 3:")
        for ref, score in matches:
            log.info(f"  {ref.title:20s} score={score:.3f}")

        lib.increment_use_count(matches[0][0].id)
        log.info(f"marked '{matches[0][0].title}' as used (use_count={matches[0][0].use_count + 1})")

        # ============================================================
        # 4. Image history with restore
        # ============================================================
        log.info("\n[4/5] Image history — record iterations, then restore")
        history = ImageHistory(history_db)
        some_images = all_images[:3]
        # Simulate: the same job ran 3 times with different seeds
        for i, img in enumerate(some_images, 1):
            history.record(
                job_id="job-001",
                image_id=img.id,
                params={"seed": 1000 + i, "cfg": 7.0, "steps": 28},
                note=f"iteration {i}",
            )
        entries = history.get_job_history("job-001")
        log.info(f"job-001 has {len(entries)} iterations:")
        for e in entries:
            marker = " ← current" if e.is_current else ""
            log.info(f"  iter {e.iteration}: image {e.image_id[:8]}... seed={e.params.get('seed')}{marker}")

        # Restore iteration 1
        log.info("restoring iteration 1...")
        new_id = history.restore("job-001", 1, gallery)
        log.info(f"restored as new gallery record {new_id[:8]}...")

        # Show diff between two iterations
        d = history.diff("job-001", 1, 2)
        log.info(f"diff(1, 2): changed params = {list(d['param_diff'].keys())}")

        # ============================================================
        # 5. Multi-view HTML gallery export
        # ============================================================
        log.info("\n[5/5] Multi-view HTML gallery export")
        output_dir = Path("./demo_phase1_output")
        output_dir.mkdir(exist_ok=True)

        for layout in ViewLayout:
            out = output_dir / f"gallery_{layout.value}.html"
            GalleryView().render(
                gallery.search(project="demo_film", limit=20),
                out,
                layout=layout,
            )
            log.info(f"  {layout.value:10s} → {out} ({out.stat().st_size:,} bytes)")

        # Also a storyboard PDF for the top-rated of demo_film
        top = gallery.search(project="demo_film", min_rating=4, limit=4)
        if top:
            pdf_path = output_dir / "demo_film_storyboard.pdf"
            StoryboardExporter(StoryboardConfig(
                layout=StoryboardLayout.TWO_UP,
                project_title="Demo Film — Phase 1 Cut",
            )).export(top, pdf_path, gallery=gallery)
            log.info(f"  storyboard → {pdf_path} ({pdf_path.stat().st_size:,} bytes)")

        # Cleanup
        vstore.close()
        history.close()
        lib.close()
        gallery.close()

    log.info("\n✓ Phase 1 demo complete")
    log.info("  Open demo_phase1_output/gallery_*.html in a browser to see the views.")


if __name__ == "__main__":
    main()
