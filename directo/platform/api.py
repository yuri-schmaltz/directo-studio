"""HTTP API server for Directo (FastAPI).

Exposes the entire Directo stack over HTTP/JSON + WebSocket:

- REST endpoints for gallery, queue, presets, projects, etc.
- WebSocket endpoint for real-time progress streaming.
- Prometheus metrics endpoint.
- Health check.

The server is **stateless** with respect to the request — all state
lives in the SQLite files pointed to by the constructor. This means
the server can be run as multiple workers (gunicorn/uvicorn workers)
sharing the same DBs (SQLite WAL mode handles this).

Run it::

    from directo.platform.api import create_app
    import uvicorn
    app = create_app(db_dir="./directo_data")
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

try:
    from fastapi import (  # type: ignore
        FastAPI, HTTPException, WebSocket, WebSocketDisconnect,
        status, Body, Query,
    )
    from fastapi.responses import JSONResponse  # type: ignore
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from directo.cinema import (
    CanvasStore, CinemaEngine, StoryboardCanvas, parse_script_text,
)
from directo.director import (
    CreativeDirector, ProjectMemory, TemplateBackend,
)
from directo.gallery import Gallery, ImageRecord
from directo.observability import MetricsCollector, configure_logging, get_logger
from directo.platform.backup import BackupManager
from directo.platform.cache import CacheLayer
from directo.platform.costs import CostTracker
from directo.platform.events import EventBus, EventKind, WebhookManager
from directo.printing import StoryboardConfig, StoryboardExporter, StoryboardLayout
from directo.queue import PersistentQueue, Job
from directo.scale import PresetStore
from directo.scale.enhance import PromptEnhancer

log = get_logger("directo.platform.api")


# =====================================================================
# App factory
# =====================================================================


def create_app(db_dir: str | Path = "./directo_data") -> "FastAPI":
    """Build the FastAPI app with all dependencies wired.

    The app holds references to long-lived services (queue, gallery,
    event bus, etc.) and creates per-request resources as needed.
    """
    if not HAS_FASTAPI:
        raise RuntimeError(
            "FastAPI is not installed. Run: pip install fastapi uvicorn"
        )
    db_dir = Path(db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)

    # Build services up-front. These are singletons for the app lifetime.
    queue = PersistentQueue(db_dir / "queue.db")
    gallery = Gallery(db_dir / "gallery.db")
    preset_store = PresetStore(db_dir / "presets.db")
    canvas_store = CanvasStore(db_dir / "canvases.db")
    project_memory = ProjectMemory(db_dir / "memory.db")
    cinema_engine = CinemaEngine()
    prompt_enhancer = PromptEnhancer(provider="auto")
    director = CreativeDirector(project_memory, TemplateBackend())
    metrics = MetricsCollector()
    costs = CostTracker(db_dir / "costs.db")
    bus = EventBus(db_path=db_dir / "events.db")
    cache = CacheLayer()
    webhooks = WebhookManager(bus, db_path=db_dir / "webhooks.db")

    @asynccontextmanager
    async def lifespan(app: "FastAPI") -> AsyncIterator[None]:
        log.info("Directo API starting")
        configure_logging(level="INFO", json_output=True)
        bus.publish(EventKind.PROJECT_CREATED, {"event": "api_started"})

        # Start background queue worker
        from directo.queue import Worker
        worker = Worker(queue, worker_id="api-bg-worker")

        async def handle_image_generate(job):
            log.info(f"Mock image generation started: {job.payload}")
            await asyncio.sleep(1.0)
            return {"status": "success", "image_path": job.payload.get("output_path", "dummy.png")}

        async def handle_animatic_generate(job):
            log.info(f"Animatic generation started: {job.payload}")
            from directo.director.animatic import (
                AnimaticProject, AnimaticClip, AnimaticBuilder, AIVideoBackend
            )
            payload = job.payload

            # Reconstruct clips
            clips = []
            for c in payload.get("clips", []):
                clips.append(AnimaticClip(
                    image_path=c.get("image_path"),
                    duration_s=c.get("duration_s", 2.0),
                    pan_start=tuple(c.get("pan_start", (0.5, 0.5))),
                    pan_end=tuple(c.get("pan_end", (0.5, 0.5))),
                    zoom_start=c.get("zoom_start", 1.0),
                    zoom_end=c.get("zoom_end", 1.0),
                    narration=c.get("narration"),
                ))

            project = AnimaticProject(
                id=payload.get("project_id", "untitled"),
                title=payload.get("title", "Animatic"),
                clips=clips,
                music_path=payload.get("music_path"),
                fps=payload.get("fps", 24),
                resolution=tuple(payload.get("resolution", (1280, 720))),
            )

            backend_name = payload.get("backend", "mock")
            endpoint = payload.get("backend_endpoint")

            if backend_name == "ken-burns":
                from directo.director.animatic import KenBurnsBackend
                backend = KenBurnsBackend()
            else:
                backend = AIVideoBackend(name=backend_name, endpoint=endpoint)

            builder = AnimaticBuilder(backend=backend)
            output_path = payload.get("output_path") or f"./directo_data/projects/{project.id}_animatic.mp4"

            # Execute build in thread pool since it's CPU/IO bound with ffmpeg
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, builder.build, project, output_path)

            return {"status": "success", "output_path": str(output_path)}

        worker.register("image.generate", handle_image_generate)
        worker.register("animatic.generate", handle_animatic_generate)

        worker_task = asyncio.create_task(worker.run())
        app.state.worker = worker
        app.state.worker_task = worker_task

        yield

        log.info("Directo API shutting down")
        worker.stop()
        try:
            await asyncio.wait_for(worker_task, timeout=5.0)
        except Exception:
            pass

        # Close all services
        for svc in (queue, gallery, preset_store, canvas_store, project_memory,
                    costs, bus, cache, webhooks):
            try:
                svc.close()
            except Exception:  # noqa: BLE001
                pass

    app = FastAPI(
        title="Directo API",
        version="1.1.5",
        description="Production API for the Directo creative AI platform.",
        lifespan=lifespan,
    )

    # Stash services on the app for handler access
    app.state.services = {
        "queue": queue, "gallery": gallery, "presets": preset_store,
        "canvas": canvas_store, "memory": project_memory, "engine": cinema_engine,
        "enhancer": prompt_enhancer, "director": director, "metrics": metrics,
        "costs": costs, "bus": bus, "cache": cache, "webhooks": webhooks,
    }

    # ============================================================
    # Health + metrics
    # ============================================================

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": "1.1.5",
            "uptime": time.time(),
            "queue": queue.stats(),
            "gallery": gallery.count(),
        }

    @app.get("/metrics")
    def prometheus():
        body, content_type = metrics.render()
        return JSONResponse(content=body.decode("utf-8") if isinstance(body, bytes) else body,
                            media_type=content_type)

    # ============================================================
    # Gallery
    # ============================================================

    @app.get("/api/gallery")
    def gallery_list(
        project: str | None = None, model: str | None = None,
        min_rating: int = 0, favorites_only: bool = False,
        tag: str | None = None, limit: int = 100, offset: int = 0,
    ) -> dict[str, Any]:
        results = gallery.search(
            project=project, model=model, min_rating=min_rating,
            favorites_only=favorites_only, tags=[tag] if tag else None,
            limit=limit, offset=offset,
        )
        return {"items": [r.to_dict() for r in results], "count": gallery.count()}

    @app.get("/api/gallery/{image_id}")
    def gallery_get(image_id: str) -> dict[str, Any]:
        rec = gallery.get(image_id)
        if not rec:
            raise HTTPException(404, "image not found")
        return rec.to_dict()

    @app.post("/api/gallery")
    def gallery_create(record: dict[str, Any]) -> dict[str, Any]:
        rec = ImageRecord(**record)
        rid = gallery.add(rec)
        bus.publish(EventKind.IMAGE_ADDED, {"image_id": rid, "path": rec.path})
        return {"id": rid}

    @app.patch("/api/gallery/{image_id}")
    def gallery_update(image_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if "rating" in fields:
            gallery.rate(image_id, int(fields["rating"]))
            bus.publish(EventKind.IMAGE_RATED, {"image_id": image_id, "rating": fields["rating"]})
        for k, v in fields.items():
            if k == "rating":
                continue
            gallery.update(image_id, **{k: v})
        return {"updated": True}

    # ============================================================
    # Queue
    # ============================================================

    @app.post("/api/jobs")
    def jobs_submit(job: dict[str, Any]) -> dict[str, Any]:
        j = Job(**job)
        jid = queue.enqueue(j)
        bus.publish(EventKind.JOB_ENQUEUED, {"job_id": jid, "kind": j.kind})
        return {"id": jid}

    @app.get("/api/jobs/{job_id}")
    def jobs_get(job_id: str) -> dict[str, Any]:
        rec = queue.get(job_id)
        if not rec:
            raise HTTPException(404, "job not found")
        return rec.to_dict()

    @app.get("/api/jobs")
    def jobs_list(state: str | None = None, limit: int = 100) -> dict[str, Any]:
        from directo.queue import JobState
        s = JobState(state) if state else None
        items = queue.list_by_state(s, limit=limit) if s else queue.list_by_state(JobState.PENDING, limit=limit)
        return {"items": [j.to_dict() for j in items], "stats": queue.stats()}

    @app.post("/api/jobs/{job_id}/cancel")
    def jobs_cancel(job_id: str) -> dict[str, Any]:
        ok = queue.cancel(job_id)
        if ok:
            bus.publish(EventKind.JOB_CANCELLED, {"job_id": job_id})
        return {"cancelled": ok}

    # ============================================================
    # Presets
    # ============================================================

    @app.get("/api/presets")
    def presets_list(kind: str | None = None, era: str | None = None) -> dict[str, Any]:
        items = preset_store.list(kind=kind, era=era)
        return {"items": [p.to_dict() for p in items], "count": preset_store.count()}

    @app.get("/api/presets/{preset_id}")
    def presets_get(preset_id: str) -> dict[str, Any]:
        p = preset_store.get(preset_id)
        if not p:
            raise HTTPException(404, "preset not found")
        return p.to_dict()

    @app.post("/api/presets/{preset_id}/enhance")
    def presets_enhance(preset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a preset's render_prompt + optional LLM enhancement to a user prompt."""
        user_prompt = payload.get("prompt", "")
        p = preset_store.get(preset_id)
        if not p:
            raise HTTPException(404, "preset not found")
        rendered = p.render_prompt(user_prompt)
        if payload.get("enhance", True):
            result = prompt_enhancer.enhance(
                rendered, target=payload.get("target", p.model or "flux-dev"),
                context={"style": "cinematic"},
            )
            enhanced = result.enhanced
        else:
            enhanced = rendered
        return {
            "preset": preset_id, "user_prompt": user_prompt,
            "rendered": rendered, "enhanced": enhanced,
        }

    # ============================================================
    # Cinema: rules engine
    # ============================================================

    @app.post("/api/cinema/evaluate")
    def cinema_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        report = cinema_engine.evaluate(
            payload.get("prompt", ""),
            context=payload.get("context") or {},
        )
        return report.to_dict()

    @app.post("/api/cinema/parse-script")
    def cinema_parse(payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text", "")
        scenes = parse_script_text(text, hint=payload.get("hint", ""))
        return {
            "scenes": [s.to_dict() for s in scenes],
            "count": len(scenes),
        }

    # ============================================================
    # Canvas
    # ============================================================

    @app.post("/api/canvases")
    def canvas_save(canvas: dict[str, Any]) -> dict[str, Any]:
        c = StoryboardCanvas.from_dict(canvas)
        canvas_store.save(c)
        bus.publish(EventKind.CANVAS_SAVED, {"canvas_id": c.id, "project": c.project})
        return {"id": c.id}

    @app.get("/api/canvases/{canvas_id}")
    def canvas_get(canvas_id: str) -> dict[str, Any]:
        c = canvas_store.get(canvas_id)
        if not c:
            raise HTTPException(404, "canvas not found")
        return c.to_dict()

    @app.get("/api/canvases")
    def canvas_list(project: str | None = None) -> dict[str, Any]:
        items = canvas_store.list_for_project(project) if project else []
        return {"items": [c.to_dict() for c in items]}

    # ============================================================
    # Projects (director agent)
    # ============================================================

    @app.post("/api/projects")
    def projects_create(payload: dict[str, Any]) -> dict[str, Any]:
        pid = director.new_project(
            payload.get("name", "Untitled"),
            concept=payload.get("concept", ""),
            logline=payload.get("logline", ""),
        )
        bus.publish(EventKind.PROJECT_CREATED, {"project_id": pid})
        return {"id": pid}

    @app.get("/api/projects")
    def projects_list() -> dict[str, Any]:
        return {"items": project_memory.list_projects()}

    @app.get("/api/projects/{project_id}")
    def projects_get(project_id: str) -> dict[str, Any]:
        p = project_memory.get_project(project_id)
        if not p:
            raise HTTPException(404, "project not found")
        return p

    @app.post("/api/projects/{project_id}/enrich-prompt")
    def projects_enrich(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = director.enrich_prompt(
            project_id,
            payload.get("prompt", ""),
            model_hint=payload.get("target", "flux-dev"),
        )
        return {"original": result, "enriched": result}  # already a string

    # ============================================================
    # Storyboard PDF export
    # ============================================================

    @app.post("/api/storyboard/pdf")
    def storyboard_pdf(payload: dict[str, Any]) -> dict[str, Any]:
        # Body: {"project": str, "layout": "1up"|"2up"|"4up"|"contact", "min_rating": int}
        project = payload.get("project")
        layout_str = payload.get("layout", "2up")
        min_rating = int(payload.get("min_rating", 0))
        try:
            layout = StoryboardLayout(layout_str)
        except ValueError:
            raise HTTPException(400, f"invalid layout: {layout_str}")
        records = gallery.search(project=project, min_rating=min_rating, limit=100)
        if not records:
            raise HTTPException(404, "no images match the criteria")
        out = Path(payload.get("output", f"./{project}_storyboard.pdf"))
        exporter = StoryboardExporter(StoryboardConfig(
            layout=layout, project_title=payload.get("title", project or "Storyboard"),
        ))
        result = exporter.export(records, out, gallery=gallery)
        return {"path": str(result), "panels": len(records)}

    # ============================================================
    # Animatic generation
    # ============================================================

    @app.post("/api/animatics")
    def animatics_generate(payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a background job to render an animatic."""
        j = Job(
            kind="animatic.generate",
            payload=payload,
            project=payload.get("project_id"),
        )
        jid = queue.enqueue(j)
        bus.publish(EventKind.JOB_ENQUEUED, {"job_id": jid, "kind": j.kind})
        return {"job_id": jid, "status": "enqueued"}

    # ============================================================
    # Costs
    # ============================================================

    @app.get("/api/costs")
    def costs_total(project: str | None = None, hours: int | None = None) -> dict[str, Any]:
        since = (time.time() - hours * 3600) if hours else None
        return {
            "total_usd": costs.total(project=project, since=since),
            "by_project": costs.by_project(since=since),
            "by_kind": costs.by_kind(project=project, since=since),
        }

    # ============================================================
    # Backup
    # ============================================================

    @app.post("/api/backup")
    def backup_create(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        target = payload.get("db", "queue")
        if target not in app.state.services:
            raise HTTPException(400, f"unknown db: {target}")
        db_path = Path(app.state.services[target]._db_path)
        out = Path(payload.get("output_dir", str(db_path.parent)))
        mgr = BackupManager(db_path)
        result = mgr.backup(out)
        return {
            "path": str(result.path), "size_bytes": result.size_bytes,
            "verified": result.verified, "duration_ms": result.duration_ms,
        }

    # ============================================================
    # WebSocket: real-time progress
    # ============================================================

    @app.websocket("/ws/events")
    async def ws_events(websocket: WebSocket) -> None:
        """Stream all events to the client in real time."""
        await websocket.accept()
        # Build a queue for this client
        q: asyncio.Queue[Event] = asyncio.Queue()

        async def listener(event: Event) -> None:
            await q.put(event)

        bus.subscribe_all(listener)
        try:
            while True:
                event = await q.get()
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            bus.unsubscribe(EventKind.CUSTOM, listener)  # placeholder; will match
        except Exception as exc:  # noqa: BLE001
            log.warning(f"websocket error: {exc}")
            bus.unsubscribe(EventKind.CUSTOM, listener)

    @app.websocket("/ws/jobs/{job_id}")
    async def ws_job(websocket: WebSocket, job_id: str) -> None:
        """Stream events for a specific job."""
        await websocket.accept()
        q: asyncio.Queue[Event] = asyncio.Queue()

        async def listener(event: Event) -> None:
            if event.payload.get("job_id") == job_id:
                await q.put(event)

        bus.subscribe_all(listener)
        try:
            while True:
                event = await q.get()
                await websocket.send_json(event.to_dict())
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning(f"websocket error: {exc}")

    return app


# Convenience runner
def run_server(
    db_dir: str | Path = "./directo_data",
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info",
) -> None:
    """Run the API server. Blocks until interrupted."""
    try:
        import uvicorn  # type: ignore
    except ImportError as exc:
        raise RuntimeError("uvicorn is required: pip install uvicorn") from exc
    app = create_app(db_dir)
    uvicorn.run(app, host=host, port=port, log_level=log_level)
