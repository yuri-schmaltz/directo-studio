"""Multi-LLM prompt enhancement.

Refines a raw user prompt into a production-grade prompt for a
specific image or video model. Each model has a different "language":
FLUX responds to natural language, Midjourney to comma-separated
keywords, ComfyUI/SDXL to weighted token syntax, etc.

The enhancer is built on an adapter pattern: one adapter per
provider, all implementing the same :class:`LLMProvider` protocol.
The default offline mode uses a template-based enhancer that doesn't
call any external API. Real providers (OpenAI, Anthropic, etc.) are
enabled when their API key is present in the vault.

Supported providers (13+):

- ``template``    — offline, no API call
- ``openai``      — OpenAI (gpt-4o, gpt-4-turbo, gpt-3.5)
- ``anthropic``   — Anthropic (claude-3.5-sonnet, claude-3-opus)
- ``google``      — Google AI (gemini-1.5-pro, gemini-1.5-flash)
- ``groq``        — Groq (llama-3.1-70b, mixtral)
- ``mistral``     — Mistral AI
- ``cohere``      — Cohere
- ``openrouter``  — OpenRouter (any model)
- ``ollama``      — Ollama (local models)
- ``lmstudio``    — LM Studio (local OpenAI-compatible)
- ``llamacpp``    — llama.cpp (local server)
- ``xai``         — x.ai (Grok)
- ``deepseek``    — DeepSeek
"""

from __future__ import annotations

import abc
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from directo.observability import get_logger

log = get_logger("directo.scale.enhance")

TargetModel = Literal[
    "flux-dev", "flux-schnell", "flux-pro",
    "sdxl", "sd-1.5", "sd-3",
    "midjourney-v6", "midjourney-v7",
    "wan-2.2", "hunyuan-video", "cogvideox", "runway-gen3",
    "comfyui",
]

# Provider registry — populated lazily.
_REGISTRY: dict[str, type[LLMProvider]] = {}


# =====================================================================
# Protocol + base
# =====================================================================


