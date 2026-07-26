"""LLM backends for the director agent.

A :class:`LLMBackend` exposes ``complete(prompt, system, ...)`` → str.
The :func:`make_backend` factory returns the best available backend
based on installed packages and configured API keys.
"""

from __future__ import annotations

import os
from typing import Any

from directo.observability import get_logger
from directo.scale.enhance import PromptEnhancer, TargetModel

log = get_logger("directo.director.backends")


class TemplateBackend:
    """Offline backend that returns a templated response.

    Doesn't actually call any LLM. Used for tests and for users who
    don't have any API key configured. The "completion" is just the
    prompt echoed back with a slight reformat.

    For real creative direction, use :class:`OpenAIBackend` (or any
    other real backend).
    """

    name = "template"

    def is_available(self) -> bool:
        return True

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        # Trivial: return the most relevant part of the user prompt
        # (anything after the last "Question:" / "Raw prompt:" / "Goal:").
        for marker in ("Question:", "Raw prompt:", "Goal:", "Rewrite"):
            if marker in prompt:
                tail = prompt.split(marker, 1)[1]
                return tail.strip()[:max_tokens]
        return prompt.strip()[:max_tokens]


class OpenAIBackend:
    """Real LLM via the OpenAI Python SDK (works for any OpenAI-compatible API)."""

    name = "openai"

    def __init__(self, *, model: str = "gpt-4o-mini", base_url: str | None = None,
                 api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = base_url
        self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        try:
            import openai  # type: ignore
            if self._client is None:
                self._client = openai.OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:  # noqa: BLE001
            log.warning(f"OpenAI backend failed: {exc}; falling back to template")
            return TemplateBackend().complete(prompt, system=system,
                                             temperature=temperature, max_tokens=max_tokens)


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, *, model: str = "claude-3-5-haiku-latest",
                 api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def is_available(self) -> bool:
        return bool(self._api_key)

    def complete(self, prompt, *, system="", temperature=0.7, max_tokens=1024):
        try:
            import anthropic  # type: ignore
            if self._client is None:
                self._client = anthropic.Anthropic(api_key=self._api_key)
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return resp.content[0].text.strip()
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Anthropic backend failed: {exc}; falling back to template")
            return TemplateBackend().complete(prompt, system=system,
                                             temperature=temperature, max_tokens=max_tokens)


class OllamaBackend:
    """Ollama local server (no API key, just localhost:11434)."""

    name = "ollama"

    def __init__(self, *, model: str | None = None,
                 base_url: str | None = None) -> None:
        self._model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")
        self._base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def is_available(self) -> bool:
        try:
            import urllib.request
            urllib.request.urlopen(f"{self._base_url}/api/tags", timeout=1)
            return True
        except Exception:
            return False

    def complete(self, prompt, *, system="", temperature=0.7, max_tokens=1024):
        try:
            import json
            import urllib.request
            body = json.dumps({
                "model": self._model,
                "prompt": prompt,
                "system": system or "You are a helpful assistant.",
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            return data.get("response", "").strip()
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Ollama backend failed: {exc}; falling back to template")
            return TemplateBackend().complete(prompt, system=system,
                                             temperature=temperature, max_tokens=max_tokens)


def make_backend(prefer: str | None = None, **kwargs: Any) -> Any:
    """Return the best available backend.

    Priority: explicit ``prefer`` > Anthropic > OpenAI > Ollama > Template.
    """
    backends: list[Any] = []
    if prefer:
        backends.append(prefer)
    for name, cls in [
        ("anthropic", AnthropicBackend),
        ("openai", OpenAIBackend),
        ("ollama", OllamaBackend),
    ]:
        if name not in [b for b in backends]:
            backends.append(name)
    backends.append("template")

    for name in backends:
        if name == "anthropic":
            b = AnthropicBackend(**kwargs)
        elif name == "openai":
            b = OpenAIBackend(**kwargs)
        elif name == "ollama":
            b = OllamaBackend(**kwargs)
        else:
            b = TemplateBackend()
        if b.is_available():
            log.info(f"using LLM backend: {b.name}")
            return b
    return TemplateBackend()


class DynamicLLMBackend:
    """An LLM backend that forwards calls to the current configured backend in settings.json."""
    name = "dynamic"

    def __init__(self, settings_path: str = "./directo_data/settings.json") -> None:
        self._settings_path = settings_path

    def _get_backend(self) -> Any:
        import json
        from pathlib import Path
        try:
            p = Path(self._settings_path)
            if p.exists():
                with open(p) as f:
                    settings = json.load(f)
                b_name = settings.get("llm_backend", "template")
                if b_name == "ollama":
                    return OllamaBackend(
                        model=settings.get("ollama_model", "llama3.1"),
                        base_url=settings.get("ollama_host", "http://localhost:11434"),
                    )
                elif b_name == "openai":
                    return OpenAIBackend(
                        model=settings.get("openai_model", "gpt-4o-mini"),
                        base_url=settings.get("openai_api_base") or None,
                        api_key=settings.get("openai_api_key") or None,
                    )
                elif b_name == "anthropic":
                    return AnthropicBackend(
                        model=settings.get("anthropic_model", "claude-3-5-sonnet-20241022"),
                        api_key=settings.get("anthropic_api_key") or None,
                    )
        except Exception as e:
            log.warning(f"Failed to load dynamic backend settings: {e}")
        return make_backend()

    def is_available(self) -> bool:
        return self._get_backend().is_available()

    def complete(self, prompt: str, *, system: str = "", temperature: float = 0.7, max_tokens: int = 1024) -> str:
        return self._get_backend().complete(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
