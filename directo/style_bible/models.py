"""Data models for Style Bible Engine & Prompt Builder.

Provides data structures (`LoRAConfig`, `CharacterProfile`, `EnvironmentAnchor`,
`StyleDirective`, `StyleBible`) for visual consistency, prompt composition,
and seed/LoRA configuration management. Supports JSON and YAML serialization/deserialization.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import yaml


class StyleDict(dict):
    """Dictionary supporting list-like indexing, value iteration, and flexible key/item lookup."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def __iter__(self):
        return iter(self.values())

    def __contains__(self, key: Any) -> bool:
        if super().__contains__(key):
            return True
        return key in self.values()


def _to_style_dict(val: Any) -> StyleDict:
    if isinstance(val, StyleDict):
        return val
    if isinstance(val, dict):
        return StyleDict(val)
    if isinstance(val, (list, tuple)):
        res = StyleDict()
        for item in val:
            if hasattr(item, "id") and item.id:
                res[item.id] = item
            elif isinstance(item, dict) and "id" in item:
                res[item["id"]] = item
        return res
    return StyleDict()


@dataclass
class LoRAConfig:
    """Configuration for a LoRA model adapter."""

    name: str
    path: str = ""
    weight: float = 1.0
    trigger_words: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("LoRA name must be a non-empty string.")
        try:
            self.weight = float(self.weight)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid LoRA weight: {self.weight}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "weight": float(self.weight),
            "trigger_words": list(self.trigger_words),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoRAConfig:
        if not isinstance(data, dict):
            raise ValueError("Data for LoRAConfig must be a dictionary.")
        name = data.get("name")
        if not name:
            raise ValueError("LoRAConfig missing required field 'name'.")
        tw = data.get("trigger_words", [])
        if tw is None:
            tw = []
        return cls(
            name=str(name),
            path=str(data.get("path", "")),
            weight=float(data.get("weight", 1.0)),
            trigger_words=list(tw),
        )


