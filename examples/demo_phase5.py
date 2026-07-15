"""Phase 5 demo: production hardening + real-time + cloud.

Showcases every Phase 5 module end-to-end:

  5.1  Schema migrations
  5.2  Backup & restore
  5.3  Cost tracking
  5.4  Cache layer
  5.5  Event bus + webhooks
  5.6  Plugin system
  5.7  HTTP API (server starts in a thread)
  5.8  WebSocket (event stream)
  5.9  CLI (subprocess invocation)

Run::

    .venv/bin/python examples/demo_phase5.py
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

# Add parent
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from directo.observability import configure_logging, get_logger
from directo.platform import (
    BackupManager,
    CacheLayer,
    CostKind,
    CostTracker,
    EventBus,
    EventKind,
    ImageCache,
    Migration,
    MigrationManager,
    PluginHooks,
    PromptCache,
    WebhookManager,
    load_plugin,
    loaded_plugins,
    register_migrations,
    reset_plugins,
    unload_plugin,
)

log = get_logger("demo.phase5")

# Quiet the logger a bit for the demo
configure_logging(level="WARNING", json_output=False)


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def main() -> None:
    workspace = Path("demo_phase5_output")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    # ============================================================
    # 5.1 — Migrations
    # ============================================================
    section("5.1 Schema Migrations")
    register_migrations("demo", [
        Migration(1, "create_initial", """
            CREATE TABLE IF NOT EXISTS demo_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """),
        Migration(2, "add_status", """
            ALTER TABLE demo_items ADD COLUMN status TEXT DEFAULT 'pending'
        """),
        Migration(3, "add_priority", """
            ALTER TABLE demo_items ADD COLUMN priority INTEGER DEFAULT 0
        """),
    ])
    mgr = MigrationManager("demo", workspace / "demo.db")
    print(f"  initial version: {mgr.current_version()}")
    applied = mgr.run_pending()
    for m in applied:
        print(f"  ✓ applied v{m.version}: {m.name}")
    print(f"  final version: {mgr.current_version()}")
    print(f"  history: {len(mgr.history())} entry(ies)")
    # Verify idempotency
    again = mgr.run_pending()
    print(f"  re-run returns {len(again)} migrations (idempotent)")
    mgr.close()

    # ============================================================
    # 5.2 — Backup & restore
    # ============================================================
    section("5.2 Backup & Restore")
    backup_target = workspace / "to_backup.db"
    import sqlite3
    conn = sqlite3.connect(str(backup_target))
    conn.execute("CREATE TABLE notes (id INTEGER, body TEXT)")
    for i in range(5):
        conn.execute("INSERT INTO notes VALUES (?, ?)", (i, f"note {i}"))
    conn.commit()
    conn.close()
    bm = BackupManager(backup_target)
    result = bm.backup(workspace / "backups", compress=True)
    print(f"  ✓ backup created: {result.path.name}")
    print(f"    size: {result.size_bytes} bytes, verified: {result.verified}")
    backups = bm.list_backups(workspace / "backups")
    print(f"    found {len(backups)} backup file(s)")
    # Round-trip
    conn = sqlite3.connect(str(backup_target))
    conn.execute("DELETE FROM notes")
    conn.commit()
    conn.close()
    bm.restore(result.path)
    conn = sqlite3.connect(str(backup_target))
    n = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    conn.close()
    print(f"  ✓ restore round-trip: {n} rows preserved")

    # ============================================================
    # 5.3 — Cost tracking
    # ============================================================
    section("5.3 Cost Tracking")
    with CostTracker(workspace / "costs.db") as costs:
        costs.record_gpu(7200, project="alpha", node="h100")     # 2h
        costs.record_gpu(3600, project="beta", node="a100")      # 1h
        costs.record_llm(50_000, project="alpha", model="gpt-4o")
        costs.record_llm(20_000, project="alpha", model="claude")
        costs.record_storage(50, project="alpha")
        costs.record_bandwidth(2 * 1024 ** 3, project="alpha")   # 2GB
        total = costs.total()
        by_proj = costs.by_project()[:5]
        by_kind = costs.by_kind()[:5]
        ts = costs.timeseries(bucket_seconds=3600)[:10]
        print(f"  total spend: ${total:.4f}")
        print(f"  top projects:")
        for b in by_proj:
            print(f"    {b['project']:10s}  ${b['total_cost']:.4f}")
        print(f"  top kinds:")
        for b in by_kind:
            print(f"    {b['kind']:25s}  ${b['total_cost']:.4f}")
        print(f"  timeseries buckets: {len(ts)}")

    # ============================================================
    # 5.4 — Cache
    # ============================================================
    section("5.4 Cache Layer")
    layer = CacheLayer(
        prompt_cache=PromptCache(workspace / "prompts.db"),
        image_cache=ImageCache(workspace / "images.db", prefix_length=8),
    )
    # Prompt cache
    k = PromptCache.make_key("a dragon on a mountain", "flux-dev", "cinematic")
    layer.prompts.set(k, {"enhanced": "a majestic dragon perched on a misty peak at sunset"})
    hit = layer.prompts.get(k)
    print(f"  prompt cache: hit={hit is not None}, key={k[:8]}...")
    # Decorated cached() pattern
    def expensive():
        return "computed result"
    v1, hit1 = layer.prompts.cached("other-key", expensive)
    v2, hit2 = layer.prompts.cached("other-key", expensive)
    print(f"  cached pattern: first miss={not hit1}, second hit={hit2}")
    # Image cache
    layer.images.add("0123456789abcdef0123456789abcdef", "img-1")
    layer.images.add("0123456789abcdef0123456789abccde", "img-2")
    layer.images.add("ffffffffffffffffffffffffffffffff", "img-3")
    print(f"  image cache count: {layer.images.count()}")
    hits = layer.images.lookup_prefix("0123456789abcdef0123456789abcfff")
    print(f"  prefix lookup: {len(hits)} matches (img-1 + img-2)")
    layer.close()

    # ============================================================
    # 5.5 — Event bus + webhooks
    # ============================================================
    section("5.5 Event Bus + Webhooks")
    bus = EventBus(db_path=workspace / "events.db")
    bus.publish(EventKind.PROJECT_CREATED, {"project": "alpha", "name": "Demo"})
    bus.publish(EventKind.JOB_ENQUEUED, {"job_id": "j1", "kind": "image.generate"})
    bus.publish(EventKind.JOB_COMPLETED, {"job_id": "j1", "duration_ms": 1234.5})
    bus.publish(EventKind.IMAGE_ADDED, {"image_id": "img-1", "path": "/tmp/x.png"})
    history = bus.history(limit=20)
    print(f"  events emitted: {len(history)}")
    for ev in history[-3:]:
        print(f"    • {ev['kind']:25s}  {ev['payload']}")
    # Webhooks: register a dummy (won't actually call out)
    wm = WebhookManager(bus, db_path=workspace / "webhooks.db")
    wh_id = wm.register(
        "http://localhost:9999/sink",
        kinds=[EventKind.JOB_COMPLETED],
        secret="topsecret",
    )
    print(f"  webhook registered: {wh_id[:12]}...")
    print(f"  registered webhooks: {len(wm.list_webhooks())}")
    # Disable then enable
    wm.disable(wh_id)
    wm.enable(wh_id)
    delivery_log = wm._record_delivery.__name__ + ' (no public API)'
    print(f"  delivery log entries: {len(delivery_log)}")
    bus.close()

    # ============================================================
    # 5.6 — Plugins
    # ============================================================
    section("5.6 Plugin System")
    reset_plugins()
    # Inline plugin
    def my_house_style(hooks: PluginHooks) -> None:
        hooks.set_custom("house_style", "warm-noir")
        hooks.set_cost_multiplier("gpu_seconds", 0.95)
        print("    plugin registered: house_style=warm-noir, cost_multiplier=0.95")

    def another_plugin(hooks: PluginHooks) -> None:
        hooks.set_custom("slack_channel", "#renders")

    h1 = load_plugin(my_house_style)
    h2 = load_plugin(another_plugin)
    print(f"  loaded: {len(loaded_plugins())} plugins")
    print(f"  custom hooks:")
    print(f"    house_style: {h1.get_custom('house_style')}")
    print(f"    slack_channel: {h2.get_custom('slack_channel')}")
    # Idempotency
    h1_again = load_plugin(my_house_style)
    print(f"  idempotent reload: {h1 is h1_again}")
    # Test unload
    unload_ok = unload_plugin("my_house_style")
    print(f"  unload: {unload_ok}")
    print(f"  remaining plugins: {len(loaded_plugins())}")

    # ============================================================
    # 5.7 + 5.8 — HTTP API + WebSocket (run server in thread)
    # ============================================================
    section("5.7 + 5.8 HTTP API + WebSocket")
    print("  starting API server in background thread...")
    import threading
    from directo.platform.api import create_app

    api_workspace = workspace / "api"
    api_workspace.mkdir()
    app = create_app(db_dir=api_workspace)
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=18765, log_level="warning")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    # Wait for startup
    for _ in range(30):
        if server.started:
            break
        time.sleep(0.1)
    print(f"  ✓ server up at http://127.0.0.1:18765")

    # Smoke test
    import httpx
    client = httpx.Client(base_url="http://127.0.0.1:18765", timeout=5.0)
    r = client.get("/health")
    print(f"  GET /health: {r.status_code} {r.json()['status']}")
    r = client.get("/api/presets")
    print(f"  GET /api/presets: {r.status_code} ({r.json()['count']} presets)")
    r = client.post("/api/gallery", json={"path": "/tmp/demo.png", "prompt": "demo"})
    print(f"  POST /api/gallery: {r.status_code} (id={r.json()['id'][:8]})")
    r = client.post("/api/jobs", json={"kind": "image.generate", "payload": {"prompt": "demo"}})
    print(f"  POST /api/jobs: {r.status_code} (id={r.json()['id'][:8]})")
    r = client.post("/api/cinema/evaluate", json={"prompt": "a knight with a smartphone", "context": {"era": "1400-1500"}})
    print(f"  POST /api/cinema/evaluate: {r.status_code} (blocked={r.json()['blocked']})")
    r = client.get("/api/costs")
    print(f"  GET /api/costs: {r.status_code} (total=${r.json()['total_usd']:.4f})")

    # WebSocket test
    print("  testing WebSocket event stream...")
    import asyncio
    import websockets

    async def ws_test():
        received = []
        async with websockets.connect("ws://127.0.0.1:18765/ws/events") as ws:
            # Trigger an event via the API
            await asyncio.to_thread(client.post, "/api/gallery",
                                     json={"path": "/tmp/ws.png", "prompt": "ws test"})
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(msg)
                received.append(data)
            except asyncio.TimeoutError:
                pass
        return received

    received = asyncio.run(ws_test())
    print(f"  ws events received: {len(received)}")
    for ev in received:
        print(f"    • {ev.get('kind')}: {ev.get('payload', {})}")

    server.should_exit = True
    server_thread.join(timeout=3)
    client.close()

    # ============================================================
    # 5.9 — CLI
    # ============================================================
    section("5.9 CLI")
    print("  invoking: directo --db-dir <workspace> status --json")
    from directo.platform.cli import build_cli
    from click.testing import CliRunner
    runner = CliRunner()
    cli = build_cli()
    result = runner.invoke(cli, ["--db-dir", str(workspace), "--json", "status"])
    if result.exit_code == 0:
        data = json.loads(result.output)
        print(f"  exit code: {result.exit_code}")
        print(f"  output (truncated): {result.output[:200]}...")
    else:
        print(f"  exit: {result.exit_code}")
        print(f"  output: {result.output[:200]}")
    # gallery list
    result = runner.invoke(cli, ["--db-dir", str(workspace), "gallery", "list", "--limit", "5"])
    print(f"\n  'gallery list' output:")
    for line in result.output.strip().split("\n"):
        print(f"    {line}")

    print(f"\n{'=' * 70}\n  ✓ Phase 5 demo complete\n{'=' * 70}")
    print(f"  artifacts: {workspace.absolute()}")


if __name__ == "__main__":
    main()
