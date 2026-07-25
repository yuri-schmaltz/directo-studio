"""Directo — full Phase 0-5 stack.

This package provides the full Directo application stack:

Phase 0 (stabilization)
- :mod:`directo.observability` — structured logging, metrics, tracing
- :mod:`directo.vault`       — encrypted credential storage
- :mod:`directo.queue`        — persistent job queue with crash recovery
- :mod:`directo.gallery`      — image gallery with ratings, search, dedup
- :mod:`directo.printing`     — storyboard PDF export

Phase 1 (creative foundation)
- :mod:`directo.creative.variants`   — 4-options pattern
- :mod:`directo.creative.references` — style/character reference library
- :mod:`directo.creative.history`     — per-job image history + restore
- :mod:`directo.creative.views`       — multi-view HTML gallery renderer

Phase 2 (technical scale)
- :mod:`directo.scale.nodes`    — ComfyUI node registry & health
- :mod:`directo.scale.vram`     — VRAM profiling & quantisation
- :mod:`directo.scale.presets`  — visual style preset packs
- :mod:`directo.scale.enhance`  — prompt enhancement (13+ LLM providers)

Phase 3 (differentiation)
- :mod:`directo.cinema.engine`  — 19 cinematic prompt rules
- :mod:`directo.cinema.canvas`  — multi-panel storyboard canvas
- :mod:`directo.cinema.parser`  — script → scene prompts (Fountain/plain text)

Phase 4 (creative direction)
- :mod:`directo.director.agent`    — creative director agent
- :mod:`directo.director.moodboard`— colour/mood extraction
- :mod:`directo.director.slerp`    — latent-space interpolation
- :mod:`directo.director.animatic` — animatic video assembly

Phase 5 (production hardening + real-time + cloud)
- :mod:`directo.platform.migrations` — schema migrations
- :mod:`directo.platform.backup`     — backup/restore utilities
- :mod:`directo.platform.costs`       — cost tracking
- :mod:`directo.platform.cache`       — prompt + image caches
- :mod:`directo.platform.events`      — event bus + webhooks
- :mod:`directo.platform.plugins`     — plugin system
- :mod:`directo.platform.api`         — HTTP API (FastAPI) + WebSocket
- :mod:`directo.platform.cli`         — Click-based CLI

All modules are designed to be drop-in: zero required external services
(except optional FastAPI/uvicorn/click for HTTP+CLI), SQLite-backed by
default, and can be integrated into existing FastAPI / asyncio /
desktop applications.
"""

from directo.observability import (
    configure_logging,
    get_logger,
    MetricsCollector,
    bind_context,
    correlation_id_var,
)
from directo.vault import CredentialVault
from directo.queue import PersistentQueue, Job, JobState, Worker
from directo.gallery import Gallery, ImageRecord

from directo.scale import (
    ComfyUINode, NodeHealth, NodeRegistry,
    GPUInfo, QuantLevel, VRAMProfile, detect_gpus, profile,
    Preset, PresetStore,
    EnhancementResult, LLMProvider, PromptEnhancer, TargetModel,
    TemplateEnhancer,
)
from directo.cinema import (
    CinemaEngine, EngineReport, Rule, RuleKind, RuleResult,
    CanvasStore, Panel, StoryboardCanvas,
    DialogueLine, Scene,
    parse_fountain, parse_plain_text, parse_script, parse_script_text,
    scenes_to_prompts, load_text_from_file,
)
from directo.director import (
    Character, CreativeDirector, Decision, LLMBackend,
    ProjectMemory, StyleGuide,
    TemplateBackend, make_backend,
    MoodAnchor, Moodboard, MoodboardBuilder,
    LatentSpaceExplorer, SlerpGrid,
    AnimaticBuilder, AnimaticClip, AnimaticProject, from_gallery,
)

from directo.platform import (
    BackupManager, BackupResult, MultiBackup,
    CostKind, CostRecord, CostTracker, DEFAULT_PRICES,
    CacheLayer, ImageCache, PromptCache,
    Event, EventBus, EventKind, Webhook, WebhookManager,
    Migration, MigrationError, MigrationManager,
    PluginHooks, load_plugin, loaded_plugins, unload_plugin, reset_plugins,
    register_migrations, list_registered_migrations,
)

from directo.creative import (
    VariantSet,
    Variant,
    VariantLock,
    VariantStore,
    GenerationStrategy,
    Reference,
    ReferenceKind,
    ReferenceLibrary,
    ImageHistory,
    GalleryView,
    ViewLayout,
)

__version__ = "1.1.1"

__all__ = [
    # observability
    "configure_logging", "get_logger", "MetricsCollector",
    "bind_context", "correlation_id_var",
    # vault
    "CredentialVault",
    # queue
    "PersistentQueue", "Job", "JobState", "Worker",
    # gallery
    "Gallery", "ImageRecord",
    # creative (Phase 1)
    "VariantSet", "Variant", "VariantLock", "VariantStore",
    "GenerationStrategy",
    "Reference", "ReferenceKind", "ReferenceLibrary",
    "ImageHistory", "GalleryView", "ViewLayout",
    # scale (Phase 2)
    "ComfyUINode", "NodeHealth", "NodeRegistry",
    "GPUInfo", "QuantLevel", "VRAMProfile",
    "detect_gpus", "profile",
    "Preset", "PresetStore",
    "EnhancementResult", "LLMProvider", "PromptEnhancer",
    "TargetModel", "TemplateEnhancer",
    # cinema (Phase 3)
    "CinemaEngine", "EngineReport", "Rule", "RuleKind", "RuleResult",
    "CanvasStore", "Panel", "StoryboardCanvas",
    "DialogueLine", "Scene",
    "parse_fountain", "parse_plain_text", "parse_script",
    "parse_script_text", "scenes_to_prompts", "load_text_from_file",
    # director (Phase 4)
    "Character", "CreativeDirector", "Decision", "LLMBackend",
    "ProjectMemory", "StyleGuide",
    "TemplateBackend", "make_backend",
    "MoodAnchor", "Moodboard", "MoodboardBuilder",
    "LatentSpaceExplorer", "SlerpGrid",
    "AnimaticBuilder", "AnimaticClip", "AnimaticProject", "from_gallery",
    # platform (Phase 5)
    "BackupManager", "BackupResult", "MultiBackup",
    "CostKind", "CostRecord", "CostTracker", "DEFAULT_PRICES",
    "CacheLayer", "ImageCache", "PromptCache",
    "Event", "EventBus", "EventKind", "Webhook", "WebhookManager",
    "Migration", "MigrationError", "MigrationManager",
    "PluginHooks", "load_plugin", "loaded_plugins", "unload_plugin",
    "reset_plugins", "register_migrations", "list_registered_migrations",
    "__version__",
]
