"""Prompt Builder subsystem for assembling positive/negative prompts from Style Bible."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from directo.style_bible.models import (
    CharacterProfile,
    EnvironmentAnchor,
    LoRAConfig,
    StyleBible,
    StyleDirective,
)


@dataclass
class PromptResult:
    """Encapsulates the output of a prompt composition operation."""

    positive_prompt: str
    negative_prompt: str
    lora_settings: List[Dict[str, Any]] = field(default_factory=list)
    seed_settings: Dict[str, Any] = field(default_factory=dict)


def _normalize_prompt_string(text: str) -> str:
    """Cleans up formatting issues in assembled prompt strings.

    - Strips leading/trailing whitespace and commas.
    - Replaces consecutive commas/spaces (e.g. ', ,' or ',,') with a single ', '.
    - Collapses multiple whitespace spaces into single space.
    """
    if not text:
        return ""
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"(,\s*)+", ", ", text)
    text = text.strip(" ,")
    text = re.sub(r" +", " ", text)
    return text


class PromptBuilder:
    """Assembles prompt strings, LoRA triggers, and seed settings from a StyleBible instance."""

    def __init__(self, style_bible: StyleBible) -> None:
        self.style_bible = style_bible

    def build_prompt(
        self,
        character_ids: Optional[List[str]] = None,
        environment_id: Optional[str] = None,
        directive_id: Optional[str] = None,
        action_prompt: str = "",
    ) -> PromptResult:
        """Build positive prompt, negative prompt, lora settings, and seed settings."""
        pos_parts: List[str] = []
        neg_parts: List[str] = []
        collected_loras: List[Dict[str, Any]] = []
        seed_settings: Dict[str, Any] = {"characters": {}}

        directive: Optional[StyleDirective] = None
        if directive_id:
            directive = self.style_bible.get_directive(directive_id)
            if directive is None:
                raise KeyError(
                    f"Directive ID '{directive_id}' not found in StyleBible directives."
                )
            if directive.global_prompt_prefix:
                pos_parts.append(directive.global_prompt_prefix)
            if directive.negative_prompt:
                neg_parts.append(directive.negative_prompt)
            if hasattr(directive, "directive_seed") and directive.directive_seed is not None:
                seed_settings["directive_seed"] = directive.directive_seed

        if character_ids:
            for char_id in character_ids:
                char = self.style_bible.get_character(char_id)
                if char is None:
                    raise KeyError(
                        f"Character ID '{char_id}' not found in StyleBible characters."
                    )
                if char.base_prompt:
                    pos_parts.append(char.base_prompt)
                if char.visual_anchors:
                    pos_parts.extend(char.visual_anchors)
                if char.loras:
                    for lora in char.loras:
                        lname = lora.name if hasattr(lora, "name") else lora.get("name")
                        lweight = lora.weight if hasattr(lora, "weight") else lora.get("weight", 1.0)
                        ltw = lora.trigger_words if hasattr(lora, "trigger_words") else lora.get("trigger_words", [])
                        collected_loras.append({
                            "name": lname,
                            "weight": lweight,
                            "trigger_words": list(ltw) if ltw else [],
                        })
                if char.seeds:
                    seed_settings["characters"][char_id] = dict(char.seeds)
                if getattr(char, "negative_prompt", None):
                    neg_parts.append(char.negative_prompt)

        if action_prompt and action_prompt.strip():
            pos_parts.append(action_prompt.strip())

        if environment_id:
            env = self.style_bible.get_environment(environment_id)
            if env is None:
                raise KeyError(
                    f"Environment ID '{environment_id}' not found in StyleBible environments."
                )
            if env.scenario_prompt:
                pos_parts.append(env.scenario_prompt)
            if env.lighting:
                pos_parts.append(env.lighting)
            if env.color_palette:
                if isinstance(env.color_palette, (list, tuple)):
                    pos_parts.extend(env.color_palette)
                else:
                    pos_parts.append(str(env.color_palette))
            if env.style_tokens:
                pos_parts.extend(env.style_tokens)
            if getattr(env, "negative_prompt", None):
                neg_parts.append(env.negative_prompt)

        if directive and directive.global_prompt_suffix:
            pos_parts.append(directive.global_prompt_suffix)

        dedup_loras: List[Dict[str, Any]] = []
        seen_lora_names = set()
        for l in collected_loras:
            if l["name"] not in seen_lora_names:
                seen_lora_names.add(l["name"])
                dedup_loras.append(l)
                pos_parts.append(f"<lora:{l['name']}:{l['weight']}>")
                for tw in l["trigger_words"]:
                    if tw and tw not in pos_parts:
                        pos_parts.append(tw)

        raw_pos = ", ".join(pos_parts)
        raw_neg = ", ".join(neg_parts)

        pos_prompt = _normalize_prompt_string(raw_pos)
        neg_prompt = _normalize_prompt_string(raw_neg)

        return PromptResult(
            positive_prompt=pos_prompt,
            negative_prompt=neg_prompt,
            lora_settings=dedup_loras,
            seed_settings=seed_settings,
        )
