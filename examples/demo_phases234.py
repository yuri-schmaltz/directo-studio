"""Phases 2, 3, and 4 demo — Scale, Cinema, Director.

A end-to-end walk through every feature built in phases 2, 3, and 4:

Phase 2 — Scale:
- Detect local GPUs and pick a quantization
- Register ComfyUI nodes and route a job
- Apply a cinema preset
- Enhance a prompt via the multi-LLM enhancer

Phase 3 — Cinema:
- Run the rules engine against a prompt
- Parse a Fountain script into scenes
- Convert scenes to prompts
- Lay out a storyboard canvas

Phase 4 — Director:
- Create a project, add characters + style
- Plan a shot list (offline)
- Build a moodboard from references
- Render an animatic

Run:
    python examples/demo_phases234.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from directo import (
    Gallery,
    ImageRecord,
    configure_logging,
    get_logger,
)
from directo.cinema import (
    CanvasStore,
    CinemaEngine,
    Panel,
    StoryboardCanvas,
    parse_fountain,
    scenes_to_prompts,
)
from directo.director import (
    AnimaticBuilder,
    AnimaticClip,
    AnimaticProject,
    Character,
    CreativeDirector,
    MoodboardBuilder,
    ProjectMemory,
    StyleGuide,
    TemplateBackend,
)
from directo.scale import (
    NodeRegistry,
    PresetStore,
    PromptEnhancer,
    TargetModel,
    profile as vram_profile,
)


SAMPLE_SCRIPT = """Title: Dragon's Perch

INT. CLIFF OVERLOOK - DAWN

A weathered DRAGON perches on the cliff edge, watching the village below.
The wind catches torn scales on its left wing.

DRAGON
(quietly, to itself)
Not yet.

It shifts its weight, claws scraping rock.

EXT. CLIFF OVERLOOK - SUNSET

The same dragon, hours later, the light now amber.

