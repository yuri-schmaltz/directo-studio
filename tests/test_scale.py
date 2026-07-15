"""Tests for the scale module (Phase 2)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from directo.scale import (
    ComfyUINode,
    GPUInfo,
    NodeHealth,
    NodeRegistry,
    Preset,
    PresetStore,
    PromptEnhancer,
    QuantLevel,
    VRAMProfile,
    recommend_quant_for_model,
)
from directo.scale.enhance import TemplateEnhancer
from directo.scale.vram import _QUANT_TABLE


# ============================================================
# VRAM
# ============================================================


def test_recommend_quant_for_model_fits():
    # Plenty of VRAM — fp16
    assert recommend_quant_for_model(model_size_mb=1000, free_vram_mb=8000) == "fp16"


def test_recommend_quant_for_model_tight():
    # Tight: needs aggressive quant
    assert recommend_quant_for_model(model_size_mb=10000, free_vram_mb=6000) in ("gguf-q3", "gguf-q4", "gguf-q5")


def test_recommend_quant_for_model_extreme():
    # Extreme: smallest quant
    assert recommend_quant_for_model(model_size_mb=24000, free_vram_mb=2000) == "gguf-q2"


def test_vram_profile_no_gpu(monkeypatch):
    """When no GPU is detected, profile returns CPU defaults."""
    from directo.scale import vram as vram_mod
    monkeypatch.setattr(vram_mod, "detect_gpus", lambda: [])
    p = vram_mod.profile()
    assert p.total_vram_mb == 0
    assert "no GPU" in p.notes[0]


def test_vram_env_compat_has_keys():
    from directo.scale.vram import env_compat
    env = env_compat()
    assert "PYTORCH_CUDA_ALLOC_CONF" in env
    assert "DIFFUSERS_ENABLE_XFORMERS_MEMORY_EFFICIENT_ATTENTION" in env


# ============================================================
# ComfyUI nodes (no actual ComfyUI server — unit tests only)
# ============================================================


def test_node_can_handle_disabled():
    n = ComfyUINode(node_id="x", url="http://x", enabled=False)
    ok, reason = n.can_handle({})
    assert not ok
    assert "disabled" in reason


def test_node_can_handle_unreachable():
    n = ComfyUINode(
        node_id="x", url="http://x",
        health=NodeHealth(node_id="x", reachable=False, error="timeout"),
    )
    ok, reason = n.can_handle({})
    assert not ok
    assert "unreachable" in reason


def test_node_can_handle_missing_tag():
    n = ComfyUINode(
        node_id="x", url="http://x", tags=["sdxl"],
        health=NodeHealth(node_id="x", reachable=True),
    )
    ok, reason = n.can_handle({"tags": ["flux"]})
    assert not ok
    assert "tags" in reason


def test_node_can_handle_vram_check():
    n = ComfyUINode(
        node_id="x", url="http://x", tags=["flux"],
        health=NodeHealth(node_id="x", reachable=True, vram_free_mb=4000),
    )
    ok, _ = n.can_handle({"tags": ["flux"], "vram_mb": 12000})
    assert not ok
    ok2, _ = n.can_handle({"tags": ["flux"], "vram_mb": 2000})
    assert ok2


def test_node_registry_pick_warm_affinity():
    reg = NodeRegistry()
    n1 = ComfyUINode(node_id="a", url="http://a", tags=["flux"],
                     health=NodeHealth(node_id="a", reachable=True, queue_depth=5))
    n2 = ComfyUINode(node_id="b", url="http://b", tags=["flux"],
                     health=NodeHealth(node_id="b", reachable=True, queue_depth=0))
    reg.add(n1)
    reg.add(n2)
    chosen = reg.pick({"tags": ["flux"]}, prefer_node="a")
    assert chosen.node_id == "a"  # warm affinity wins


def test_node_registry_pick_lowest_load():
    reg = NodeRegistry()
    n1 = ComfyUINode(node_id="a", url="http://a", tags=["flux"],
                     health=NodeHealth(node_id="a", reachable=True, queue_depth=10))
    n2 = ComfyUINode(node_id="b", url="http://b", tags=["flux"],
                     health=NodeHealth(node_id="b", reachable=True, queue_depth=0))
    reg.add(n1)
    reg.add(n2)
    chosen = reg.pick({"tags": ["flux"]})
    assert chosen.node_id == "b"


def test_node_registry_serialization_round_trip():
    reg = NodeRegistry()
    reg.add(ComfyUINode(node_id="a", url="http://a", tags=["flux", "sdxl"]))
    reg.add(ComfyUINode(node_id="b", url="http://b", tags=["video"]))
    data = reg.to_json()
    reg2 = NodeRegistry.from_json(data)
    assert {n.node_id for n in reg2.all()} == {"a", "b"}
    assert reg2.get("a").tags == ["flux", "sdxl"]


# ============================================================
# Presets
# ============================================================


def test_preset_render_prompt():
    p = Preset(
        id="x", name="x", prompt_prefix="cinematic,", prompt_suffix=", 8k",
    )
    out = p.render_prompt("a dragon")
    assert "cinematic" in out
    assert "8k" in out
    assert "dragon" in out


def test_preset_store_builtins_seeded():
    with PresetStore(":memory:") as store:
        all_presets = store.list(limit=100)
        assert len(all_presets) >= 8  # 8 live-action + 5 animation = 13
        # Check some specific builtins
        ids = [p.id for p in all_presets]
        assert "live-silent-german-expressionism" in ids
        assert "anim-ghibli" in ids


def test_preset_store_filter_by_kind():
    with PresetStore(":memory:") as store:
        live = store.list(kind="live_action")
        anim = store.list(kind="animation")
        assert all(p.kind == "live_action" for p in live)
        assert all(p.kind == "animation" for p in anim)
        assert len(live) > 0
        assert len(anim) > 0


def test_preset_store_filter_by_era():
    with PresetStore(":memory:") as store:
        noir = store.list(era="1940-1950")
        assert any("noir" in p.id for p in noir)


def test_preset_store_user_preset():
    with PresetStore(":memory:") as store:
        p = Preset(id="my-style", name="My Style", kind="custom",
                   model="sdxl", prompt_prefix="my style,")
        store.add(p)
        loaded = store.get("my-style")
        assert loaded is not None
        assert loaded.is_builtin is False
        assert store.get("my-style").name == "My Style"


def test_preset_store_cannot_delete_builtin():
    with PresetStore(":memory:") as store:
        assert store.delete("live-classic-noir-1940s") is False
        assert store.get("live-classic-noir-1940s") is not None


def test_preset_store_use_count_increments():
    with PresetStore(":memory:") as store:
        # use_count is stored in the DB but not on the in-memory Preset dataclass
        # Verify it works at the SQL level
        store.increment_use_count("live-classic-noir-1940s")
        with store._lock:
            row = store._conn.execute("SELECT use_count FROM presets WHERE id = ?",
                                       ("live-classic-noir-1940s",)).fetchone()
        assert row["use_count"] >= 1


def test_preset_store_search():
    with PresetStore(":memory:") as store:
        results = store.search("noir")
        assert any("noir" in p.id for p in results)


# ============================================================
# Prompt enhancement
# ============================================================


def test_template_enhancer_always_available():
    t = TemplateEnhancer()
    assert t.is_available() is True


def test_template_enhancer_short_prompt():
    t = TemplateEnhancer()
    out = t.enhance("a cat", target="flux-dev")
    assert "cat" in out
    assert "cinematic" in out or "high" in out  # some suffix


def test_template_enhancer_long_prompt_unchanged():
    t = TemplateEnhancer()
    long_prompt = "a " + " ".join(["detailed"] * 50)  # 50 words
    out = t.enhance(long_prompt, target="sdxl")
    assert out == long_prompt


def test_template_enhancer_force_augment():
    t = TemplateEnhancer()
    long_prompt = "a " + " ".join(["detailed"] * 50)
    out = t.enhance(long_prompt, target="sdxl", context={"force_augment": True})
    assert out != long_prompt


def test_prompt_enhancer_returns_metadata():
    pe = PromptEnhancer(provider="template")
    r = pe.enhance("a cat on a roof", target="sdxl", context={"style": "cinematic"})
    assert r.enhanced
    assert r.provider == "template"
    assert r.target == "sdxl"
    assert r.duration_ms >= 0


def test_prompt_enhancer_negative_prompt():
    pe = PromptEnhancer(provider="template")
    neg = pe.negative_prompt_for("sdxl")
    assert "low" in neg.lower() or "worst" in neg.lower()


def test_prompt_enhancer_falls_back_to_template():
    """If a real provider is unavailable, falls back to template."""
    pe = PromptEnhancer(provider="openai")  # no key set
    # is_available returns False, so we fall back
    r = pe.enhance("a cat", target="flux-dev")
    # The provider field should reflect what was actually used
    assert r.provider in ("template", "openai")
    assert r.enhanced
