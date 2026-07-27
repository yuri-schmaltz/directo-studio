"""Tests for the platform module (Phase 5)."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.platform import (
    BackupManager,
    CacheLayer,
    Event,
    EventBus,
    EventKind,
    ImageCache,
    Migration,
    MigrationError,
    MigrationManager,
    MultiBackup,
    PluginHooks,
    PromptCache,
    WebhookManager,
    load_plugin,
    noop_register,
    register_migrations,
    reset_plugins,
    unload_plugin,
    loaded_plugins,
)


# ============================================================
# Migrations
# ============================================================


def test_migration_manager_runs_pending(tmp_path):
    register_migrations("test_mod_a", [
        Migration(1, "create_initial", "CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY, name TEXT)"),
        Migration(2, "add_email", "ALTER TABLE t1 ADD COLUMN email TEXT"),
    ])
    db = tmp_path / "test.db"

    mgr = MigrationManager("test_mod_a", db)
    assert mgr.current_version() == 0
    applied = mgr.run_pending()
    assert len(applied) == 2
    assert mgr.current_version() == 2
    # Idempotent
    assert mgr.run_pending() == []


def test_migration_out_of_order_raises(tmp_path):
    register_migrations("test_mod_b", [
        Migration(2, "second", "CREATE TABLE t2 (id INTEGER)"),
    ])
    db = tmp_path / "test.db"
    mgr = MigrationManager("test_mod_b", db)
    with pytest.raises(MigrationError):
        mgr.run_pending()


def test_migration_history_persists(tmp_path):
    register_migrations("test_mod_c", [
        Migration(1, "create", "CREATE TABLE x (id INTEGER)"),
    ])
    db = tmp_path / "test.db"
    mgr = MigrationManager("test_mod_c", db)
    mgr.run_pending()
    mgr.close()
    # New manager, same DB
    mgr2 = MigrationManager("test_mod_c", db)
    assert mgr2.current_version() == 1
    assert mgr2.history()[0]["name"] == "create"


# ============================================================
# Backup
# ============================================================


def test_backup_basic(tmp_path):
    import sqlite3
    src = tmp_path / "src.db"
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'hello')")
    conn.commit()
    conn.close()
    mgr = BackupManager(src)
    result = mgr.backup(tmp_path)
    assert result.error is None
    assert result.verified
    assert result.path.exists()


def test_backup_compress_and_prune(tmp_path):
    import sqlite3
    import time as _time
    src = tmp_path / "src.db"
    sqlite3.connect(str(src)).execute("CREATE TABLE t (id INTEGER)").close()
    mgr = BackupManager(src)
    # Make 3 backups (each timestamped uniquely)
    for i in range(3):
        b = mgr.backup(tmp_path, compress=True, timestamped=True)
        _time.sleep(0.01)
    backups = mgr.list_backups(tmp_path)
    # Filter to actual backup files (exclude source db)
    actual = [b for b in backups if b.name.startswith("src.") and ".db" in b.name and b != src]
    assert len(actual) == 3
    pruned = mgr.prune(keep=1, directory=tmp_path)
    assert pruned == 2


def test_backup_restore_round_trip(tmp_path):
    import sqlite3
    src = tmp_path / "src.db"
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t (id INTEGER, val TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'original')")
    conn.commit()
    conn.close()
    mgr = BackupManager(src)
    backup = mgr.backup(tmp_path)
    # Mutate the DB
    conn = sqlite3.connect(str(src))
    conn.execute("UPDATE t SET val = 'changed' WHERE id = 1")
    conn.commit()
    conn.close()
    # Restore
    mgr.restore(backup.path)
    # Verify
    conn = sqlite3.connect(str(src))
    val = conn.execute("SELECT val FROM t WHERE id = 1").fetchone()[0]
    conn.close()
    assert val == "original"


def test_multi_backup(tmp_path):
    import sqlite3
    db1 = tmp_path / "one.db"
    db2 = tmp_path / "two.db"
    for p in (db1, db2):
        conn = sqlite3.connect(str(p))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()
    mb = MultiBackup({"one": db1, "two": db2})
    results = mb.backup_all(tmp_path / "backups", timestamped=False)
    assert "one" in results and "two" in results
    assert all(r.verified for r in results.values())


# ============================================================
# Cost tracking
# ============================================================



# ============================================================
# Cache
# ============================================================


def test_prompt_cache_get_set(tmp_path):
    with PromptCache(tmp_path / "c.db") as c:
        c.set("k1", {"value": 42}, ttl_seconds=60)
        assert c.get("k1") == {"value": 42}


def test_prompt_cache_ttl_expires(tmp_path):
    with PromptCache(tmp_path / "c.db") as c:
        c.set("k1", "value", ttl_seconds=0.01)
        import time
        time.sleep(0.05)
        assert c.get("k1") is None


def test_prompt_cache_make_key_deterministic():
    k1 = PromptCache.make_key("prompt", "model", "style")
    k2 = PromptCache.make_key("prompt", "model", "style")
    assert k1 == k2
    k3 = PromptCache.make_key("prompt", "model", "other")
    assert k1 != k3


def test_prompt_cache_cached_pattern(tmp_path):
    with PromptCache(tmp_path / "c.db") as c:
        calls = []
        def compute():
            calls.append(1)
            return "computed"
        v1, hit1 = c.cached("k", compute)
        v2, hit2 = c.cached("k", compute)
        assert v1 == "computed" == v2
        assert not hit1
        assert hit2
        assert len(calls) == 1


def test_prompt_cache_max_entries(tmp_path):
    with PromptCache(tmp_path / "c.db") as c:
        c.set_max_entries(3)
        for i in range(5):
            c.set(f"k{i}", i)
        assert c.stats()["entries"] == 3


def test_image_cache_lookup(tmp_path):
    with ImageCache(tmp_path / "i.db", prefix_length=4) as c:
        c.add("0123456789abcdef", "img-1")
        c.add("0123456789abcdee", "img-2")
        c.add("ffffffffffffffff", "img-3")
        # prefix "0123" returns both
        results = c.lookup_prefix("0123456789abcdee")
        assert len(results) == 2
        # prefix "ffff" returns one
        results = c.lookup_prefix("ffff000000000000")
        assert len(results) == 1


def test_cache_layer_combined(tmp_path):
    layer = CacheLayer(
        prompt_cache=PromptCache(tmp_path / "p.db"),
        image_cache=ImageCache(tmp_path / "i.db"),
    )
    layer.prompts.set("k", "v")
    layer.images.add("deadbeef00000000", "img-1")
    assert layer.prompts.get("k") == "v"
    assert layer.images.count() == 1
    layer.close()


# ============================================================
# Event bus
# ============================================================


def test_event_bus_publish_and_history():
    bus = EventBus(db_path=":memory:")
    bus.publish(EventKind.JOB_ENQUEUED, {"job_id": "j1"})
    bus.publish(EventKind.JOB_COMPLETED, {"job_id": "j1"})
    h = bus.history()
    assert len(h) == 2
    assert h[0]["kind"] == "job.completed"
    bus.close()


@pytest.mark.asyncio
async def test_event_bus_async_listener():
    bus = EventBus(db_path=":memory:")
    received: list[Event] = []
    async def listener(event: Event) -> None:
        received.append(event)
    bus.subscribe(EventKind.IMAGE_ADDED, listener)
    await bus.publish_async(EventKind.IMAGE_ADDED, {"x": 1})
    assert len(received) == 1
    assert received[0].payload == {"x": 1}
    bus.close()


def test_event_bus_global_listener():
    bus = EventBus(db_path=":memory:")
    # We don't await async listeners from sync publish; just verify no errors
    async def listener(event):
        pass
    bus.subscribe_all(listener)
    bus.publish(EventKind.JOB_ENQUEUED)
    bus.close()


# ============================================================
# Webhooks (we test the registration + delivery log, no actual HTTP)
# ============================================================


def test_webhook_register_and_list():
    bus = EventBus(db_path=":memory:")
    wm = WebhookManager(bus, db_path=":memory:")
    wh_id = wm.register("http://example.com/hook", kinds=[EventKind.JOB_COMPLETED])
    webhooks = wm.list_webhooks()
    assert len(webhooks) == 1
    assert webhooks[0].url == "http://example.com/hook"
    assert EventKind.JOB_COMPLETED in webhooks[0].kinds
    wm.delete(wh_id)
    assert len(wm.list_webhooks()) == 0
    bus.close()


def test_webhook_disable():
    bus = EventBus(db_path=":memory:")
    wm = WebhookManager(bus, db_path=":memory:")
    wh_id = wm.register("http://x.com")
    wm.disable(wh_id)
    wh = next(w for w in wm.list_webhooks() if w.id == wh_id)
    assert wh.enabled is False
    bus.close()


# ============================================================
# Plugins
# ============================================================


def test_plugin_hooks_basic():
    h = PluginHooks()
    h.set_custom("foo", "bar")
    assert h.get_custom("foo") == "bar"
    assert h.get_custom("missing", "default") == "default"


def test_plugin_subscribe_requires_async():
    h = PluginHooks()
    def sync_listener(e):
        pass
    with pytest.raises(TypeError):
        h.on(EventKind.JOB_ENQUEUED, sync_listener)


def test_load_plugin_callable():
    reset_plugins()
    captured = []
    def my_plugin(hooks: PluginHooks) -> None:
        captured.append("called")
        hooks.set_custom("hello", "world")
    h = load_plugin(my_plugin)
    assert captured == ["called"]
    assert h.get_custom("hello") == "world"
    # Idempotent
    h2 = load_plugin(my_plugin)
    assert h is h2


def test_loaded_plugins_tracking():
    reset_plugins()
    load_plugin(noop_register)
    load_plugin(lambda h: h.set_custom("x", 1))
    assert len(loaded_plugins()) >= 1  # other tests may have loaded plugins too


def test_unload_plugin():
    reset_plugins()
    load_plugin(noop_register)
    assert unload_plugin(noop_register.__name__) is True
    assert unload_plugin("nonexistent") is False


def test_plugin_via_dotted_path(tmp_path, monkeypatch):
    """Load a plugin by module name (writes a tiny module to tmp)."""
    import sys
    import importlib.util
    p = tmp_path / "my_plugin.py"
    p.write_text("def register(hooks):\n    hooks.set_custom('from_module', 'yes')\n")
    spec = importlib.util.spec_from_file_location("test_my_plugin", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_my_plugin"] = mod
    spec.loader.exec_module(mod)
    reset_plugins()
    h = load_plugin("test_my_plugin")
    assert h.get_custom("from_module") == "yes"




# ============================================================
# Extra coverage: ws auth, cache eviction, plugin custom hooks
# ============================================================


def test_event_bus_history_filter():
    bus = EventBus(db_path=":memory:")
    bus.publish(EventKind.JOB_ENQUEUED, {"job_id": "j1"})
    bus.publish(EventKind.JOB_COMPLETED, {"job_id": "j1"})
    bus.publish(EventKind.IMAGE_ADDED, {"x": 1})
    h = bus.history(kind=EventKind.JOB_COMPLETED, limit=10)
    assert len(h) == 1
    assert h[0]["kind"] == "job.completed"
    bus.close()


def test_prompt_cache_invalidate():
    with PromptCache(":memory:") as c:
        c.set("k", "v1")
        assert c.get("k") == "v1"
        c.invalidate("k")
        assert c.get("k") is None


def test_prompt_cache_clear():
    with PromptCache(":memory:") as c:
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.stats()["entries"] == 0


def test_image_cache_count_and_purge(tmp_path):
    with ImageCache(tmp_path / "i.db") as c:
        c.add("aaaafffffffffffff", "img-1")
        c.add("bbbbffffffffffff", "img-2")
        assert c.count() == 2
        purged = c.purge("aaaafffffffffffff")
        assert purged == 1
        assert c.count() == 1



def test_backup_integrity_check_real(tmp_path):
    import sqlite3
    db = tmp_path / "ok.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.close()
    mgr = BackupManager(db)
    assert mgr._verify(db) is True
    # Corrupt the file
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a database")
    assert mgr._verify(bad) is False


def test_plugin_register_preset_succeeds():
    from directo.scale import Preset
    h = PluginHooks()
    p = Preset(id="p1", name="Test", kind="live_action", model="flux-dev",
               description="test")
    h.register_preset(p)
    assert "p1" in h.list_presets()


def test_plugin_register_llm_provider_succeeds():
    """Just verify the registration mechanism accepts a class-based provider."""
    h = PluginHooks()
    # Use a simple stub class
    class _StubProvider:
        name = "custom-llm"
        def is_available(self): return True
        def enhance(self, prompt, **kwargs): return prompt
    h.register_llm_provider(_StubProvider())
    providers = h.list_llm_providers()
    assert "custom-llm" in providers


def test_migration_register_and_list():
    register_migrations("test_list_mod", [Migration(1, "init", "SELECT 1")])
    from directo.platform.migrations import list_registered_migrations
    names = list_registered_migrations("test_list_mod")
    assert len(names) >= 1
    assert names[0].name == "init"


def test_eventbus_to_dict_roundtrip():
    bus = EventBus(db_path=":memory:")
    bus.publish(EventKind.CANVAS_SAVED, {"canvas_id": "c1"})
    e = bus.history()[0]
    # Convert to Event object
    ev = Event.from_dict(e)
    assert ev.kind == EventKind.CANVAS_SAVED
    bus.close()

# ============================================================
# HTTP API smoke test (FastAPI TestClient)
# ============================================================


@pytest.fixture
def api_client(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from directo.platform.api import create_app
    app = create_app(db_dir=tmp_path)
    return TestClient(app)


def test_api_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "queue" in body
    assert "gallery" in body


def test_api_gallery_crud(api_client):
    # Create
    r = api_client.post("/api/gallery", json={"path": "/tmp/test.png", "prompt": "test"})
    assert r.status_code == 200
    rid = r.json()["id"]
    # Get
    r = api_client.get(f"/api/gallery/{rid}")
    assert r.status_code == 200
    assert r.json()["prompt"] == "test"
    # List
    r = api_client.get("/api/gallery")
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    # Rate
    r = api_client.patch(f"/api/gallery/{rid}", json={"rating": 4})
    assert r.status_code == 200
    r = api_client.get(f"/api/gallery/{rid}")
    assert r.json()["rating"] == 4


def test_api_jobs_submit_and_list(api_client):
    r = api_client.post("/api/jobs", json={
        "kind": "image.generate",
        "payload": {"prompt": "a dragon"},
    })
    assert r.status_code == 200
    jid = r.json()["id"]
    r = api_client.get(f"/api/jobs/{jid}")
    assert r.status_code == 200
    assert r.json()["kind"] == "image.generate"


def test_api_cinema_evaluate(api_client):
    r = api_client.post("/api/cinema/evaluate", json={
        "prompt": "a man with a smartphone",
        "context": {"era": "1920-1930"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["blocked"] is True


def test_api_cinema_evaluate_script(api_client):
    script_text = "# INT. SALOON - DAY\n\nA cowboy checks his smartphone.\n\n# EXT. DESERT - DAY\n\nA horse trots past."
    r = api_client.post("/api/cinema/evaluate-script", json={
        "text": script_text,
        "hint": ".md",
        "context": {"era": "1920-1930"},
    })
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["blocked_count"] == 1
    assert "evaluation" in body["scenes"][0]
    assert body["scenes"][0]["evaluation"]["blocked"] is True


def test_api_presets_list(api_client):
    r = api_client.get("/api/presets")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 8



def test_api_backup(api_client):
    r = api_client.post("/api/backup", json={"db": "queue"})
    assert r.status_code == 200
    body = r.json()
    assert "path" in body
    assert body["verified"] is True