DRAGON
(quietly)
...perhaps.
"""


def make_ref_image(path: Path, label: str, color: tuple[int, int, int]) -> None:
    img = Image.new("RGB", (640, 360), color=color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
        )
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 20), label[:40], fill=(255, 255, 255), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def main() -> None:
    configure_logging(level="INFO", json_output=False)
    log = get_logger("directo.demo")
    log.info("=" * 70)
    log.info("Directo Phases 2-4 Demo")
    log.info("=" * 70)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # ============================================================
        # PHASE 2 — SCALE
        # ============================================================
        log.info("\n[Phase 2/3] SCALE — GPUs, nodes, presets, LLM enhancement")

        # 2.1 VRAM
        vp = vram_profile()
        log.info(f"GPU profile: total={vp.total_vram_mb}MB free={vp.free_vram_mb}MB")
        log.info(f"  recommended quant: {vp.recommended_quant}")
        if vp.gpus:
            for g in vp.gpus:
                log.info(f"  GPU {g.index}: {g.name} ({g.vram_total_mb}MB)")
        else:
            log.info("  (no GPU detected — CPU mode)")

        # 2.2 Nodes (registry, no real servers)
        reg = NodeRegistry()
        log.info("ComfyUI node registry (simulated):")
        # Don't actually ping; just demonstrate the structure
        from directo.scale import ComfyUINode, NodeHealth
        reg.add(ComfyUINode(
            node_id="gpu-1", url="http://gpu-1.local:8188",
            tags=["flux", "video"],
            health=NodeHealth(node_id="gpu-1", reachable=True, queue_depth=2, vram_free_mb=20000),
        ))
        reg.add(ComfyUINode(
            node_id="gpu-2", url="http://gpu-2.local:8188",
            tags=["sdxl"],
            health=NodeHealth(node_id="gpu-2", reachable=True, queue_depth=0, vram_free_mb=8000),
        ))
        # Pick a node for a flux job
        chosen = reg.pick({"tags": ["flux"]})
        log.info(f"  picked node for flux job: {chosen.node_id} (queue_depth={chosen.health.queue_depth})")
        # Pick for video
        chosen_video = reg.pick({"tags": ["video"]})
        log.info(f"  picked node for video job: {chosen_video.node_id}")

        # 2.3 Presets
        with PresetStore(tmp / "presets.db") as ps:
            live_count = len(ps.list(kind="live_action"))
            anim_count = len(ps.list(kind="animation"))
            log.info(f"Built-in preset packs: {live_count} live-action + {anim_count} animation")
            for p in ps.list(kind="live_action")[:3]:
                log.info(f"  • {p.name} (era: {p.era or '—'})")
            log.info(f"  … and {live_count - 3} more live-action presets")
            # Pick a preset and render a sample prompt
            p = ps.get("live-classic-noir-1940s")
            sample = p.render_prompt("a man in a fedora, venetian blind shadows")
            log.info(f"noir preset → sample prompt: {sample[:120]}...")

        # 2.4 Prompt enhancement (template fallback)
        pe = PromptEnhancer(provider="template")
        result = pe.enhance("a man in fedora, venetian shadows",
                            target="sdxl",
                            context={"style": "cinematic"})
        log.info(f"enhanced prompt: {result.enhanced[:120]}...")
        log.info(f"  via {result.provider} in {result.duration_ms:.1f}ms")
        log.info(f"  negative prompt: {pe.negative_prompt_for('sdxl')[:80]}...")

        # ============================================================
        # PHASE 3 — CINEMA
        # ============================================================
        log.info("\n[Phase 3/3] CINEMA — rules engine, script parser, canvas")

        # 3.1 Rules engine
        engine = CinemaEngine()
        log.info(f"rules engine: {engine.rule_count} rules loaded")
        log.info("examples:")
        for prompt, ctx in [
            ("a knight in shining armor on a smartphone", {"era": "1300-1400"}),
            ("a man breathing fire underwater", {}),
            ("dragon", {}),  # short → will trigger suggestions
        ]:
            report = engine.evaluate(prompt, ctx)
            status = "BLOCKED" if report.blocked else "OK"
            log.info(f"  {status}: {prompt[:60]!r}")
            for w in report.warnings[:2]:
                log.info(f"      ⚠ {w[:100]}")
            for s in report.suggestions[:2]:
                log.info(f"      → {s}")

        # 3.2 Script parser
        script_path = tmp / "script.fountain"
        script_path.write_text(SAMPLE_SCRIPT)
        scenes = parse_fountain(SAMPLE_SCRIPT)
        log.info(f"\nparsed {len(scenes)} scenes from {script_path.name}:")
        for s in scenes:
            log.info(f"  scene {s.number}: {s.slugline}")
            log.info(f"    chars: {s.characters}")
            log.info(f"    prompt-ready: {s.to_prompt()[:100]}...")

        scene_prompts = scenes_to_prompts(scenes)
        log.info(f"\n{len(scene_prompts)} scene prompts ready for image generation")

        # 3.3 Storyboard canvas
        with CanvasStore(tmp / "canvases.db") as cs:
            canvas = StoryboardCanvas(id="storyboard-1", project="dragon", title="Dragon's Perch")
            for i, sp in enumerate(scene_prompts):
                p = canvas.add_panel(
                    shot_label=f"S{i+1:02d}",
                    x=(i % 4) * 340,
                    y=(i // 4) * 200,
                    width=320,
                    height=180,
                )
                log.info(f"  panel {p.id} ({p.shot_label}) at ({p.x:.0f},{p.y:.0f})")
            cs.save(canvas)
            loaded = cs.get("storyboard-1")
            log.info(f"  saved and reloaded: {len(loaded.panels)} panels")

        # ============================================================
        # PHASE 4 — DIRECTOR
        # ============================================================
        log.info("\n[Phase 4/4] DIRECTOR — agent, moodboard, animatic")

        # 4.1 Creative director + project
        mem = ProjectMemory(tmp / "memory.db")
        director = CreativeDirector(mem, TemplateBackend())
        pid = director.new_project(
            name="Dragon's Perch",
            concept="A weathered dragon watches a village from a cliff, deciding whether to intervene.",
            logline="A short about a dragon's choice.",
        )
        log.info(f"created project {pid}")

        director.add_character(pid, Character(
            name="The Dragon",
            description="ancient, scarred, weary but hopeful",
            visual_traits=["green scales", "scarred face", "torn left wing", "amber eyes"],
        ))
        director.add_character(pid, Character(
            name="The Village",
            description="a small medieval village in the valley below",
            visual_traits=["thatched roofs", "smoke from chimneys", "stone walls"],
        ))
        director.set_style(pid, StyleGuide(
            palette=["#2c1810", "#d4a574", "#7c5cff", "#f472b6"],
            lighting="golden hour, low-key chiaroscuro",
            camera="anamorphic 35mm, widescreen 2.39:1",
            mood="epic, melancholic, hopeful",
        ))
        log.info("  project set up: 2 characters + style guide")

        # 4.2 Enrich a prompt with the project context
        enriched = director.enrich_prompt(
            pid, "the dragon watches the village from the cliff",
            model_hint="flux-dev",
        )
        log.info(f"  enriched prompt: {enriched[:200]}...")

        # 4.3 Plan a shot list
        shots = director.plan_shot_list(
            pid, "an 8-shot reveal sequence for the dragon's decision",
            num_shots=4,
        )
        log.info(f"  planned {len(shots)} shots:")
        for s in shots:
            log.info(f"    shot {s['shot']}: {s.get('angle', '?')} - {s.get('framing', '?')}")

        # 4.4 Record a decision
        director.record_decision(
            pid, "dragon_wing_state", "torn left wing",
            rationale="shows vulnerability and history",
        )
        log.info("  recorded decision: dragon_wing_state = 'torn left wing'")

        # 4.5 Build a moodboard from reference images
        refs_dir = tmp / "refs"
        refs_dir.mkdir()
        for name, color in [
            ("golden_hour.png", (220, 170, 80)),
            ("dark_forest.png", (40, 60, 30)),
            ("dragon_scale.png", (60, 120, 80)),
        ]:
            make_ref_image(refs_dir / name, name.replace(".png", ""), color)

        builder = MoodboardBuilder()
        mb = builder.build(
            list(refs_dir.glob("*.png")),
            title="Dragon's Perch — mood anchor",
            output_dir=tmp / "moodboards",
        )
        log.info(f"  moodboard built: palette={mb.palette[:3]}, keywords={mb.keywords[:4]}")
        log.info(f"    anchor image: {mb.anchor_image_path}")

        # 4.6 Build an animatic from generated frames
        # We need real images; copy the refs as fake frames
        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        for i, src in enumerate(sorted(refs_dir.glob("*.png"))):
            shutil.copy(src, frames_dir / f"frame_{i:02d}.png")

        records = [
            ImageRecord(path=str(p)) for p in sorted(frames_dir.glob("*.png"))
        ]
        from directo.director import from_gallery
        proj = from_gallery(records, title="Dragon's Perch animatic")
        for i, clip in enumerate(proj.clips):
            clip.duration_s = 0.5
            clip.zoom_end = 1.15

        if shutil.which("ffmpeg"):
            out = tmp / "animatic.mp4"
            AnimaticBuilder().build(proj, out)
            # Copy to working dir for inspection
            demo_out = Path("demo_phases234_output")
            demo_out.mkdir(exist_ok=True)
            shutil.copy(out, demo_out / "animatic.mp4")
            log.info(f"  animatic: {out} ({out.stat().st_size:,} bytes)")
        else:
            log.warning("  ffmpeg not installed; skipping animatic render")

        mem.close()
        cs.close()

    log.info("\n" + "=" * 70)
    log.info("✓ Phases 2-4 demo complete")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