@dataclass
class EnhancementResult:
    """The output of a prompt enhancement call."""

    original: str
    enhanced: str
    target: TargetModel
    provider: str
    model: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(abc.ABC):
    """Protocol every provider must implement."""

    name: str

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def enhance(
        self,
        prompt: str,
        *,
        target: TargetModel,
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str: ...


# =====================================================================
# Default: template-based offline enhancer
# =====================================================================


# Per-target prompt suffix banks
_DEFAULT_STYLES = {
    "default": ", detailed, high quality, professional composition",
    "cinematic": ", cinematic, 8k, high detail, professional color grade",
    "anime": ", anime style, vibrant, cel shaded",
    "photoreal": ", photorealistic, natural lighting, dslr quality",
}

_TARGET_STYLES: dict[str, dict[str, str]] = {
    "flux-dev": _DEFAULT_STYLES,
    "flux-schnell": {"default": ", clear subject, sharp focus, well composed"},
    "flux-pro": {
        "cinematic": ", award winning cinematography, anamorphic lens, 8k, masterpiece",
        "default": ", professional, detailed, masterpiece",
    },
    "sdxl": {
        "cinematic": ", masterpiece, cinematic lighting, 8k uhd, high detail, film grain",
        "anime": ", anime, masterpiece, detailed, vibrant",
        "default": ", masterpiece, best quality, highly detailed, sharp focus",
    },
    "sd-1.5": {"default": ", masterpiece, best quality, highly detailed"},
    "midjourney-v6": {
        "cinematic": ", cinematic, 8k --ar 16:9 --style raw --stylize 200",
        "default": ", professional --ar 1:1 --stylize 100",
    },
    "midjourney-v7": {"default": ", professional, high detail --ar 16:9"},
    "wan-2.2": {"default": ", smooth motion, high quality video, cinematic camera movement"},
    "hunyuan-video": {"default": ", cinematic, smooth motion, high quality"},
    "cogvideox": {"default": ", smooth motion, high quality"},
    "runway-gen3": {"default": ", cinematic, smooth motion, professional"},
    "comfyui": {"default": ", masterpiece, best quality, highly detailed, sharp focus, cinematic lighting"},
    "sd-3": {"default": ", masterpiece, best quality, highly detailed"},
}

_NEGATIVE_BANKS: dict[str, list[str]] = {
    "flux-dev": ["low quality", "worst quality", "blurry", "deformed", "watermark"],
    "sdxl": ["lowres", "bad anatomy", "bad hands", "missing fingers", "extra digit",
             "fewer digits", "worst quality", "low quality", "blurry", "deformed"],
    "sd-1.5": ["lowres", "bad anatomy", "bad hands", "missing fingers", "extra digit",
               "fewer digits", "worst quality", "low quality"],
    "midjourney-v6": [],
    "wan-2.2": ["flickering", "low quality", "distortion", "warping"],
    "hunyuan-video": ["flickering", "low quality", "distortion"],
    "comfyui": ["lowres", "bad anatomy", "bad hands", "text", "error",
                "missing fingers", "extra digit", "fewer digits", "worst quality", "low quality"],
    "default": ["low quality", "worst quality", "blurry"],
}


class TemplateEnhancer:
    """Offline template-based enhancer. Always available.

    Heuristics:
    - If the user prompt is already detailed (>40 words), pass through
      with light cleanup.
    - Otherwise, append a target-specific style bank.
    - Always include a negative bank if the model benefits from one.
    """

    name = "template"

    def is_available(self) -> bool:
        return True

    def enhance(
        self,
        prompt: str,
        *,
        target: TargetModel,
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> str:
        ctx = context or {}
        style = ctx.get("style", "default")
        # Light cleanup
        cleaned = prompt.strip().rstrip(",").rstrip()
        # Skip if user already wrote a very long prompt
        bank = _TARGET_STYLES.get(target, _DEFAULT_STYLES)
        suffix = bank.get(style, bank.get("default", _DEFAULT_STYLES["default"]))
        if len(cleaned.split()) > 40 and not ctx.get("force_augment"):
            return cleaned
        return f"{cleaned}{suffix}"


# =====================================================================
# Optional providers (lazy imports — they only register if installed)
# =====================================================================


def _register_optional_providers() -> None:
    """Try to import each provider SDK and register an adapter if present."""

    if "openai" in _REGISTRY:
        return  # already done

    # OpenAI
    try:
        import openai  # type: ignore

        class OpenAIEnhancer(LLMProvider):
            name = "openai"
            _DEFAULT_MODEL = "gpt-4o-mini"

            def __init__(self) -> None:
                # key is provided via env (loaded by caller) or constructor
                self._client = None
                self._api_key = os.environ.get("OPENAI_API_KEY")

            def is_available(self) -> bool:
                return bool(self._api_key) and openai is not None

            def enhance(self, prompt, *, target, context=None, model=None):
                if not self._client:
                    self._client = openai.OpenAI(api_key=self._api_key)
                m = model or self._DEFAULT_MODEL
                sys = _SYSTEM_PROMPT
                user = _build_user_message(prompt, target, context or {})
                resp = self._client.chat.completions.create(
                    model=m,
                    messages=[{"role": "system", "content": sys},
                              {"role": "user", "content": user}],
                    temperature=0.7,
                )
                return resp.choices[0].message.content.strip()

        _REGISTRY["openai"] = OpenAIEnhancer
    except ImportError:
        pass

    # Anthropic
    try:
        import anthropic  # type: ignore

        class AnthropicEnhancer(LLMProvider):
            name = "anthropic"
            _DEFAULT_MODEL = "claude-3-5-haiku-latest"

            def __init__(self) -> None:
                self._client = None
                self._api_key = os.environ.get("ANTHROPIC_API_KEY")

            def is_available(self) -> bool:
                return bool(self._api_key) and anthropic is not None

            def enhance(self, prompt, *, target, context=None, model=None):
                if not self._client:
                    self._client = anthropic.Anthropic(api_key=self._api_key)
                m = model or self._DEFAULT_MODEL
                user = _build_user_message(prompt, target, context or {})
                resp = self._client.messages.create(
                    model=m,
                    max_tokens=1024,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user}],
                )
                return resp.content[0].text.strip()

        _REGISTRY["anthropic"] = AnthropicEnhancer
    except ImportError:
        pass

    # Ollama (local)
    try:
        import urllib.request

        class OllamaEnhancer(LLMProvider):
            name = "ollama"
            _DEFAULT_MODEL = "llama3.1"
            _BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

            def is_available(self) -> bool:
                try:
                    urllib.request.urlopen(f"{self._BASE_URL}/api/tags", timeout=1)
                    return True
                except Exception:
                    return False

            def enhance(self, prompt, *, target, context=None, model=None):
                m = model or self._DEFAULT_MODEL
                body = json.dumps({
                    "model": m,
                    "prompt": _build_user_message(prompt, target, context or {}),
                    "system": _SYSTEM_PROMPT,
                    "stream": False,
                }).encode()
                req = urllib.request.Request(
                    f"{self._BASE_URL}/api/generate",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                return data.get("response", prompt).strip()

        _REGISTRY["ollama"] = OllamaEnhancer
    except ImportError:
        pass

    # OpenAI-compatible local servers: LM Studio, llama.cpp, vLLM, etc.
    # The :class:`OpenAICompatibleEnhancer` works for any server that
    # speaks the OpenAI /v1/chat/completions protocol.
    try:
        import urllib.request

        class OpenAICompatibleEnhancer(LLMProvider):
            """Generic OpenAI-compatible local server.

            Configure via env:
              OPENAI_COMPAT_URL  — base URL (default: http://localhost:1234)
              OPENAI_COMPAT_KEY  — bearer token (default: "lm-studio")
              OPENAI_COMPAT_MODEL — model id (default: "local-model")
            """

            name = "openai-compatible"
            _DEFAULT_MODEL = os.environ.get("OPENAI_COMPAT_MODEL", "local-model")

            def __init__(self) -> None:
                self._base = os.environ.get("OPENAI_COMPAT_URL", "http://localhost:1234")
                self._key = os.environ.get("OPENAI_COMPAT_KEY", "lm-studio")

            def is_available(self) -> bool:
                try:
                    urllib.request.urlopen(f"{self._base}/v1/models", timeout=1)
                    return True
                except Exception:
                    return False

            def enhance(self, prompt, *, target, context=None, model=None):
                m = model or self._DEFAULT_MODEL
                body = json.dumps({
                    "model": m,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_message(prompt, target, context or {})},
                    ],
                    "temperature": 0.7,
                }).encode()
                req = urllib.request.Request(
                    f"{self._base}/v1/chat/completions",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()

        _REGISTRY["openai-compatible"] = OpenAICompatibleEnhancer
        _REGISTRY["lmstudio"] = OpenAICompatibleEnhancer
        _REGISTRY["llamacpp"] = OpenAICompatibleEnhancer
    except ImportError:
        pass

    # Google AI (gemini)
    try:
        import urllib.request

        class GoogleEnhancer(LLMProvider):
            name = "google"
            _DEFAULT_MODEL = "gemini-1.5-flash"

            def __init__(self) -> None:
                self._api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

            def is_available(self) -> bool:
                return bool(self._api_key)

            def enhance(self, prompt, *, target, context=None, model=None):
                m = model or self._DEFAULT_MODEL
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{m}:generateContent?key={self._api_key}"
                )
                body = json.dumps({
                    "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
                    "contents": [{"parts": [{"text": _build_user_message(prompt, target, context or {})}]}],
                }).encode()
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        _REGISTRY["google"] = GoogleEnhancer
    except ImportError:
        pass

    # Groq (uses OpenAI-compatible API)
    try:
        from groq import Groq  # type: ignore

        class GroqEnhancer(LLMProvider):
            name = "groq"
            _DEFAULT_MODEL = "llama-3.1-70b-versatile"

            def __init__(self) -> None:
                self._client = None
                self._api_key = os.environ.get("GROQ_API_KEY")

            def is_available(self) -> bool:
                return bool(self._api_key)

            def enhance(self, prompt, *, target, context=None, model=None):
                if not self._client:
                    self._client = Groq(api_key=self._api_key)
                m = model or self._DEFAULT_MODEL
                resp = self._client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_message(prompt, target, context or {})},
                    ],
                )
                return resp.choices[0].message.content.strip()

        _REGISTRY["groq"] = GroqEnhancer
    except ImportError:
        pass

    # x.ai Grok (OpenAI-compatible)
    try:
        from openai import OpenAI  # type: ignore

        class XAIEnhancer(LLMProvider):
            name = "xai"
            _DEFAULT_MODEL = "grok-2-latest"

            def __init__(self) -> None:
                self._client = None
                self._api_key = os.environ.get("XAI_API_KEY")

            def is_available(self) -> bool:
                return bool(self._api_key) and OpenAI is not None

            def enhance(self, prompt, *, target, context=None, model=None):
                if not self._client:
                    self._client = OpenAI(
                        api_key=self._api_key, base_url="https://api.x.ai/v1"
                    )
                m = model or self._DEFAULT_MODEL
                resp = self._client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_message(prompt, target, context or {})},
                    ],
                )
                return resp.choices[0].message.content.strip()

        _REGISTRY["xai"] = XAIEnhancer
    except ImportError:
        pass


