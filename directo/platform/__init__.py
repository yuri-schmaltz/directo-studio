"""Platform module (Phase 5): production hardening + real-time + cloud.

Modules:
- :mod:`directo.platform.migrations` — schema migrations
- :mod:`directo.platform.backup`     — backup/restore utilities
- :mod:`directo.platform.costs`       — cost tracking
- :mod:`directo.platform.cache`       — prompt + image caches
- :mod:`directo.platform.events`      — event bus + webhooks
- :mod:`directo.platform.plugins`     — plugin system
- :mod:`directo.platform.api`         — HTTP API (FastAPI) + WebSocket
- :mod:`directo.platform.cli`         — Click-based CLI
- :mod:`directo.platform.gui`          — Streamlit web dashboard
"""

from directo.platform.migrations import (
    Migration,
    MigrationError,
    MigrationManager,
    register_migrations,
    list_registered_migrations,
)
from directo.platform.backup import BackupManager, BackupResult, MultiBackup
from directo.platform.costs import (
    CostKind,
    CostRecord,
    CostTracker,
    DEFAULT_PRICES,
)
from directo.platform.cache import (
    CacheLayer,
    ImageCache,
    PromptCache,
)
from directo.platform.events import (
    AsyncListener,
    Event,
    EventBus,
    EventKind,
    Webhook,
    WebhookManager,
)
from directo.platform.plugins import (
    PluginHooks,
    load_plugin,
    loaded_plugins,
    noop_register,
    reset_plugins,
    unload_plugin,
)
from directo.platform.gui import main as gui_main, run as gui_run

__all__ = [
    # migrations
    "Migration", "MigrationError", "MigrationManager",
    "register_migrations", "list_registered_migrations",
    # backup
    "BackupManager", "BackupResult", "MultiBackup",
    # costs
    "CostKind", "CostRecord", "CostTracker", "DEFAULT_PRICES",
    # cache
    "CacheLayer", "ImageCache", "PromptCache",
    # events
    "AsyncListener", "Event", "EventBus", "EventKind", "Webhook", "WebhookManager",
    # plugins
    "PluginHooks", "load_plugin", "loaded_plugins", "noop_register",
    "reset_plugins", "unload_plugin",
    # gui
    "gui_main", "gui_run",
]
