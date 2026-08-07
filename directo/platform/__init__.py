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

from directo.platform.backup import BackupManager, BackupResult, MultiBackup
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
from directo.platform.migrations import (
    Migration,
    MigrationError,
    MigrationManager,
    list_registered_migrations,
    register_migrations,
)
from directo.platform.plugins import (
    PluginHooks,
    load_plugin,
    loaded_plugins,
    noop_register,
    reset_plugins,
    unload_plugin,
)


def gui_main(*args, **kwargs):
    from directo.platform.gui import main
    return main(*args, **kwargs)

def gui_run(*args, **kwargs):
    from directo.platform.gui import run
    return run(*args, **kwargs)

__all__ = [
    # events
    "AsyncListener",
    # backup
    "BackupManager",
    "BackupResult",
    # cache
    "CacheLayer",
    "Event",
    "EventBus",
    "EventKind",
    "ImageCache",
    # migrations
    "Migration",
    "MigrationError",
    "MigrationManager",
    "MultiBackup",
    # plugins
    "PluginHooks",
    "PromptCache",
    "Webhook",
    "WebhookManager",
    # gui
    "gui_main",
    "gui_run",
    "list_registered_migrations",
    "load_plugin",
    "loaded_plugins",
    "noop_register",
    "register_migrations",
    "reset_plugins",
    "unload_plugin",
]