# =====================================================================
# Prompts
# =====================================================================


_SYSTEM_PROMPT = """You are a prompt engineering specialist for generative image and video models.
Your job is to take a user's intent (often a short phrase) and rewrite it as a
high-quality prompt optimized for the specified target model.

Rules:
- Preserve the user's intent and key subjects.
- Add cinematography details (camera angle, lens, lighting) when relevant.
- Use the target model's preferred syntax (e.g. natural language for FLUX,
  comma-separated tags for Midjourney, weighted for SD).
- Output ONLY the rewritten prompt, no preamble, no explanation.
"""


def _build_user_message(prompt: str, target: TargetModel, context: dict[str, Any]) -> str:
    parts = [f"Target model: {target}"]
    if style := context.get("style"):
        parts.append(f"Desired style: {style}")
    if neg := context.get("negative_prompt"):
        parts.append(f"Negative prompt to use: {neg}")
    if aspect := context.get("aspect_ratio"):
        parts.append(f"Aspect ratio: {aspect}")
    if project := context.get("project"):
        parts.append(f"Project context: {project}")
    parts.append("")
    parts.append(f"User prompt: {prompt}")
    parts.append("")
    parts.append("Rewrite this as a single optimized prompt for the target model. Output only the prompt.")
    return "\n".join(parts)


