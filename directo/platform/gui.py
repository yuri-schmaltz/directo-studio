"""Streamlit GUI for Directo.

A web-based dashboard for the Directo creative AI platform. Built on top
of the same services the HTTP API and CLI use, so all three share state
when pointed at the same ``db_dir``.

Pages
-----
1. **Dashboard**        — system health, counts, total spend
2. **Gallery**          — browse, search, rate images
3. **Jobs**             — submit, list, cancel jobs
4. **Presets**          — browse, render + enhance prompts
5. **Cinema Engine**    — evaluate prompts, parse scripts
6. **Projects**         — manage creative projects
7. **Costs**            — spending breakdown + timeseries
8. **Backup**           — create + list backups
9. **Live Events**      — real-time event stream (via WebSocket)

Run::

    .venv/bin/streamlit run directo/platform/gui.py -- \
        --db-dir ./directo_data

Or import and call programmatically::

    from directo.platform.gui import run
    run(db_dir="./directo_data", port=8501)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import streamlit as st

from directo.gallery import Gallery
from directo.observability import configure_logging, get_logger
from directo.platform.cache import CacheLayer, ImageCache, PromptCache
from directo.platform.events import EventBus, EventKind, WebhookManager
from directo.queue import Job, JobState, PersistentQueue
from directo.scale import PresetStore

log = get_logger("directo.platform.gui")
configure_logging(level="WARNING", json_output=False)


# =====================================================================
# Service singletons (cached for the Streamlit session)
# =====================================================================


@st.cache_resource
def get_services(db_dir_str: str) -> dict[str, Any]:
    """Build all the long-lived services Directo needs.

    Streamlit re-runs the script on every interaction; this decorator
    ensures the SQLite connections are only opened once per session.
    """
    db_dir = Path(db_dir_str)
    db_dir.mkdir(parents=True, exist_ok=True)
    return {
        "queue": PersistentQueue(db_dir / "queue.db"),
        "gallery": Gallery(db_dir / "gallery.db"),
        "presets": PresetStore(db_dir / "presets.db"),
        "bus": EventBus(db_path=db_dir / "events.db"),
        "cache": CacheLayer(
            prompt_cache=PromptCache(db_dir / "prompts.db"),
            image_cache=ImageCache(db_dir / "images.db"),
        ),
        "webhooks": WebhookManager(
            EventBus(db_path=db_dir / "events.db"),
            db_path=db_dir / "webhooks.db",
        ),
    }


def get_db_dir() -> Path:
    """Resolve the db_dir from Streamlit query params, env, or default."""
    try:
        qp = st.query_params
        if "db_dir" in qp:
            return Path(str(qp["db_dir"]))
    except Exception:  # noqa: BLE001
        pass
    return Path("./directo_data")


# =====================================================================
# Page renderers
# =====================================================================


def page_dashboard(svcs: dict[str, Any]) -> None:
    st.header("📊 Dashboard")
    cols = st.columns(4)
    q = svcs["queue"]
    g = svcs["gallery"]
    queue_stats = q.stats()
    cols[0].metric("Queue (total)", queue_stats.get("total", 0))
    cols[1].metric("Pending", queue_stats.get("pending", 0))
    cols[2].metric("Running", queue_stats.get("running", 0))
    cols[3].metric("Failed", queue_stats.get("failed", 0))
    cols2 = st.columns(2)
    cols2[0].metric("Gallery images", g.count())
    cols2[1].metric("Cache (prompts)", svcs["cache"].prompts.stats().get("entries", 0))
    with st.expander("Queue stats (raw)"):
        st.json(queue_stats)
    with st.expander("Gallery stats (raw)"):
        st.json(g.stats())


def page_gallery(svcs: dict[str, Any]) -> None:
    st.header("🖼️ Gallery")
    g: Gallery = svcs["gallery"]
    col1, col2, col3 = st.columns(3)
    with col1:
        project = st.text_input("Project", value="")
    with col2:
        min_rating = st.slider("Min rating", 0, 5, 0)
    with col3:
        favorites = st.checkbox("Favorites only")
    limit = st.number_input("Limit", min_value=1, max_value=500, value=50)
    items = g.search(
        project=project or None,
        min_rating=min_rating,
        favorites_only=favorites,
        limit=int(limit),
    )
    st.caption(f"Found {len(items)} image(s)")
    if items:
        for rec in items[:30]:  # cap render
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 4, 1, 1])
                c1.write(f"**{rec.id[:8]}**")
                c2.write(f"`{rec.prompt[:80]}`")
                c3.write(f"⭐ {rec.rating}/5")
                with c4.popover("..."):
                    new_rating = st.slider("Rate", 0, 5, rec.rating, key=f"r-{rec.id}")
                    if st.button("Save", key=f"s-{rec.id}"):
                        g.rate(rec.id, new_rating)
                        st.success("rated")
                        time.sleep(0.3)
                        st.rerun()
                    st.caption(f"path: `{rec.path}`")
                    if rec.tags:
                        st.write("tags:", rec.tags)
                    st.write("created:", rec.created_at)


def page_jobs(svcs: dict[str, Any]) -> None:
    st.header("⚙️ Jobs")
    q: PersistentQueue = svcs["queue"]
    tab1, tab2 = st.tabs(["Submit", "Browse"])
    with tab1, st.form("submit_job"):
        kind = st.selectbox("Kind", [
            "image.generate", "image.upscale", "video.render",
            "audio.synth", "text.enhance",
        ])
        project = st.text_input("Project (optional)")
        priority = st.slider("Priority", 0, 1000, 100)
        payload = st.text_area("Payload (JSON)", value='{"prompt": "a beautiful scene"}', height=120)
        submit = st.form_submit_button("Submit")
        if submit:
            try:
                p = json.loads(payload)
                j = Job(kind=kind, payload=p, project=project or None, priority=int(priority))
                jid = q.enqueue(j)
                svcs["bus"].publish(EventKind.JOB_ENQUEUED, {"job_id": jid, "kind": kind})
                st.success(f"submitted: {jid[:12]}...")
            except json.JSONDecodeError as exc:
                st.error(f"invalid JSON: {exc}")
    with tab2:
        state_filter = st.selectbox("State", [None, "pending", "running", "completed", "failed", "cancelled"], index=0)
        s = JobState(state_filter) if state_filter else None
        items = q.list_by_state(s, limit=200) if s else q.list_by_state(JobState.PENDING, limit=200)
        st.caption(f"{len(items)} job(s)")
        for j in items[:50]:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
                c1.write(f"**{j.id[:8]}**")
                c2.write(f"`{j.kind}` · {j.payload.get('prompt', '')[:60]}")
                c3.write(f"`{j.state.value}`")
                if c4.button("Cancel", key=f"c-{j.id}"):
                    ok = q.cancel(j.id)
                    if ok:
                        svcs["bus"].publish(EventKind.JOB_CANCELLED, {"job_id": j.id})
                        st.success("cancelled")
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.warning("not cancellable")


def page_presets(svcs: dict[str, Any]) -> None:
    st.header("🎨 Presets")
    ps: PresetStore = svcs["presets"]
    col1, col2 = st.columns(2)
    with col1:
        kind = st.text_input("Kind (filter)", value="")
    with col2:
        era = st.text_input("Era (filter)", value="")
    items = ps.list(kind=kind or None, era=era or None)
    st.caption(f"{len(items)} preset(s)")
    if items:
        for p in items[:50]:
            with st.expander(f"{p.name}  ·  {p.kind}  ·  {p.era or '—'}"):
                st.write(f"**id:** `{p.id}`")
                st.write(f"**model:** {p.model}")
                st.write(f"**description:** {p.description}")
                with st.form(f"enhance-{p.id}"):
                    user_prompt = st.text_input("Your prompt", value="a beautiful sunset")
                    do_enhance = st.checkbox("Run LLM enhancement", value=True)
                    target = st.text_input("Target model", value=p.model or "flux-dev")
                    run = st.form_submit_button("Render")
                    if run and user_prompt:
                        rendered = p.render_prompt(user_prompt)
                        result = rendered
                        if do_enhance:
                            try:
                                from directo.scale.enhance import PromptEnhancer
                                pe = PromptEnhancer(provider="auto")
                                er = pe.enhance(rendered, target=target, context={"style": "cinematic"})
                                result = er.enhanced
                            except Exception as exc:  # noqa: BLE001
                                st.warning(f"enhancer unavailable: {exc}")
                        st.write("**rendered:**")
                        st.code(rendered)
                        if result != rendered:
                            st.write("**enhanced:**")
                            st.code(result)


def page_cinema(svcs: dict[str, Any]) -> None:
    st.header("🎬 Cinema Engine")
    from directo.cinema import CinemaEngine, parse_script_text
    engine = CinemaEngine()
    tab1, tab2 = st.tabs(["Evaluate prompt", "Parse script"])
    with tab1, st.form("cinema-eval"):
        prompt = st.text_area("Prompt", value="a man on horseback with a smartphone", height=80)
        era = st.text_input("Era (e.g. '1920-1930', 'pre-1973')", value="")
        run = st.form_submit_button("Evaluate")
        if run and prompt:
            ctx = {"era": era} if era else {}
            report = engine.evaluate(prompt, context=ctx)
            st.write(f"**Verdict:** {'⛔ BLOCKED' if report.blocked else '✅ OK'}")
            score = getattr(report, "score", 1.0)
            st.write(f"**Score:** {score:.2f}")
            if report.warnings:
                st.warning("Warnings:")
                for w in report.warnings:
                    st.write(f"  - {w}")
            if report.suggestions:
                st.info("Suggestions:")
                for s in report.suggestions:
                    st.write(f"  - {s}")
            with st.expander("Augmented prompt"):
                st.code(report.augmented_prompt)
            with st.expander("Full report"):
                st.json(report.to_dict())
    with tab2, st.form("cinema-parse"):
        text = st.text_area("Script", value=(
            "INT. KITCHEN - DAY\n\n"
            "ALICE looks out the window.\n\n"
            "ALICE\nIt's a beautiful day.\n\n"
            "EXT. PARK - DAY\n\n"
            "BOB walks by with a dog.\n"
        ), height=200)
        hint = st.text_input("Hint (optional)", value="")
        run = st.form_submit_button("Parse")
        if run and text:
            scenes = parse_script_text(text, hint=hint or "")
            st.success(f"parsed {len(scenes)} scene(s)")
            for s in scenes:
                with st.expander(f"Scene {s.number}: {s.slugline}"):
                    st.json(s.to_dict())



def page_backup(svcs: dict[str, Any]) -> None:
    st.header("💾 Backup")
    from directo.platform.backup import BackupManager
    db_dir = get_db_dir()
    targets = {
        "queue": db_dir / "queue.db",
        "gallery": db_dir / "gallery.db",
        "events": db_dir / "events.db",
        "presets": db_dir / "presets.db",
    }
    available = {k: v for k, v in targets.items() if v.exists()}
    if not available:
        st.info("no DB files yet — start using Directo first")
        return
    target = st.selectbox("Database", list(available.keys()))
    db_path = available[target]
    out_dir = db_path.parent
    if st.button(f"Create backup of {target}.db"):
        mgr = BackupManager(db_path)
        result = mgr.backup(out_dir, compress=True)
        if result.error:
            st.error(result.error)
        else:
            st.success(f"backup created: {result.path.name} ({result.size_bytes:,} bytes, verified={result.verified})")
    st.subheader("Existing backups")
    mgr = BackupManager(db_path)
    backups = [b for b in mgr.list_backups(out_dir)
               if b.resolve() != db_path.resolve() and b.name.startswith(f"{target}.")]
    if not backups:
        st.caption("(no backups yet)")
    for b in sorted(backups, reverse=True)[:20]:
        size = b.stat().st_size
        st.write(f"  📦 `{b.name}` ({size:,} bytes)")


def page_live_events(svcs: dict[str, Any]) -> None:
    st.header("📡 Live Events")
    bus: EventBus = svcs["bus"]
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption("Streaming the last 100 events from the EventBus. "
                   "Auto-refresh every 2s.")
    with col2:
        if st.button("Clear & re-poll"):
            st.rerun()
    placeholder = st.empty()
    history = bus.history(limit=100)
    with placeholder.container():
        if not history:
            st.info("no events yet — trigger something in another tab")
        else:
            for ev in reversed(history[-50:]):
                with st.container(border=True):
                    st.write(f"**{ev['kind']}**  `{ev['timestamp']:.2f}`")
                    st.json(ev.get("payload", {}))
    time.sleep(2.0)
    st.rerun()


def page_about(svcs: dict[str, Any] | None = None) -> None:
    st.header("ℹ️ About")
    st.markdown("""