@dataclass
class CharacterProfile:
    """Visual profile and prompt rules for a character."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    base_prompt: str = ""
    visual_anchors: list[str] = field(default_factory=list)
    loras: list[LoRAConfig] = field(default_factory=list)
    seeds: dict[str, Any] = field(default_factory=dict)
    reference_images: list[str] = field(default_factory=list)
    negative_prompt: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("CharacterProfile ID must be a non-empty string.")

        lora_names = set()
        for lora in self.loras:
            lname = lora.name if isinstance(lora, LoRAConfig) else lora.get("name")
            if lname in lora_names:
                raise ValueError(
                    f"Duplicate LoRA name detected in character profile '{self.name}': '{lname}'"
                )
            lora_names.add(lname)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "base_prompt": self.base_prompt,
            "visual_anchors": list(self.visual_anchors),
            "loras": [l.to_dict() if hasattr(l, "to_dict") else l for l in self.loras],
            "seeds": dict(self.seeds),
            "reference_images": list(self.reference_images),
            "negative_prompt": self.negative_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterProfile:
        if not isinstance(data, dict):
            raise ValueError("Data for CharacterProfile must be a dictionary.")
        if "id" in data and not str(data["id"]).strip():
            raise ValueError("CharacterProfile missing or empty required field 'id'.")

        loras_raw = data.get("loras", [])
        loras_parsed: list[LoRAConfig] = []
        if loras_raw:
            for l in loras_raw:
                if isinstance(l, LoRAConfig):
                    loras_parsed.append(l)
                elif isinstance(l, dict):
                    loras_parsed.append(LoRAConfig.from_dict(l))
                else:
                    raise ValueError(f"Invalid LoRA item type: {type(l)}")

        cid = str(data.get("id") or uuid.uuid4().hex)
        name = str(data.get("name", ""))
        base_prompt = str(data.get("base_prompt", ""))
        visual_anchors = list(data.get("visual_anchors", []) or [])
        seeds = dict(data.get("seeds", {}) or {})
        ref_images = list(data.get("reference_images", []) or [])
        neg_prompt = str(data.get("negative_prompt", ""))

        return cls(
            id=cid,
            name=name,
            base_prompt=base_prompt,
            visual_anchors=visual_anchors,
            loras=loras_parsed,
            seeds=seeds,
            reference_images=ref_images,
            negative_prompt=neg_prompt,
        )


@dataclass
class EnvironmentAnchor:
    """Environmental context and lighting parameters."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    scenario_prompt: str = ""
    lighting: str = ""
    color_palette: Any = ""
    style_tokens: list[str] = field(default_factory=list)
    negative_prompt: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("EnvironmentAnchor ID must be a non-empty string.")

    def to_dict(self) -> dict[str, Any]:
        palette = (
            list(self.color_palette)
            if isinstance(self.color_palette, (list, tuple))
            else self.color_palette
        )
        return {
            "id": self.id,
            "name": self.name,
            "scenario_prompt": self.scenario_prompt,
            "lighting": self.lighting,
            "color_palette": palette,
            "style_tokens": list(self.style_tokens),
            "negative_prompt": self.negative_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentAnchor:
        if not isinstance(data, dict):
            raise ValueError("Data for EnvironmentAnchor must be a dictionary.")
        if "id" in data and not str(data["id"]).strip():
            raise ValueError("EnvironmentAnchor missing or empty required field 'id'.")

        eid = str(data.get("id") or uuid.uuid4().hex)
        name = str(data.get("name", ""))
        scenario_prompt = str(data.get("scenario_prompt", ""))
        lighting = str(data.get("lighting", ""))
        palette = data.get("color_palette", "")
        if isinstance(palette, list):
            palette = list(palette)
        elif palette is None:
            palette = ""
        else:
            palette = str(palette)
        style_tokens = list(data.get("style_tokens", []) or [])
        neg_prompt = str(data.get("negative_prompt", ""))

        return cls(
            id=eid,
            name=name,
            scenario_prompt=scenario_prompt,
            lighting=lighting,
            color_palette=palette,
            style_tokens=style_tokens,
            negative_prompt=neg_prompt,
        )


@dataclass
class StyleDirective:
    """Global aesthetic directives and generation constraints."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    global_prompt_prefix: str = ""
    global_prompt_suffix: str = ""
    negative_prompt: str = ""
    aspect_ratio: str = "16:9"
    audio_voice_filters: dict[str, Any] = field(default_factory=dict)
    directive_seed: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("StyleDirective ID must be a non-empty string.")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "global_prompt_prefix": self.global_prompt_prefix,
            "global_prompt_suffix": self.global_prompt_suffix,
            "negative_prompt": self.negative_prompt,
            "aspect_ratio": self.aspect_ratio,
            "audio_voice_filters": dict(self.audio_voice_filters),
        }
        if self.directive_seed is not None:
            d["directive_seed"] = self.directive_seed
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleDirective:
        if not isinstance(data, dict):
            raise ValueError("Data for StyleDirective must be a dictionary.")
        if "id" in data and not str(data["id"]).strip():
            raise ValueError("StyleDirective missing or empty required field 'id'.")

        did = str(data.get("id") or uuid.uuid4().hex)
        name = str(data.get("name", ""))
        prefix = str(data.get("global_prompt_prefix", ""))
        suffix = str(data.get("global_prompt_suffix", ""))
        neg = str(data.get("negative_prompt", ""))
        aspect = str(data.get("aspect_ratio", "16:9"))
        audio = dict(data.get("audio_voice_filters", {}) or {})
        dir_seed = data.get("directive_seed")

        return cls(
            id=did,
            name=name,
            global_prompt_prefix=prefix,
            global_prompt_suffix=suffix,
            negative_prompt=neg,
            aspect_ratio=aspect,
            audio_voice_filters=audio,
            directive_seed=dir_seed,
        )


@dataclass
class StyleBible:
    """Container aggregating character profiles, environment anchors, and style directives."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    version: str = "1.0.0"
    characters: Any = field(default_factory=StyleDict)
    environments: Any = field(default_factory=StyleDict)
    directives: Any = field(default_factory=StyleDict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("StyleBible ID must be a non-empty string.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("StyleBible Name must be a non-empty string.")

        self.characters = _to_style_dict(self.characters)
        self.environments = _to_style_dict(self.environments)
        self.directives = _to_style_dict(self.directives)

    def add_character(self, character: CharacterProfile) -> None:
        if not isinstance(self.characters, StyleDict):
            self.characters = _to_style_dict(self.characters)
        self.characters[character.id] = character

    def get_character(self, character_id: str) -> CharacterProfile | None:
        if isinstance(self.characters, StyleDict):
            return self.characters.get(character_id)
        if isinstance(self.characters, dict):
            return self.characters.get(character_id)
        if isinstance(self.characters, (list, tuple)):
            for c in self.characters:
                if hasattr(c, "id") and c.id == character_id:
                    return c
        return None

    def add_environment(self, environment: EnvironmentAnchor) -> None:
        if not isinstance(self.environments, StyleDict):
            self.environments = _to_style_dict(self.environments)
        self.environments[environment.id] = environment

    def get_environment(self, environment_id: str) -> EnvironmentAnchor | None:
        if isinstance(self.environments, StyleDict):
            return self.environments.get(environment_id)
        if isinstance(self.environments, dict):
            return self.environments.get(environment_id)
        if isinstance(self.environments, (list, tuple)):
            for e in self.environments:
                if hasattr(e, "id") and e.id == environment_id:
                    return e
        return None

    def add_directive(self, directive: StyleDirective) -> None:
        if not isinstance(self.directives, StyleDict):
            self.directives = _to_style_dict(self.directives)
        self.directives[directive.id] = directive

    def get_directive(self, directive_id: str) -> StyleDirective | None:
        if isinstance(self.directives, StyleDict):
            return self.directives.get(directive_id)
        if isinstance(self.directives, dict):
            return self.directives.get(directive_id)
        if isinstance(self.directives, (list, tuple)):
            for d in self.directives:
                if hasattr(d, "id") and d.id == directive_id:
                    return d
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "characters": [
                c.to_dict() if hasattr(c, "to_dict") else c for c in self.characters
            ],
            "environments": [
                e.to_dict() if hasattr(e, "to_dict") else e for e in self.environments
            ],
            "directives": [
                d.to_dict() if hasattr(d, "to_dict") else d for d in self.directives
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleBible:
        if not isinstance(data, dict):
            raise ValueError("Data for StyleBible must be a dictionary.")
        if not data.get("id") or not str(data.get("id")).strip():
            raise ValueError("StyleBible missing or empty required field 'id'.")
        if not data.get("name") or not str(data.get("name")).strip():
            raise ValueError("StyleBible missing or empty required field 'name'.")

        sbid = str(data["id"])
        sbname = str(data["name"])
        version = str(data.get("version", "1.0.0"))

        chars_raw = data.get("characters", {})
        parsed_chars = StyleDict()
        if isinstance(chars_raw, dict):
            for cid, cdata in chars_raw.items():
                if isinstance(cdata, CharacterProfile):
                    parsed_chars[cid] = cdata
                elif isinstance(cdata, dict):
                    profile = CharacterProfile.from_dict(cdata)
                    parsed_chars[profile.id or cid] = profile
        elif isinstance(chars_raw, (list, tuple)):
            for cdata in chars_raw:
                if isinstance(cdata, CharacterProfile):
                    parsed_chars[cdata.id] = cdata
                elif isinstance(cdata, dict):
                    profile = CharacterProfile.from_dict(cdata)
                    parsed_chars[profile.id] = profile

        envs_raw = data.get("environments", {})
        parsed_envs = StyleDict()
        if isinstance(envs_raw, dict):
            for eid, edata in envs_raw.items():
                if isinstance(edata, EnvironmentAnchor):
                    parsed_envs[eid] = edata
                elif isinstance(edata, dict):
                    anchor = EnvironmentAnchor.from_dict(edata)
                    parsed_envs[anchor.id or eid] = anchor
        elif isinstance(envs_raw, (list, tuple)):
            for edata in envs_raw:
                if isinstance(edata, EnvironmentAnchor):
                    parsed_envs[edata.id] = edata
                elif isinstance(edata, dict):
                    anchor = EnvironmentAnchor.from_dict(edata)
                    parsed_envs[anchor.id] = anchor

        dirs_raw = data.get("directives", {})
        parsed_dirs = StyleDict()
        if isinstance(dirs_raw, dict):
            for did, ddata in dirs_raw.items():
                if isinstance(ddata, StyleDirective):
                    parsed_dirs[did] = ddata
                elif isinstance(ddata, dict):
                    directive = StyleDirective.from_dict(ddata)
                    parsed_dirs[directive.id or did] = directive
        elif isinstance(dirs_raw, (list, tuple)):
            for ddata in dirs_raw:
                if isinstance(ddata, StyleDirective):
                    parsed_dirs[ddata.id] = ddata
                elif isinstance(ddata, dict):
                    directive = StyleDirective.from_dict(ddata)
                    parsed_dirs[directive.id] = directive

        return cls(
            id=sbid,
            name=sbname,
            version=version,
            characters=parsed_chars,
            environments=parsed_envs,
            directives=parsed_dirs,
        )

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> StyleBible:
        if not json_str or not json_str.strip():
            raise ValueError("Failed to parse JSON string: Empty string provided")
        try:
            data = json.loads(json_str)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON string: {e}") from e
        if not isinstance(data, dict):
            raise TypeError(f"Expected JSON object (dict), got {type(data).__name__}")
        return cls.from_dict(data)

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> StyleBible:
        if not yaml_str or not yaml_str.strip():
            raise ValueError("Failed to parse YAML string: Empty string provided")
        try:
            data = yaml.safe_load(yaml_str)
        except Exception as e:
            raise ValueError(f"Failed to parse YAML string: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("YAML content must decode to a dictionary.")
        return cls.from_dict(data)