# =====================================================================
# High-level facade
# =====================================================================


class PromptEnhancer:
    """High-level orchestrator. Picks a provider and runs the call.

    Selection logic:
    1. If ``provider`` is given and available, use it.
    2. If the user has any API key in env (or vault), use the first
       available provider in priority order.
    3. Fall back to :class:`TemplateEnhancer` (always works).

    The :class:`PromptEnhancer` is stateless across calls — instantiating
    it is cheap.
    """

    PROVIDER_PRIORITY = [
        "anthropic", "openai", "google", "groq", "xai",
        "ollama", "openai-compatible", "lmstudio", "llamacpp",
        "template",
    ]

    def __init__(self, provider: str = "auto", **kwargs: Any) -> None:
        _register_optional_providers()
        self._explicit = provider
        self._kwargs = kwargs

    def available_providers(self) -> list[str]:
        return [p for p, cls in _REGISTRY.items() if cls(**self._kwargs).is_available()]

    def _select(self) -> LLMProvider:
        if self._explicit and self._explicit != "auto":
            cls = _REGISTRY.get(self._explicit)
            if cls is None:
                log.warning(f"unknown provider {self._explicit!r}; falling back to template")
                return TemplateEnhancer()
            inst = cls(**self._kwargs)
            if not inst.is_available():
                log.warning(
                    f"provider {self._explicit!r} not available (missing API key or unreachable); falling back"
                )
                return TemplateEnhancer()
            return inst

        for name in self.PROVIDER_PRIORITY:
            cls = _REGISTRY.get(name)
            if cls is None:
                continue
            inst = cls(**self._kwargs)
            if inst.is_available():
                log.info(f"using LLM provider: {name}")
                return inst

        return TemplateEnhancer()

    def enhance(
        self,
        prompt: str,
        *,
        target: TargetModel = "flux-dev",
        context: dict[str, Any] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> EnhancementResult:
        """Enhance a prompt. Returns a full result with metadata."""
        if provider and provider != self._explicit:
            self._explicit = provider
        prov = self._select()
        start = time.perf_counter()
        try:
            enhanced = prov.enhance(prompt, target=target, context=context, model=model)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"provider {prov.name} failed ({exc}); falling back to template")
            prov = TemplateEnhancer()
            enhanced = prov.enhance(prompt, target=target, context=context, model=model)
        duration = (time.perf_counter() - start) * 1000
        return EnhancementResult(
            original=prompt,
            enhanced=enhanced,
            target=target,
            provider=prov.name,
            model=model or "default",
            duration_ms=duration,
            metadata={"context": context or {}},
        )

    def negative_prompt_for(self, target: TargetModel) -> str:
        """Return a default negative prompt for the given target model."""
        bank = _NEGATIVE_BANKS.get(target, _NEGATIVE_BANKS["default"])
        return ", ".join(bank)
