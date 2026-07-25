"""Directo CLI — the command-line interface for ops and power users.

A simple Click-based CLI exposing the most common operations:

    directo status                              # queue + project health
    directo gallery list [--project p]           # browse the gallery
    directo gallery show <image_id>              # inspect an image
    directo gallery rate <image_id> 5            # 1-5 stars
    directo jobs list [--state pending]          # browse the queue
    directo jobs submit --kind image.generate ...# enqueue a job
    directo jobs cancel <job_id>                 # cancel
    directo presets list [--kind live_action]    # browse preset packs
    directo cinema evaluate "a dragon on fire"   # rules engine
    directo backup [queue|gallery|...]           # create a backup
    directo restore <path>                       # restore a backup
    directo server [--port 8000]                 # run the HTTP API
    directo migrate <module>                     # run pending migrations

Run::

    directo --help
    directo status --db-dir ./directo_data
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import click  # type: ignore
except ImportError:
    click = None  # type: ignore

from directo.observability import configure_logging, get_logger
from directo.platform.migrations import MigrationManager, list_registered_migrations

log = get_logger("directo.platform.cli")


# Lazy service init helpers (so the CLI doesn't pay for what it doesn't use)
def _ensure_click() -> None:
    if click is None:
        raise RuntimeError("Click is required for the CLI. Run: pip install click")


def _queue(db_dir: Path):
    from directo.queue import PersistentQueue
    return PersistentQueue(db_dir / "queue.db")


def _gallery(db_dir: Path):
    from directo.gallery import Gallery
    return Gallery(db_dir / "gallery.db")


def _presets(db_dir: Path):
    from directo.scale import PresetStore
    return PresetStore(db_dir / "presets.db")


def _cinema():
    from directo.cinema import CinemaEngine
    return CinemaEngine()


def _bus(db_dir: Path):
    from directo.platform.events import EventBus
    return EventBus(db_path=db_dir / "events.db")


def _costs(db_dir: Path):
    from directo.platform.costs import CostTracker
    return CostTracker(db_dir / "costs.db")


# =====================================================================
# CLI
# =====================================================================


def build_cli():
    _ensure_click()

    @click.group(context_settings={"help_option_names": ["-h", "--help"]})
    @click.option("--db-dir", default="./directo_data", type=click.Path(),
                  help="Directory for SQLite databases.")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
    @click.pass_context
    @click.version_option(version="1.1.1", prog_name="directo")
    def cli(ctx: click.Context, db_dir: str, as_json: bool) -> None:
        """Directo — production CLI for the creative AI platform."""
        ctx.ensure_object(dict)
        ctx.obj["db_dir"] = Path(db_dir)
        ctx.obj["as_json"] = as_json
        configure_logging(level="WARNING", json_output=False)

    # ----------------- status -----------------

    @cli.command()
    @click.pass_context
    def status(ctx: click.Context) -> None:
        """Show queue + project health."""
        db_dir: Path = ctx.obj["db_dir"]
        as_json: bool = ctx.obj["as_json"]
        q = _queue(db_dir)
        g = _gallery(db_dir)
        c = _costs(db_dir)
        snap = {
            "queue": q.stats(),
            "gallery": {"total": g.count(), "stats": g.stats()},
            "costs_total_usd": c.total(),
        }
        if as_json:
            click.echo(json.dumps(snap, indent=2, default=str))
        else:
            click.echo("Directo status:")
            click.echo(f"  queue: {snap['queue']}")
            click.echo(f"  gallery: {snap['gallery']['total']} images")
            click.echo(f"  total cost: ${snap['costs_total_usd']:.4f}")
        q.close(); g.close(); c.close()

    # ----------------- gallery -----------------

    @cli.group()
    def gallery() -> None:
        """Browse and curate the gallery."""

    @gallery.command("list")
    @click.option("--project", default=None)
    @click.option("--min-rating", default=0, type=int)
    @click.option("--limit", default=20, type=int)
    @click.pass_context
    def gallery_list(ctx: click.Context, project: str | None, min_rating: int, limit: int) -> None:
        """List gallery images."""
        g = _gallery(ctx.obj["db_dir"])
        items = g.search(project=project, min_rating=min_rating, limit=limit)
        if ctx.obj["as_json"]:
            click.echo(json.dumps([r.to_dict() for r in items], indent=2, default=str))
        else:
            for r in items:
                stars = "★" * r.rating + "☆" * (5 - r.rating) if r.rating else "·"
                click.echo(f"  {r.id[:8]}  {stars}  [{r.project or '—'}]  {r.prompt[:60]}")
        g.close()

    @gallery.command("show")
    @click.argument("image_id")
    @click.pass_context
    def gallery_show(ctx: click.Context, image_id: str) -> None:
        """Show full details of one image."""
        g = _gallery(ctx.obj["db_dir"])
        r = g.get(image_id)
        if r is None:
            click.echo("not found", err=True); sys.exit(1)
        if ctx.obj["as_json"]:
            click.echo(json.dumps(r.to_dict(), indent=2, default=str))
        else:
            for k, v in r.to_dict().items():
                click.echo(f"  {k}: {v}")
        g.close()

    @gallery.command("rate")
    @click.argument("image_id")
    @click.argument("rating", type=int)
    @click.pass_context
    def gallery_rate(ctx: click.Context, image_id: str, rating: int) -> None:
        """Rate an image 1-5 stars (0 to clear)."""
        g = _gallery(ctx.obj["db_dir"])
        g.rate(image_id, rating)
        click.echo(f"rated {image_id}: {rating}/5")
        g.close()

    # ----------------- jobs -----------------

    @cli.group()
    def jobs() -> None:
        """Inspect and submit queue jobs."""

    @jobs.command("list")
    @click.option("--state", default=None, help="pending|running|completed|failed")
    @click.option("--limit", default=20, type=int)
    @click.pass_context
    def jobs_list(ctx: click.Context, state: str | None, limit: int) -> None:
        """List jobs by state."""
        from directo.queue import JobState
        q = _queue(ctx.obj["db_dir"])
        s = JobState(state) if state else None
        items = q.list_by_state(s, limit=limit) if s else q.list_by_state(JobState.PENDING, limit=limit)
        if ctx.obj["as_json"]:
            click.echo(json.dumps([j.to_dict() for j in items], indent=2, default=str))
        else:
            for j in items:
                click.echo(f"  {j.id[:8]}  [{j.state.value:10s}]  {j.kind}  {j.payload.get('prompt', '')[:50]}")
        q.close()

    @jobs.command("submit")
    @click.option("--kind", required=True)
    @click.option("--payload-json", default="{}")
    @click.option("--project", default=None)
    @click.option("--priority", default=100, type=int)
    @click.pass_context
    def jobs_submit(ctx: click.Context, kind: str, payload_json: str,
                    project: str | None, priority: int) -> None:
        """Submit a job to the queue."""
        from directo.queue import Job
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            click.echo(f"invalid payload JSON: {exc}", err=True); sys.exit(1)
        q = _queue(ctx.obj["db_dir"])
        j = Job(kind=kind, payload=payload, project=project, priority=priority)
        jid = q.enqueue(j)
        click.echo(f"submitted job: {jid}")
        q.close()

    @jobs.command("cancel")
    @click.argument("job_id")
    @click.pass_context
    def jobs_cancel(ctx: click.Context, job_id: str) -> None:
        """Cancel a pending or running job."""
        q = _queue(ctx.obj["db_dir"])
        ok = q.cancel(job_id)
        click.echo("cancelled" if ok else "not found / not cancellable")
        q.close()

    # ----------------- presets -----------------

    @cli.command("presets")
    @click.option("--kind", default=None)
    @click.option("--era", default=None)
    @click.pass_context
    def presets_list(ctx: click.Context, kind: str | None, era: str | None) -> None:
        """List preset packs."""
        ps = _presets(ctx.obj["db_dir"])
        items = ps.list(kind=kind, era=era)
        if ctx.obj["as_json"]:
            click.echo(json.dumps([p.to_dict() for p in items], indent=2, default=str))
        else:
            for p in items:
                click.echo(f"  {p.id:50s}  {p.name:40s}  era={p.era or '—'}")
        ps.close()

    # ----------------- cinema -----------------

    @cli.command("cinema")
    @click.argument("prompt")
    @click.option("--era", default=None, help="pre-1973, 1920-1930, etc.")
    @click.option("--skip-suggests", is_flag=True)
    @click.pass_context
    def cinema_evaluate(ctx: click.Context, prompt: str, era: str | None,
                        skip_suggests: bool) -> None:
        """Run the cinema prompt rules engine."""
        engine = _cinema()
        ctx_obj: dict[str, Any] = ctx.obj
        if ctx_obj["as_json"]:
            report = engine.evaluate(prompt, context={"era": era} if era else {})
            click.echo(json.dumps(report.to_dict(), indent=2, default=str))
        else:
            report = engine.evaluate(prompt, context={"era": era} if era else {},
                                      skip_suggests=skip_suggests)
            status = "BLOCKED" if report.blocked else "OK"
            click.echo(f"  {status}: {prompt!r}")
            for w in report.warnings:
                click.echo(f"    ⚠ {w}")
            for s in report.suggestions:
                click.echo(f"    → {s}")
            click.echo(f"  augmented: {report.augmented_prompt[:200]}")

    # ----------------- backup / restore -----------------

    @cli.command("backup")
    @click.argument("db_name", default="queue")
    @click.option("--output-dir", default=None)
    @click.option("--no-compress", is_flag=True)
    @click.pass_context
    def backup(ctx: click.Context, db_name: str, output_dir: str | None, no_compress: bool) -> None:
        """Create a backup of a database."""
        from directo.platform.backup import BackupManager
        db_dir: Path = ctx.obj["db_dir"]
        # Map name to path
        db_path = db_dir / f"{db_name}.db"
        if not db_path.exists():
            click.echo(f"no such db: {db_path}", err=True); sys.exit(1)
        mgr = BackupManager(db_path)
        out_dir = Path(output_dir) if output_dir else db_dir
        result = mgr.backup(out_dir, compress=not no_compress)
        if result.error:
            click.echo(f"backup failed: {result.error}", err=True); sys.exit(1)
        click.echo(f"backup: {result.path} ({result.size_bytes:,} bytes, verified={result.verified})")

    @cli.command("restore")
    @click.argument("backup_path", type=click.Path(exists=True))
    @click.argument("db_name", default="queue")
    @click.pass_context
    def restore(ctx: click.Context, backup_path: str, db_name: str) -> None:
        """Restore a database from a backup file."""
        from directo.platform.backup import BackupManager
        db_dir: Path = ctx.obj["db_dir"]
        db_path = db_dir / f"{db_name}.db"
        mgr = BackupManager(db_path)
        result = mgr.restore(backup_path)
        if result.error:
            click.echo(f"restore failed: {result.error}", err=True); sys.exit(1)
        click.echo(f"restored: {result.path} ({result.size_bytes:,} bytes)")

    # ----------------- migrate -----------------

    @cli.command("migrate")
    @click.argument("module")
    @click.pass_context
    def migrate(ctx: click.Context, module: str) -> None:
        """Run pending schema migrations for a module."""
        from directo.platform.migrations import MigrationManager
        db_dir: Path = ctx.obj["db_dir"]
        # Convention: migration DB lives next to the module's DB
        db_path = db_dir / f"{module}.db"
        if not db_path.exists():
            click.echo(f"no such db: {db_path} (will create)", err=True)
        mgr = MigrationManager(module, db_path)
        pending = mgr.pending()
        click.echo(f"current: v{mgr.current_version()}, pending: {len(pending)}")
        applied = mgr.run_pending()
        for m in applied:
            click.echo(f"  ✓ v{m.version}: {m.name}")
        mgr.close()

    # ----------------- server -----------------

    @cli.command("server")
    @click.option("--host", default="0.0.0.0")
    @click.option("--port", default=8000, type=int)
    @click.pass_context
    def server(ctx: click.Context, host: str, port: int) -> None:
        """Run the HTTP API server."""
        from directo.platform.api import run_server
        run_server(db_dir=ctx.obj["db_dir"], host=host, port=port)

    return cli


def main() -> None:
    """Entry point for ``python -m directo.platform.cli``."""
    cli = build_cli()
    cli()


if __name__ == "__main__":
    main()
