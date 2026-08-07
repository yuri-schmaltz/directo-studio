"""End-to-end demo of the Phase 0 Directo core.

This script exercises every module: logs (with correlation IDs), the
encrypted vault, the persistent queue (with retries and a worker that
sometimes fails), the gallery (with rating, dedup, search), and a
storyboard PDF export.

Run it:
    python examples/demo.py
"""

from __future__ import annotations

import asyncio
import random
import sys
import tempfile
import time
from pathlib import Path

# Make the parent package importable when running this script directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from directo import (
    CredentialVault,
    Gallery,
    ImageRecord,
    Job,
    JobState,
    MetricsCollector,
    PersistentQueue,
    Worker,
    bind_context,
    configure_logging,
    correlation_id_var,
    get_logger,
)
from directo.printing import StoryboardConfig, StoryboardExporter, StoryboardLayout


def make_placeholder_png(path: Path, label: str, color: tuple[int, int, int]) -> None:
    """Generate a small colored PNG to simulate a generated image."""
    img = Image.new("RGB", (768, 512), color=color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
        )
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 30), label, fill=(255, 255, 255), font=font)
    draw.rectangle([(0, 0), (767, 511)], outline=(255, 255, 255), width=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", dpi=(150, 150))


# ----------------- Handlers -----------------

log = get_logger("directo.demo")


async def handle_image_generation(job: Job) -> dict:
    """Fake image generation: writes a placeholder PNG and reports a phash."""
    project = job.payload.get("project", "default")
    seed = job.payload.get("seed", random.randint(0, 999_999))
    prompt = job.payload.get("prompt", "")

    # Simulate work
    await asyncio.sleep(0.05)

    # 20% failure rate to exercise retry logic
    if random.random() < 0.2:
        raise RuntimeError(f"simulated GPU OOM on seed {seed}")

    out_dir = Path("./demo_output") / project
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"frame_{seed}.png"
    make_placeholder_png(out_path, prompt[:40], color=(
        random.randint(40, 200), random.randint(40, 200), random.randint(40, 200),
    ))

    # Compute perceptual hash
    import imagehash
    phash = str(imagehash.phash(Image.open(out_path)))

    return {
        "path": str(out_path),
        "seed": seed,
        "phash": phash,
        "width": 768,
        "height": 512,
    }


async def handle_prompt_enhance(job: Job) -> dict:
    """Fake LLM prompt enhancement."""
    await asyncio.sleep(0.02)
    raw = job.payload.get("prompt", "")
    return {"enhanced": f"cinematic masterpiece, {raw}, volumetric lighting, 8k"}


# ----------------- Demo -----------------

async def main() -> None:
    configure_logging(level="INFO", json_output=False)
    log.info("=" * 70)
    log.info("Directo Phase 0 Demo")
    log.info("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        queue_db = tmp / "queue.db"
        gallery_db = tmp / "gallery.db"
        vault_db = tmp / "vault.db"
        img_dir = tmp / "images"
        img_dir.mkdir()

        # ----- 1. Vault -----
        log.info("\n[1/5] Vault — encrypted credentials")
        with CredentialVault.from_passphrase("correct horse battery staple", db_path=vault_db) as v:
            v.set("openai_api_key", "sk-fake-abc123def456")
            v.set("anthropic_api_key", "sk-ant-fake-xyz789")
            log.info(f"stored credentials: {v.list_names()}")
            log.info(f"audit log entries: {len(v.get_audit_log())}")
            log.info(f"openai key decrypted: {v.get('openai_api_key')[:10]}...")
            v.rotate_key("new-better-passphrase")
            log.info("rotated master key; openai key still readable:")
            log.info(f"openai key after rotate: {v.get('openai_api_key')[:10]}...")

        # ----- 2. Queue + Worker -----
        log.info("\n[2/5] Persistent queue + worker (with simulated failures + retries)")
        queue = PersistentQueue(queue_db, stale_timeout_seconds=10.0)
        worker = Worker(queue, worker_id="demo-worker", poll_interval=0.1)
        worker.register("image.generate", handle_image_generation)
        worker.register("prompt.enhance", handle_prompt_enhance)

        # Enqueue 20 image jobs
        for i in range(20):
            correlation_id_var.set(f"job-batch-{i // 5:02d}")
            with bind_context(batch=i // 5):
                for j in range(5):
                    job = Job(
                        kind="image.generate",
                        payload={
                            "project": "demo_film",
                            "seed": 1000 + i * 5 + j,
                            "prompt": f"a cinematic {random.choice(['cyberpunk', 'film noir', 'fantasy'])} scene, shot {i*5+j}",
                        },
                        project="demo_film",
                        priority=random.randint(1, 200),
                    )
                    queue.enqueue(job)
            correlation_id_var.set(None)

        # Enqueue 5 prompt enhancements
        for k in range(5):
            queue.enqueue(Job(kind="prompt.enhance", payload={"prompt": f"a dragon in the clouds {k}"}))

        # Start the worker in the background
        worker_task = asyncio.create_task(worker.run())
        # Let it drain
        await asyncio.sleep(2.0)
        worker.stop()
        await worker_task

        stats = queue.stats()
        log.info(f"queue stats: {stats}")
        log.info(f"DLQ size: {queue.depth(JobState.FAILED)}")

        # ----- 3. Gallery -----
        log.info("\n[3/5] Gallery — add generated images, rate, tag, search, dedup")
        gallery = Gallery(gallery_db, image_root=img_dir)

        completed = queue.list_by_state(JobState.COMPLETED, limit=200)
        for job in completed:
            res = job.result or {}
            path = res.get("path")
            if not path or not Path(path).exists():
                continue
            rec = ImageRecord(
                path=path,
                job_id=job.id,
                project=job.project,
                prompt=job.payload.get("prompt", ""),
                model="flux-dev",
                sampler="euler",
                scheduler="normal",
                cfg_scale=4.5,
                steps=28,
                seed=res.get("seed"),
                width=res.get("width"),
                height=res.get("height"),
                rating=random.randint(0, 5),
                color_tag=random.choice([None, None, "blue", "green", "yellow"]),
                tags=random.sample(["hero", "establishing", "close-up", "wide", "tracking"], k=2),
                phash=res.get("phash"),
            )
            gallery.add(rec)

        log.info(f"gallery has {gallery.count()} images")
        log.info(f"stats: {gallery.stats()}")

        # Search
        top = gallery.search(text="dragon", min_rating=3, limit=5)
        log.info(f"search 'dragon' (rating>=3): {len(top)} hits")
        favs = gallery.list_favorites(limit=5)
        log.info(f"favorites: {len(favs)}")

        # Dedup
        if completed and completed[0].result:
            sample_phash = completed[0].result["phash"]
            dups = gallery.find_duplicates(sample_phash, max_hamming=2)
            log.info(f"dedup test (hamming<=2): {len(dups)} matches for {sample_phash}")

        # ----- 4. Metrics -----
        log.info("\n[4/5] Metrics snapshot")
        metrics = MetricsCollector()
        body, content_type = metrics.render()
        log.info(f"prometheus body size: {len(body)} bytes ({content_type})")
        # Show the first few non-comment lines
        lines = [
            l for l in body.decode().splitlines()
            if not l.startswith("#") and "directo_" in l
        ][:5]
        for line in lines:
            log.info(f"  {line}")

        # ----- 5. Storyboard PDF -----
        log.info("\n[5/5] Storyboard PDF export")
        output_pdf = Path("./demo_storyboard.pdf")
        top_rated = gallery.list_top_rated(limit=8)
        if top_rated:
            exporter = StoryboardExporter(StoryboardConfig(
                layout=StoryboardLayout.TWO_UP,
                project_title="Demo Film — Rough Cut",
            ))
            pdf_path = exporter.export(top_rated, output_pdf, gallery=gallery)
            log.info(f"PDF written: {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
        else:
            log.warning("no top-rated images to export")

        # ----- 6. Watchdog demo -----
        log.info("\n[6/6] Watchdog — reap stale jobs")
        # Manually mark a job as running with old heartbeat
        if completed:
            stale_id = completed[0].id
            with queue._lock:
                queue._conn.execute(
                    "UPDATE jobs SET state = ?, heartbeat_at = ? WHERE id = ?",
                    (JobState.RUNNING.value, time.time() - 60, stale_id),
                )
            reaped = queue.reap_stale()
            log.info(f"reaped {reaped} stale job(s)")

        queue.close()
        gallery.close()

    log.info("\n✓ demo complete")


if __name__ == "__main__":
    asyncio.run(main())
