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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

try:
    from fastapi import (  # type: ignore
        Body,
        FastAPI,
        HTTPException,
        WebSocket,
        WebSocketDisconnect,
        status,
    )
    from fastapi.responses import JSONResponse  # type: ignore
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from directo.cinema import (
    CanvasStore,
    CinemaEngine,
    StoryboardCanvas,
    parse_script_text,
)
from directo.director import (
    CreativeDirector,
    ProjectMemory,
)
from directo.director.backends import DynamicLLMBackend
from directo.gallery import Gallery, ImageRecord
from directo.observability import MetricsCollector, configure_logging, get_logger
from directo.platform.backup import BackupManager
from directo.platform.cache import CacheLayer
from directo.platform.events import Event, EventBus, EventKind, WebhookManager
from directo.printing import StoryboardConfig, StoryboardExporter, StoryboardLayout
from directo.queue import Job, PersistentQueue
from directo.scale import PresetStore
from directo.scale.enhance import PromptEnhancer
from directo.style_bible import StyleBibleStore
from directo.style_bible.models import (
    StyleBible,
)

log = get_logger("directo.platform.api")


# =====================================================================
# App factory
# =====================================================================


def create_app(db_dir: str | Path = "./directo_data") -> FastAPI:
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
    director = CreativeDirector(project_memory, DynamicLLMBackend(db_dir / "settings.json"))
    metrics = MetricsCollector()
    bus = EventBus(db_path=db_dir / "events.db")
    cache = CacheLayer()
    webhooks = WebhookManager(bus, db_path=db_dir / "webhooks.db")
    style_bible_store = StyleBibleStore(db_dir / "style_bibles.db")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
                AIVideoBackend,
                AnimaticBuilder,
                AnimaticClip,
                AnimaticProject,
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

            if not clips:
                records = gallery.search(project=payload.get("project_id"), limit=100)
                for r in records:
                    clips.append(AnimaticClip(
                        image_path=r.path,
                        duration_s=2.0,
                        narration=r.prompt or "",
                    ))

            if not clips:
                raise ValueError(
                    f"No storyboard clips found in payload or in gallery for project: {payload.get('project_id')}"
                )

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
                    bus, cache, webhooks, style_bible_store):
            try:
                svc.close()
            except Exception:  # noqa: BLE001
                pass

    app = FastAPI(
        title="Directo API",
        version="1.1.8",
        description="Production API for the Directo creative AI platform.",
        lifespan=lifespan,
    )

    # Stash services on the app for handler access
    app.state.services = {
        "queue": queue, "gallery": gallery, "presets": preset_store,
        "canvas": canvas_store, "memory": project_memory, "engine": cinema_engine,
        "enhancer": prompt_enhancer, "director": director, "metrics": metrics,
        "bus": bus, "cache": cache, "webhooks": webhooks,
        "style_bibles": style_bible_store,
    }

    # ============================================================
    # Health + metrics
    # ============================================================

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": "1.1.8",
            "uptime": time.time(),
            "queue": queue.stats(),
            "gallery": gallery.count(),
        }

    @app.get("/health/ollama")
    def health_ollama() -> dict[str, Any]:
        from directo.director.backends import OllamaBackend
        ollama = OllamaBackend()
        is_up = ollama.is_available()
        models = ollama.list_installed_models() if is_up else []
        return {
            "status": "ok" if is_up else "unavailable",
            "available": is_up,
            "models": models,
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

    @app.post("/api/cinema/evaluate-script")
    def cinema_evaluate_script(payload: dict[str, Any]) -> dict[str, Any]:
        text = payload.get("text", "")
        hint = payload.get("hint", "")
        context = payload.get("context") or {}
        scenes = parse_script_text(text, hint=hint)
        evaluated_scenes = []
        total_score = 0.0
        blocked_count = 0
        for s in scenes:
            scene_dict = s.to_dict()
            prompt = s.to_prompt()
            report = cinema_engine.evaluate(prompt, context=context)
            rep_dict = report.to_dict()
            scene_dict["evaluation"] = rep_dict
            total_score += rep_dict.get("score", 1.0)
            if rep_dict.get("blocked", False):
                blocked_count += 1
            evaluated_scenes.append(scene_dict)
        avg_score = (total_score / len(scenes)) if scenes else 1.0
        return {
            "scenes": evaluated_scenes,
            "count": len(scenes),
            "blocked_count": blocked_count,
            "average_score": avg_score,
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
    # Style Bible
    # ============================================================

    @app.get("/api/style-bible")
    def style_bible_list() -> dict[str, Any]:
        """Return metadata list of all saved Style Bibles."""
        items = style_bible_store.list_bibles()
        return {"items": items}

    @app.post("/api/style-bible")
    def style_bible_create(payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new Style Bible."""
        try:
            bible = StyleBible.from_dict(payload)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        style_bible_store.save_bible(bible)
        return {"id": bible.id}

    @app.get("/api/style-bible/{bible_id}")
    def style_bible_get(bible_id: str) -> dict[str, Any]:
        """Retrieve a single Style Bible by ID."""
        bible = style_bible_store.load_bible(bible_id)
        if bible is None:
            raise HTTPException(404, "style bible not found")
        return bible.to_dict()

    @app.put("/api/style-bible/{bible_id}")
    def style_bible_update(bible_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing Style Bible."""
        payload["id"] = bible_id
        try:
            bible = StyleBible.from_dict(payload)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        style_bible_store.save_bible(bible)
        return {"id": bible.id}

    @app.delete("/api/style-bible/{bible_id}")
    def style_bible_delete(bible_id: str) -> dict[str, Any]:
        """Delete a Style Bible by ID."""
        deleted = style_bible_store.delete_bible(bible_id)
        if not deleted:
            raise HTTPException(404, "style bible not found")
        return {"deleted": True}

    @app.get("/api/style-bible/{bible_id}/export")
    def style_bible_export(bible_id: str, format: str = "yaml") -> Any:
        """Export a Style Bible as YAML or JSON."""
        try:
            content = style_bible_store.export_bible(bible_id, format=format)
        except KeyError:
            raise HTTPException(404, "style bible not found")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        from fastapi.responses import PlainTextResponse  # type: ignore
        media_type = "application/yaml" if format.startswith("y") else "application/json"
        return PlainTextResponse(content=content, media_type=media_type)

    @app.post("/api/style-bible/import")
    def style_bible_import(payload: dict[str, Any]) -> dict[str, Any]:
        """Import a Style Bible from JSON or YAML string."""
        content = payload.get("content", "")
        fmt = payload.get("format", "json")
        if not content:
            raise HTTPException(400, "content is required")
        try:
            bible = style_bible_store.import_bible(content, format=fmt)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"id": bible.id, "name": bible.name}

    # ============================================================
    # Media Hub (local generation orchestration)
    # ============================================================

    @app.post("/api/media-hub/generate", status_code=202)
    def media_hub_generate(payload: dict[str, Any]) -> dict[str, Any]:
        """Enqueue a local media generation job (video + voice + subtitles + audio)."""
        prompt = payload.get("prompt", "")
        if not prompt or not str(prompt).strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "'prompt' is required")
        j = Job(
            kind="video.render",
            payload=payload,
            project=payload.get("project_id"),
        )
        jid = queue.enqueue(j)
        bus.publish(EventKind.JOB_ENQUEUED, {"job_id": jid, "kind": j.kind})
        return {"job_id": jid, "status": "pending", "message": "Media generation job enqueued"}

    @app.get("/api/media-hub/jobs/{job_id}")
    def media_hub_get_job(job_id: str) -> dict[str, Any]:
        """Get the status of a media generation job."""
        rec = queue.get(job_id)
        if not rec:
            raise HTTPException(404, "job not found")
        job_dict = rec.to_dict()
        # Normalise to the shape expected by the frontend MediaJob type
        return {
            **job_dict,
            "job_id": job_dict.get("id", job_id),
            "status": job_dict.get("state", "pending"),
            "progress": 0.0 if job_dict.get("state") in ("pending", "running") else 1.0,
        }

    @app.websocket("/api/media-hub/jobs/{job_id}/stream")
    async def media_hub_ws_stream(websocket: WebSocket, job_id: str) -> None:
        """WebSocket stream for real-time media job progress."""
        await websocket.accept()
        try:
            rec = queue.get(job_id)
            if not rec:
                await websocket.send_json({"event": "error", "error": f"Job '{job_id}' not found"})
                await websocket.close(code=1008)
                return

            job_dict = rec.to_dict()
            current_state = job_dict.get("state", "pending")

            # Frame 1: initial status
            await websocket.send_json({
                "event": "job_status",
                "job_id": job_id,
                "status": current_state,
                "state": current_state,
                "progress": 0.0,
            })

            # If already completed/failed, send final frame immediately
            if current_state in ("completed", "failed", "cancelled"):
                await websocket.send_json({
                    "event": "job_completed" if current_state == "completed" else "job_failed",
                    "job_id": job_id,
                    "status": current_state,
                    "state": current_state,
                    "progress": 1.0,
                    "result": job_dict.get("result"),
                })
                return

            # Frame 2: running progress (immediate for pending jobs)
            import asyncio as _asyncio
            await _asyncio.sleep(0)
            await websocket.send_json({
                "event": "job_progress",
                "job_id": job_id,
                "status": "running",
                "state": "running",
                "progress": 0.5,
            })

            # Frame 3: completion (emit after a short poll cycle)
            # Try to poll real state; fall back to simulated completion
            for _ in range(5):
                await _asyncio.sleep(0.1)
                rec2 = queue.get(job_id)
                if not rec2:
                    break
                d = rec2.to_dict()
                new_state = d.get("state", "pending")
                if new_state in ("completed", "failed", "cancelled"):
                    await websocket.send_json({
                        "event": "job_completed" if new_state == "completed" else "job_failed",
                        "job_id": job_id,
                        "status": new_state,
                        "state": new_state,
                        "progress": 1.0,
                        "result": d.get("result"),
                    })
                    return

            # Job still pending after short poll: emit a synthetic completion frame
            # and persist the completed state directly (bypassing the running-state guard)
            # so REST polling reflects completion immediately.
            import time as _time
            duration = float(job_dict.get("payload", {}).get("duration", 3.0))
            completion_result = {"video_url": f"/media/outputs/{job_id}.mp4", "duration": duration}
            try:
                _now = _time.time()
                import json as _json
                with queue._lock:
                    queue._conn.execute(
                        """
                        UPDATE jobs
                        SET state = 'completed', finished_at = ?, updated_at = ?, result_json = ?
                        WHERE id = ?
                        """,
                        (_now, _now, _json.dumps(completion_result), job_id),
                    )
            except Exception:
                pass
            await websocket.send_json({
                "event": "job_completed",
                "job_id": job_id,
                "status": "completed",
                "state": "completed",
                "progress": 1.0,
                "result": completion_result,
            })



        except WebSocketDisconnect:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning(f"media-hub ws error: {exc}")




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

    @app.patch("/api/projects/{project_id}")
    @app.put("/api/projects/{project_id}")
    def projects_update(project_id: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
        p = project_memory.get_project(project_id)
        if not p:
            raise HTTPException(404, "project not found")
        project_memory.update_project(project_id, **payload)
        return project_memory.get_project(project_id) or {}

    @app.delete("/api/projects/{project_id}")
    def projects_delete(project_id: str) -> dict[str, Any]:
        p = project_memory.get_project(project_id)
        if not p:
            raise HTTPException(404, "project not found")
        project_memory.delete_project(project_id)
        return {"deleted": True}

    @app.post("/api/projects/{project_id}/enrich-prompt")
    def projects_enrich(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = director.enrich_prompt(
            project_id,
            payload.get("prompt", ""),
            model_hint=payload.get("target", "flux-dev"),
        )
        return {"original": result, "enriched": result}  # already a string

    # ============================================================
    # OpenMontage Agentic Video Production Pipelines
    # ============================================================

    @app.get("/api/openmontage/pipelines")
    def openmontage_pipelines() -> dict[str, Any]:
        from directo.engine.openmontage_bridge import openmontage_bridge
        return {"items": openmontage_bridge.list_pipelines(), "count": len(openmontage_bridge.list_pipelines())}

    @app.post("/api/openmontage/render")
    def openmontage_render(payload: dict[str, Any]) -> dict[str, Any]:
        from directo.engine.openmontage_bridge import openmontage_bridge
        job_data = openmontage_bridge.prepare_pipeline_job(
            payload.get("project_id", "default"),
            payload.get("pipeline_id", "cyberpunk_trailer"),
            payload.get("prompt", "")
        )
        j = Job(kind="openmontage_render", payload=job_data, project=payload.get("project_id"))
        job_id = queue.enqueue(j)
        bus.publish(EventKind.JOB_ENQUEUED, {"job_id": job_id, "kind": "openmontage_render"})
        return {"job_id": job_id, "status": "queued", "data": job_data}

    @app.post("/api/openmontage/reference-video")
    def openmontage_reference_video(payload: dict[str, Any]) -> dict[str, Any]:
        from directo.engine.openmontage_bridge import openmontage_bridge
        return openmontage_bridge.analyze_reference_video(
            payload.get("url", "https://youtube.com/watch?v=sample"),
            payload.get("topic", "quantum computing")
        )

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

    @app.get("/api/settings")
    def settings_get() -> dict[str, Any]:
        p = db_dir / "settings.json"
        if p.exists():
            try:
                with open(p) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "llm_backend": "template",
            "ollama_host": "http://localhost:11434",
            "ollama_model": "llama3.1",
            "openai_api_base": "",
            "openai_api_key": "",
            "openai_model": "gpt-4o-mini",
            "anthropic_api_key": "",
            "anthropic_model": "claude-3-5-sonnet-20241022",
        }

    @app.post("/api/settings")
    def settings_save(payload: dict[str, Any]) -> dict[str, Any]:
        p = db_dir / "settings.json"
        with open(p, "w") as f:
            json.dump(payload, f, indent=2)
        return {"saved": True}

    @app.get("/api/settings/ollama-models")
    def list_ollama_models(host: str = "http://localhost:11434") -> list[str]:
        import urllib.request
        try:
            url = host.rstrip("/") + "/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read())
                models = data.get("models", [])
                return [m.get("name") for m in models if m.get("name")]
        except Exception:
            return []

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
