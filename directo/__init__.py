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

from directo.cinema import (
    CanvasStore,
    CinemaEngine,
    DialogueLine,
    EngineReport,
    Panel,
    Rule,
    RuleKind,
    RuleResult,
    Scene,
    StoryboardCanvas,
    load_text_from_file,
    parse_fountain,
    parse_plain_text,
    parse_script,
    parse_script_text,
    scenes_to_prompts,
)
from directo.creative import (
    GalleryView,
    GenerationStrategy,
    ImageHistory,
    Reference,
    ReferenceKind,
    ReferenceLibrary,
    Variant,
    VariantLock,
    VariantSet,
    VariantStore,
    ViewLayout,
)
from directo.director import (
    AIVideoBackend,
    AnimaticBuilder,
    AnimaticClip,
    AnimaticProject,
    Character,
    CreativeDirector,
    Decision,
    LatentSpaceExplorer,
    LLMBackend,
    MoodAnchor,
    Moodboard,
    MoodboardBuilder,
    ProjectMemory,
    SlerpGrid,
    StyleGuide,
    TemplateBackend,
    from_gallery,
    make_backend,
)
from directo.gallery import Gallery, ImageRecord
from directo.observability import (
    MetricsCollector,
    bind_context,
    configure_logging,
    correlation_id_var,
    get_logger,
)
from directo.platform import (
    BackupManager,
    BackupResult,
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
    Webhook,
    WebhookManager,
    list_registered_migrations,
    load_plugin,
    loaded_plugins,
    register_migrations,
    reset_plugins,
    unload_plugin,
)
from directo.queue import Job, JobState, PersistentQueue, Worker
from directo.scale import (
    ComfyUINode,
    EnhancementResult,
    GPUInfo,
    LLMProvider,
    NodeHealth,
    NodeRegistry,
    Preset,
    PresetStore,
    PromptEnhancer,
    QuantLevel,
    TargetModel,
    TemplateEnhancer,
    VRAMProfile,
    detect_gpus,
    profile,
)
from directo.vault import CredentialVault

__version__ = "1.1.6"

__all__ = [
    "AIVideoBackend",
    "AnimaticBuilder",
    "AnimaticClip",
    "AnimaticProject",
    # platform (Phase 5)
    "BackupManager",
    "BackupResult",
    "CacheLayer",
    "CanvasStore",
    # director (Phase 4)
    "Character",
    # cinema (Phase 3)
    "CinemaEngine",
    # scale (Phase 2)
    "ComfyUINode",
    "CreativeDirector",
    # vault
    "CredentialVault",
    "Decision",
    "DialogueLine",
    "EngineReport",
    "EnhancementResult",
    "Event",
    "EventBus",
    "EventKind",
    "GPUInfo",
    # gallery
    "Gallery",
    "GalleryView",
    "GenerationStrategy",
    "ImageCache",
    "ImageHistory",
    "ImageRecord",
    "Job",
    "JobState",
    "LLMBackend",
    "LLMProvider",
    "LatentSpaceExplorer",
    "MetricsCollector",
    "Migration",
    "MigrationError",
    "MigrationManager",
    "MoodAnchor",
    "Moodboard",
    "MoodboardBuilder",
    "MultiBackup",
    "NodeHealth",
    "NodeRegistry",
    "Panel",
    # queue
    "PersistentQueue",
    "PluginHooks",
    "Preset",
    "PresetStore",
    "ProjectMemory",
    "PromptCache",
    "PromptEnhancer",
    "QuantLevel",
    "Reference",
    "ReferenceKind",
    "ReferenceLibrary",
    "Rule",
    "RuleKind",
    "RuleResult",
    "Scene",
    "SlerpGrid",
    "StoryboardCanvas",
    "StyleGuide",
    "TargetModel",
    "TemplateBackend",
    "TemplateEnhancer",
    "VRAMProfile",
    "Variant",
    "VariantLock",
    # creative (Phase 1)
    "VariantSet",
    "VariantStore",
    "ViewLayout",
    "Webhook",
    "WebhookManager",
    "Worker",
    "__version__",
    "bind_context",
    # observability
    "configure_logging",
    "correlation_id_var",
    "detect_gpus",
    "from_gallery",
    "get_logger",
    "list_registered_migrations",
    "load_plugin",
    "load_text_from_file",
    "loaded_plugins",
    "make_backend",
    "parse_fountain",
    "parse_plain_text",
    "parse_script",
    "parse_script_text",
    "profile",
    "register_migrations",
    "reset_plugins",
    "scenes_to_prompts",
    "unload_plugin",
]
