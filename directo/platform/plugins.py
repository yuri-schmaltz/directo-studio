"""Plugin system for Directo.

A plugin is a Python module that exposes a ``register(hooks)`` function.
When the plugin is loaded, ``register(hooks)`` is called and the plugin
uses :class:`PluginHooks` to subscribe to lifecycle events and
register custom components (LLM providers, video backends, presets,
canvas exporters, etc.).

The plugin system is intentionally simple — no entry_points, no
packaging magic. Users explicitly call :func:`load_plugin` with the
module path or a callable. This keeps the surface small and
debuggable.

Typical use case: a studio has its own "house style" preset pack.
They package it as a module::

    # my_studio_plugin.py
    def register(hooks: PluginHooks) -> None:
        # Add a custom preset
        hooks.register_preset(Preset(
            id="house-style",
            name="Studio House Style",
            kind="custom",
            model="flux-dev",
            prompt_prefix="in the style of our studio",
        ))
        # Listen to events
        hooks.on(EventKind.IMAGE_ADDED, log_to_slack)

Then in the host app::

    from directo.platform.plugins import load_plugin
    load_plugin("my_studio_plugin")
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable, TYPE_CHECKING

from directo.observability import get_logger
from directo.platform.events import AsyncListener, Event, EventKind

if TYPE_CHECKING:
    from directo.cinema import CinemaEngine
    from directo.director.animatic import VideoBackend
    from directo.director.moodboard import MoodAnchor
    from directo.gallery import ImageRecord
    from directo.creative.references import Reference
    from directo.scale.enhance import LLMProvider
    from directo.scale.presets import Preset
    from directo.creative.variants import VariantSet

log = get_logger("directo.platform.plugins")


class PluginHooks:
    """The interface a plugin uses to interact with Directo.

    Plugins receive a ``PluginHooks`` instance in their ``register()``
    function and call methods on it to subscribe to events or register
    custom components.
    """

    def __init__(self) -> None:
        self._event_listeners: list[tuple[EventKind, AsyncListener]] = []
        self._presets: list["Preset"] = []
        self._llm_providers: list["LLMProvider"] = []
        self._video_backends: list["VideoBackend"] = []
        self._canvas_exporters: list[Callable[[Any, str], None]] = []
        self._reference_resolvers: list[Callable[[str], "Reference | None"]] = []
        self._cost_multipliers: dict[str, float] = {}
        self._cinema_rule_packs: list[tuple[str, Callable[[str, dict], list]]] = []
        self._variant_strategies: list[tuple[str, Callable[..., Any]]] = []
        # Custom hook storage — plugins can add their own
        self._custom: dict[str, Any] = {}

    # ----------------- Events -----------------

    def on(self, kind: EventKind, listener: AsyncListener) -> None:
        """Subscribe to an event kind.

        The listener is an async function: ``async def listener(event: Event) -> None``.
        """
        if not inspect.iscoroutinefunction(listener):
            raise TypeError(f"event listener must be async; got {type(listener).__name__}")
        self._event_listeners.append((kind, listener))

    def on_all(self, listener: AsyncListener) -> None:
        self.on(EventKind.CUSTOM, listener)  # placeholder; will be wired by loader

    # ----------------- Component registration -----------------

    def register_preset(self, preset: "Preset") -> None:
        self._presets.append(preset)
        log.info(f"plugin registered preset: {preset.id}")

    def register_llm_provider(self, provider: "LLMProvider") -> None:
        self._llm_providers.append(provider)
        log.info(f"plugin registered LLM provider: {provider.name}")

    def register_video_backend(self, backend: "VideoBackend") -> None:
        self._video_backends.append(backend)
        log.info(f"plugin registered video backend: {backend.name}")

    def register_canvas_exporter(self, exporter: Callable[[Any, str], None]) -> None:
        self._canvas_exporters.append(exporter)
        log.info("plugin registered canvas exporter")

    def register_reference_resolver(self, resolver: Callable[[str], "Reference | None"]) -> None:
        self._reference_resolvers.append(resolver)
        log.info("plugin registered reference resolver")

    def register_cinema_rule_pack(
        self, name: str, rule: Callable[[str, dict], list]
    ) -> None:
        self._cinema_rule_packs.append((name, rule))
        log.info(f"plugin registered cinema rule pack: {name}")

    def register_variant_strategy(self, name: str, fn: Callable[..., Any]) -> None:
        self._variant_strategies.append((name, fn))
        log.info(f"plugin registered variant strategy: {name}")

    def set_cost_multiplier(self, kind: str, multiplier: float) -> None:
        self._cost_multipliers[kind] = multiplier

    def set_custom(self, key: str, value: Any) -> None:
        self._custom[key] = value


    def list_presets(self) -> list[str]:
        return [p.id for p in self._presets]

    def list_llm_providers(self) -> list[str]:
        return [p.name for p in self._llm_providers]

    def list_video_backends(self) -> list[str]:
        return [b.name for b in self._video_backends]
    def get_custom(self, key: str, default: Any = None) -> Any:
        return self._custom.get(key, default)

    # ----------------- Access (read-only) -----------------

    @property
    def event_listeners(self) -> list[tuple[EventKind, AsyncListener]]:
        return list(self._event_listeners)

    @property
    def presets(self) -> list["Preset"]:
        return list(self._presets)

    @property
    def llm_providers(self) -> list["LLMProvider"]:
        return list(self._llm_providers)

    @property
    def video_backends(self) -> list["VideoBackend"]:
        return list(self._video_backends)

    @property
    def canvas_exporters(self) -> list[Callable[[Any, str], None]]:
        return list(self._canvas_exporters)

    @property
    def reference_resolvers(self) -> list[Callable[[str], "Reference | None"]]:
        return list(self._reference_resolvers)

    @property
    def cinema_rule_packs(self) -> list[tuple[str, Callable]]:
        return list(self._cinema_rule_packs)

    @property
    def variant_strategies(self) -> list[tuple[str, Callable]]:
        return list(self._variant_strategies)

    @property
    def cost_multipliers(self) -> dict[str, float]:
        return dict(self._cost_multipliers)


# =====================================================================
# Plugin loader
# =====================================================================


_loaded_plugins: dict[str, PluginHooks] = {}


def load_plugin(source: str | Callable[[PluginHooks], None]) -> PluginHooks:
    """Load a plugin and return its hooks.

    ``source`` can be:
    - A dotted module path (``"my_studio_plugin"``)
    - A callable that takes a ``PluginHooks`` and registers components

    The same plugin cannot be loaded twice (idempotent by source).
    """
    key = source if isinstance(source, str) else getattr(source, "__name__", repr(source))
    if key in _loaded_plugins:
        return _loaded_plugins[key]

    hooks = PluginHooks()
    if isinstance(source, str):
        try:
            module = importlib.import_module(source)
        except ImportError as exc:
            raise RuntimeError(f"failed to import plugin {source!r}: {exc}") from exc
        if not hasattr(module, "register"):
            raise RuntimeError(f"plugin {source!r} has no 'register' function")
        module.register(hooks)
    else:
        source(hooks)

    _loaded_plugins[key] = hooks
    log.info(f"plugin loaded: {key}")
    return hooks


def loaded_plugins() -> dict[str, PluginHooks]:
    return dict(_loaded_plugins)


def unload_plugin(key: str) -> bool:
    return _loaded_plugins.pop(key, None) is not None


def reset_plugins() -> None:
    """Clear all loaded plugins. Used in tests."""
    _loaded_plugins.clear()



# Convenience: a no-op plugin for testing
def noop_register(hooks: PluginHooks) -> None:
    pass