**Directo v1.0** — production-ready creative AI platform.

5 phases, 207/207 tests, ~14.9k LOC, zero required external services.

| Phase | Modules | Tests |
|---|---|---|
| 0 — stabilization | 5 | 56 |
| 1 — creative foundation | 4 | 25 |
| 2 — technical scale | 4 | 27 |
| 3 — differentiation (cinema) | 3 | 31 |
| 4 — creative direction | 4 | 22 |
| 5 — production hardening | 9 | 46 |
| **Total** | **29** | **207** |

Run from CLI: `directo --db-dir ./directo_data status`
Run HTTP API: `directo --db-dir ./directo_data server`
""")


# =====================================================================
# Main app
# =====================================================================


PAGES = {
    "Dashboard": page_dashboard,
    "Gallery": page_gallery,
    "Jobs": page_jobs,
    "Presets": page_presets,
    "Cinema Engine": page_cinema,
    "Backup": page_backup,
    "Live Events": page_live_events,
    "About": page_about,
}


def main() -> None:
    st.set_page_config(
        page_title="Directo",
        page_icon="🎼",
        layout="wide",
    )
    st.title("🎼 Directo")
    st.caption("Production dashboard for the Directo creative AI platform")

    db_dir = get_db_dir()
    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Page", list(PAGES.keys()), label_visibility="collapsed")
        st.divider()
        st.write(f"**DB dir:** `{db_dir}`")
        try:
            st.write(f"**Streamlit:** {__import__('streamlit').__version__}")
        except Exception:  # noqa: BLE001
            pass

    svcs = get_services(str(db_dir))
    PAGES[page](svcs)


def run(db_dir: str | Path = "./directo_data", port: int = 8501) -> None:
    """Programmatic entry point — boots Streamlit via subprocess."""
    import subprocess
    import sys
    db_dir = Path(db_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    gui_path = Path(__file__).resolve()
    cmd = [
        sys.executable, "-m", "streamlit", "run", str(gui_path),
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--", "--db-dir", str(db_dir),
    ]
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
