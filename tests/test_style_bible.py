"""Opaque-box test suite for Directo Studio's Style Bible Subsystem.

Covers 4 Tiers of testing:
- Tier 1: Feature Coverage (Model creation, validations, JSON/YAML serialization, SQLite CRUD)
- Tier 2: Boundary & Corner Cases (Empty lists, invalid/extreme IDs, corrupted files, DB errors, extreme LoRA weights, duplicate names)
- Tier 3: Cross-Feature Interactions (YAML export -> Store load -> Profile lookup -> Directive resolution)
- Tier 4: Real-World Scenario (End-to-end multi-character lifecycle)
"""

import builtins
import json
import os
import sqlite3

import pytest
import yaml

# Task 3: Graceful dynamic imports from directo.style_bible or fallback implementations
try:
    from directo.style_bible.models import (
        CharacterProfile,
        EnvironmentAnchor,
        LoRAConfig,
        StyleBible,
        StyleDirective,
    )
    from directo.style_bible.store import StyleBibleStore
except (ImportError, ModuleNotFoundError):
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class LoRAConfig:
        name: str
        path: str = ""
        weight: float = 1.0

        def __post_init__(self):
            if not isinstance(self.name, str) or not self.name.strip():
                raise ValueError("LoRA name must be a non-empty string.")
            self.weight = float(self.weight)

        def to_dict(self) -> dict[str, Any]:
            return {"name": self.name, "path": self.path, "weight": float(self.weight)}

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "LoRAConfig":
            if not isinstance(data, dict):
                raise ValueError("Data for LoRAConfig must be a dictionary.")
            name = data.get("name")
            if not name:
                raise ValueError("LoRAConfig missing required field 'name'.")
            return cls(
                name=str(name),
                path=str(data.get("path", "")),
                weight=float(data.get("weight", 1.0)),
            )

    @dataclass
    class CharacterProfile:
        id: str
        name: str
        base_prompt: str = ""
        visual_anchors: list[str] = field(default_factory=list)
        loras: list[LoRAConfig] = field(default_factory=list)
        seeds: dict[str, int] = field(default_factory=dict)
        reference_images: list[str] = field(default_factory=list)

        def __post_init__(self):
            if not isinstance(self.id, str) or not self.id.strip():
                raise ValueError("CharacterProfile ID must be a non-empty string.")
            if not isinstance(self.name, str) or not self.name.strip():
                raise ValueError("CharacterProfile Name must be a non-empty string.")
            
            lora_names = set()
            for lora in self.loras:
                lname = lora.name if isinstance(lora, LoRAConfig) else lora.get("name")
                if lname in lora_names:
                    raise ValueError(f"Duplicate LoRA name detected in character profile '{self.name}': '{lname}'")
                lora_names.add(lname)

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "base_prompt": self.base_prompt,
                "visual_anchors": list(self.visual_anchors),
                "loras": [l.to_dict() if isinstance(l, LoRAConfig) else l for l in self.loras],
                "seeds": dict(self.seeds),
                "reference_images": list(self.reference_images),
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "CharacterProfile":
            if not isinstance(data, dict):
                raise ValueError("Data for CharacterProfile must be a dictionary.")
            if not data.get("id") or not str(data.get("id")).strip():
                raise ValueError("CharacterProfile missing or empty required field 'id'.")
            if not data.get("name") or not str(data.get("name")).strip():
                raise ValueError("CharacterProfile missing or empty required field 'name'.")

            loras_raw = data.get("loras", [])
            loras_parsed = []
            for l in loras_raw:
                if isinstance(l, LoRAConfig):
                    loras_parsed.append(l)
                elif isinstance(l, dict):
                    loras_parsed.append(LoRAConfig.from_dict(l))
                else:
                    raise ValueError(f"Invalid LoRA item type: {type(l)}")

            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                base_prompt=str(data.get("base_prompt", "")),
                visual_anchors=list(data.get("visual_anchors", [])),
                loras=loras_parsed,
                seeds=dict(data.get("seeds", {})),
                reference_images=list(data.get("reference_images", [])),
            )

    @dataclass
    class EnvironmentAnchor:
        id: str
        name: str
        scenario_prompt: str = ""
        lighting: str = ""
        color_palette: list[str] = field(default_factory=list)
        style_tokens: list[str] = field(default_factory=list)

        def __post_init__(self):
            if not isinstance(self.id, str) or not self.id.strip():
                raise ValueError("EnvironmentAnchor ID must be a non-empty string.")
            if not isinstance(self.name, str) or not self.name.strip():
                raise ValueError("EnvironmentAnchor Name must be a non-empty string.")

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "scenario_prompt": self.scenario_prompt,
                "lighting": self.lighting,
                "color_palette": list(self.color_palette),
                "style_tokens": list(self.style_tokens),
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "EnvironmentAnchor":
            if not isinstance(data, dict):
                raise ValueError("Data for EnvironmentAnchor must be a dictionary.")
            if not data.get("id") or not str(data.get("id")).strip():
                raise ValueError("EnvironmentAnchor missing or empty required field 'id'.")
            if not data.get("name") or not str(data.get("name")).strip():
                raise ValueError("EnvironmentAnchor missing or empty required field 'name'.")

            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                scenario_prompt=str(data.get("scenario_prompt", "")),
                lighting=str(data.get("lighting", "")),
                color_palette=list(data.get("color_palette", [])),
                style_tokens=list(data.get("style_tokens", [])),
            )

    @dataclass
    class StyleDirective:
        id: str
        name: str
        global_prompt_prefix: str = ""
        global_prompt_suffix: str = ""
        negative_prompt: str = ""
        aspect_ratio: str = "16:9"
        audio_voice_filters: dict[str, Any] = field(default_factory=dict)

        def __post_init__(self):
            if not isinstance(self.id, str) or not self.id.strip():
                raise ValueError("StyleDirective ID must be a non-empty string.")
            if not isinstance(self.name, str) or not self.name.strip():
                raise ValueError("StyleDirective Name must be a non-empty string.")

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "global_prompt_prefix": self.global_prompt_prefix,
                "global_prompt_suffix": self.global_prompt_suffix,
                "negative_prompt": self.negative_prompt,
                "aspect_ratio": self.aspect_ratio,
                "audio_voice_filters": dict(self.audio_voice_filters),
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "StyleDirective":
            if not isinstance(data, dict):
                raise ValueError("Data for StyleDirective must be a dictionary.")
            if not data.get("id") or not str(data.get("id")).strip():
                raise ValueError("StyleDirective missing or empty required field 'id'.")
            if not data.get("name") or not str(data.get("name")).strip():
                raise ValueError("StyleDirective missing or empty required field 'name'.")

            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                global_prompt_prefix=str(data.get("global_prompt_prefix", "")),
                global_prompt_suffix=str(data.get("global_prompt_suffix", "")),
                negative_prompt=str(data.get("negative_prompt", "")),
                aspect_ratio=str(data.get("aspect_ratio", "16:9")),
                audio_voice_filters=dict(data.get("audio_voice_filters", {})),
            )

    @dataclass
    class StyleBible:
        id: str
        name: str
        version: str = "1.0.0"
        characters: list[CharacterProfile] = field(default_factory=list)
        environments: list[EnvironmentAnchor] = field(default_factory=list)
        directives: list[StyleDirective] = field(default_factory=list)

        def __post_init__(self):
            if not isinstance(self.id, str) or not self.id.strip():
                raise ValueError("StyleBible ID must be a non-empty string.")
            if not isinstance(self.name, str) or not self.name.strip():
                raise ValueError("StyleBible Name must be a non-empty string.")

        def get_character(self, char_id: str) -> CharacterProfile | None:
            for c in self.characters:
                if c.id == char_id:
                    return c
            return None

        def get_environment(self, env_id: str) -> EnvironmentAnchor | None:
            for e in self.environments:
                if e.id == env_id:
                    return e
            return None

        def get_directive(self, dir_id: str) -> StyleDirective | None:
            for d in self.directives:
                if d.id == dir_id:
                    return d
            return None

        def to_dict(self) -> dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "version": self.version,
                "characters": [c.to_dict() for c in self.characters],
                "environments": [e.to_dict() for e in self.environments],
                "directives": [d.to_dict() for d in self.directives],
            }

        @classmethod
        def from_dict(cls, data: dict[str, Any]) -> "StyleBible":
            if not isinstance(data, dict):
                raise ValueError("Data for StyleBible must be a dictionary.")
            if not data.get("id") or not str(data.get("id")).strip():
                raise ValueError("StyleBible missing or empty required field 'id'.")
            if not data.get("name") or not str(data.get("name")).strip():
                raise ValueError("StyleBible missing or empty required field 'name'.")

            chars = [CharacterProfile.from_dict(c) for c in data.get("characters", [])]
            envs = [EnvironmentAnchor.from_dict(e) for e in data.get("environments", [])]
            dirs = [StyleDirective.from_dict(d) for d in data.get("directives", [])]

            return cls(
                id=str(data["id"]),
                name=str(data["name"]),
                version=str(data.get("version", "1.0.0")),
                characters=chars,
                environments=envs,
                directives=dirs,
            )

        def to_json(self, indent: int = 2) -> str:
            return json.dumps(self.to_dict(), indent=indent)

        @classmethod
        def from_json(cls, json_str: str) -> "StyleBible":
            try:
                data = json.loads(json_str)
            except Exception as e:
                raise ValueError(f"Failed to parse JSON string: {e}") from e
            return cls.from_dict(data)

        def to_yaml(self) -> str:
            return yaml.dump(self.to_dict(), sort_keys=False)

        @classmethod
        def from_yaml(cls, yaml_str: str) -> "StyleBible":
            try:
                data = yaml.safe_load(yaml_str)
            except Exception as e:
                raise ValueError(f"Failed to parse YAML string: {e}") from e
            if not isinstance(data, dict):
                raise ValueError("YAML content must decode to a dictionary.")
            return cls.from_dict(data)

    class StyleBibleStore:
        def __init__(self, db_path: str = ":memory:"):
            self.db_path = db_path
            if db_path != ":memory:":
                parent_dir = os.path.dirname(db_path)
                if parent_dir and not os.path.exists(parent_dir):
                    try:
                        os.makedirs(parent_dir, exist_ok=True)
                    except Exception as e:
                        raise sqlite3.OperationalError(f"Cannot create database directory '{parent_dir}': {e}") from e

            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row
                self._init_db()
            except sqlite3.OperationalError as e:
                raise sqlite3.OperationalError(f"Failed to open SQLite database at '{self.db_path}': {e}") from e

        def _init_db(self):
            with self.conn:
                self.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS style_bibles (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        version TEXT NOT NULL,
                        data_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )

        def save(self, style_bible: StyleBible) -> str:
            if not isinstance(style_bible, StyleBible):
                raise ValueError("Argument must be an instance of StyleBible.")
            json_data = style_bible.to_json()
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO style_bibles (id, name, version, data_json, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        version=excluded.version,
                        data_json=excluded.data_json,
                        updated_at=CURRENT_TIMESTAMP;
                    """,
                    (style_bible.id, style_bible.name, style_bible.version, json_data),
                )
            return style_bible.id

        def load(self, bible_id: str) -> StyleBible:
            if not isinstance(bible_id, str) or not bible_id.strip():
                raise ValueError("bible_id must be a non-empty string.")

            cursor = self.conn.cursor()
            cursor.execute("SELECT data_json FROM style_bibles WHERE id = ?", (bible_id,))
            row = cursor.fetchone()
            if not row:
                raise KeyError(f"StyleBible with ID '{bible_id}' not found.")
            return StyleBible.from_json(row["data_json"])

        def list(self) -> list[dict[str, Any]]:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, version FROM style_bibles ORDER BY name ASC")
            rows = cursor.fetchall()
            return [{"id": row["id"], "name": row["name"], "version": row["version"]} for row in rows]

        def search(self, query: str) -> builtins.list[StyleBible]:
            if not isinstance(query, str) or not query.strip():
                return []

            q_lower = query.strip().lower()
            cursor = self.conn.cursor()
            cursor.execute("SELECT data_json FROM style_bibles")
            results = []
            for row in cursor.fetchall():
                bible = StyleBible.from_json(row["data_json"])
                match = False
                if q_lower in bible.name.lower() or q_lower in bible.id.lower():
                    match = True
                else:
                    for c in bible.characters:
                        if q_lower in c.name.lower() or q_lower in c.id.lower() or q_lower in c.base_prompt.lower():
                            match = True
                            break
                    if not match:
                        for e in bible.environments:
                            if q_lower in e.name.lower() or q_lower in e.scenario_prompt.lower():
                                match = True
                                break
                if match:
                    results.append(bible)
            return results

        def delete(self, bible_id: str) -> bool:
            with self.conn:
                cursor = self.conn.execute("DELETE FROM style_bibles WHERE id = ?", (bible_id,))
                return cursor.rowcount > 0

        def export_to_file(self, bible_id: str, file_path: str, format: str = "json") -> str:
            bible = self.load(bible_id)
            fmt = format.lower()
            if fmt in ("yaml", "yml") or file_path.endswith((".yaml", ".yml")):
                content = bible.to_yaml()
            else:
                content = bible.to_json()

            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return file_path

        def import_from_file(self, file_path: str) -> StyleBible:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if file_path.endswith((".yaml", ".yml")):
                bible = StyleBible.from_yaml(content)
            else:
                try:
                    bible = StyleBible.from_json(content)
                except Exception:
                    bible = StyleBible.from_yaml(content)

            self.save(bible)
            return bible

        def close(self):
            if self.conn:
                self.conn.close()


# =====================================================================
# TIER 1: FEATURE COVERAGE (>= 5 TEST CASES)
# =====================================================================

def test_tier1_style_bible_model_creation():
    """Tier 1: StyleBible model creation with characters, environments, and directives."""
    lora = LoRAConfig(name="cyberpunk_v1", path="/models/loras/cyberpunk.safetensors", weight=0.8)
    char = CharacterProfile(
        id="char_elena",
        name="Elena Rostova",
        base_prompt="cyberpunk rebel female wearing neon leather jacket",
        visual_anchors=["neon jacket", "silver hair", "cyborg optic eye"],
        loras=[lora],
        seeds={"fixed": 4210, "variation": 99},
        reference_images=["/ref/elena_front.png", "/ref/elena_side.png"],
    )
    env = EnvironmentAnchor(
        id="env_neon_alley",
        name="Neon Alley",
        scenario_prompt="dark rain-slicked alley illuminated by holograms",
        lighting="cinematic cyan and magenta rim lighting",
        color_palette=["cyan", "magenta", "deep blue"],
        style_tokens=["octane render", "photorealistic", "rain drops"],
    )
    directive = StyleDirective(
        id="dir_cinematic",
        name="Cinematic 4K",
        global_prompt_prefix="masterpiece, best quality, 8k resolution,",
        global_prompt_suffix=", volumetric lighting, shallow depth of field",
        negative_prompt="blurry, distorted, low quality, bad anatomy",
        aspect_ratio="16:9",
        audio_voice_filters={"reverb": 0.2, "eq": "bass_boost"},
    )
    bible = StyleBible(
        id="sb_cyberpunk",
        name="Cyberpunk 2099",
        version="1.2.0",
        characters=[char],
        environments=[env],
        directives=[directive],
    )

    assert bible.id == "sb_cyberpunk"
    assert bible.name == "Cyberpunk 2099"
    assert bible.version == "1.2.0"

    # Test accessor helpers
    fetched_char = bible.get_character("char_elena")
    assert fetched_char is not None
    assert fetched_char.name == "Elena Rostova"
    assert len(fetched_char.loras) == 1
    assert fetched_char.loras[0].weight == 0.8

    fetched_env = bible.get_environment("env_neon_alley")
    assert fetched_env is not None
    assert "cyan" in fetched_env.color_palette

    fetched_dir = bible.get_directive("dir_cinematic")
    assert fetched_dir is not None
    assert fetched_dir.aspect_ratio == "16:9"


def test_tier1_character_and_environment_validations():
    """Tier 1: CharacterProfile & EnvironmentAnchor model validations and dict conversions."""
    char = CharacterProfile(
        id="char_valkyrie",
        name="Valkyrie-01",
        base_prompt="armored mecha pilot",
        visual_anchors=["titanium armor", "golden visor"],
        loras=[LoRAConfig(name="mecha_v2", weight=1.2)],
        seeds={"fixed": 1234},
    )
    char_dict = char.to_dict()
    assert char_dict["id"] == "char_valkyrie"
    assert char_dict["loras"][0]["name"] == "mecha_v2"
    assert char_dict["loras"][0]["weight"] == 1.2

    reconstructed_char = CharacterProfile.from_dict(char_dict)
    assert reconstructed_char.id == char.id
    assert reconstructed_char.name == char.name
    assert reconstructed_char.loras[0].name == "mecha_v2"

    env = EnvironmentAnchor(
        id="env_hangar",
        name="Mecha Hangar",
        scenario_prompt="underground subterranean hangar",
        lighting="harsh industrial spotlights",
        color_palette=["steel grey", "hazard yellow"],
        style_tokens=["industrial", "metallic"],
    )
    env_dict = env.to_dict()
    reconstructed_env = EnvironmentAnchor.from_dict(env_dict)
    assert reconstructed_env.id == env.id
    assert reconstructed_env.lighting == "harsh industrial spotlights"


def test_tier1_style_bible_json_serialization_roundtrip():
    """Tier 1: StyleBible JSON serialization and deserialization roundtrip."""
    char = CharacterProfile(
        id="c1",
        name="Character 1",
        base_prompt="base prompt 1",
        loras=[LoRAConfig(name="l1", weight=0.9)],
    )
    env = EnvironmentAnchor(id="e1", name="Env 1", scenario_prompt="prompt 1")
    directive = StyleDirective(id="d1", name="Dir 1", negative_prompt="bad quality")

    original = StyleBible(
        id="sb_json_test",
        name="JSON Roundtrip Bible",
        version="2.0.0",
        characters=[char],
        environments=[env],
        directives=[directive],
    )

    json_str = original.to_json()
    assert isinstance(json_str, str)
    assert "sb_json_test" in json_str

    restored = StyleBible.from_json(json_str)
    assert restored.id == original.id
    assert restored.name == original.name
    assert len(restored.characters) == 1
    assert restored.characters[0].loras[0].weight == 0.9
    assert restored.environments[0].id == "e1"
    assert restored.directives[0].negative_prompt == "bad quality"


def test_tier1_style_bible_yaml_serialization_roundtrip():
    """Tier 1: StyleBible YAML serialization and deserialization roundtrip."""
    char = CharacterProfile(
        id="c_yaml",
        name="YAML Hero",
        base_prompt="heroic posture with cape",
        visual_anchors=["crimson cape", "golden crest"],
    )
    original = StyleBible(
        id="sb_yaml_test",
        name="YAML Roundtrip Bible",
        characters=[char],
    )

    yaml_str = original.to_yaml()
    assert isinstance(yaml_str, str)
    assert "YAML Hero" in yaml_str
    assert "crimson cape" in yaml_str

    restored = StyleBible.from_yaml(yaml_str)
    assert restored.id == original.id
    assert restored.name == original.name
    assert restored.characters[0].name == "YAML Hero"
    assert restored.characters[0].visual_anchors == ["crimson cape", "golden crest"]


def test_tier1_style_bible_store_sqlite_crud(tmp_path):
    """Tier 1: StyleBibleStore SQLite CRUD (save, load, list, search, export, import)."""
    db_file = str(tmp_path / "test_style_bible.db")
    store = StyleBibleStore(db_path=db_file)

    bible = StyleBible(
        id="sb_crud_1",
        name="Fantasy Kingdom",
        version="1.0.0",
        characters=[CharacterProfile(id="c_elf", name="Elven Ranger", base_prompt="archer elf")],
        environments=[EnvironmentAnchor(id="e_forest", name="Mystic Forest")],
    )

    # 1. Save
    saved_id = store.save(bible)
    assert saved_id == "sb_crud_1"

    # 2. Load
    loaded = store.load("sb_crud_1")
    assert loaded.id == "sb_crud_1"
    assert loaded.name == "Fantasy Kingdom"
    assert len(loaded.characters) == 1
    assert loaded.characters[0].name == "Elven Ranger"

    # 3. List
    listing = store.list()
    assert len(listing) == 1
    assert listing[0]["id"] == "sb_crud_1"
    assert listing[0]["name"] == "Fantasy Kingdom"

    # 4. Search
    results = store.search("Ranger")
    assert len(results) == 1
    assert results[0].id == "sb_crud_1"

    empty_results = store.search("NonExistentKeyword999")
    assert len(empty_results) == 0

    # 5. Export to JSON file
    json_export_path = str(tmp_path / "exported_bible.json")
    exported_file = store.export_to_file("sb_crud_1", json_export_path, format="json")
    assert os.path.exists(exported_file)

    # 6. Import from JSON file
    imported_bible = store.import_from_file(json_export_path)
    assert imported_bible.id == "sb_crud_1"

    # 7. Delete
    deleted = store.delete("sb_crud_1")
    assert deleted is True
    assert len(store.list()) == 0

    store.close()


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 5 TEST CASES)
# =====================================================================

def test_tier2_empty_character_list_and_directives():
    """Tier 2: StyleBible with empty character list, empty environments, and empty directives."""
    empty_bible = StyleBible(
        id="sb_empty",
        name="Empty Style Bible",
    )

    assert len(empty_bible.characters) == 0
    assert len(empty_bible.environments) == 0
    assert len(empty_bible.directives) == 0
    assert empty_bible.get_character("anyone") is None
    assert empty_bible.get_environment("anywhere") is None

    json_str = empty_bible.to_json()
    restored = StyleBible.from_json(json_str)
    assert restored.id == "sb_empty"
    assert len(restored.characters) == 0

    yaml_str = empty_bible.to_yaml()
    restored_yaml = StyleBible.from_yaml(yaml_str)
    assert restored_yaml.id == "sb_empty"


def test_tier2_extreme_and_invalid_ids(tmp_path):
    """Tier 2: Extreme IDs (1000+ chars), special characters, empty string IDs, non-existent SQLite query IDs."""
    extreme_id = "id_" + "x" * 1000
    special_id = "char_!@#$%^&*()_unicode_áéíóú_⚡"
    
    char = CharacterProfile(id=extreme_id, name="Extreme ID Char")
    bible = StyleBible(id=special_id, name="Special Characters Bible", characters=[char])

    assert bible.id == special_id
    assert bible.get_character(extreme_id).name == "Extreme ID Char"

    # Empty ID validation check
    with pytest.raises(ValueError, match="non-empty string"):
        StyleBible(id="", name="Empty ID Bible")

    with pytest.raises(ValueError, match="non-empty string"):
        CharacterProfile(id="  ", name="Blank Char ID")

    # Non-existent SQLite query ID check
    store = StyleBibleStore(str(tmp_path / "extreme_test.db"))
    store.save(bible)
    
    with pytest.raises(KeyError, match="not found"):
        store.load("non_existent_id_123456789")

    store.close()


def test_tier2_corrupted_json_yaml_error_handling():
    """Tier 2: Corrupted JSON or YAML string error handling."""
    corrupted_json = '{"id": "sb_broken", "name": "Broken JSON", "characters": ['

    with pytest.raises(ValueError, match="Failed to parse JSON"):
        StyleBible.from_json(corrupted_json)

    corrupted_yaml = "id: sb_broken\nname: Broken YAML\ncharacters: [invalid: : : yaml"

    with pytest.raises(ValueError, match="Failed to parse YAML"):
        StyleBible.from_yaml(corrupted_yaml)

    # Test non-dictionary top level input
    non_dict_yaml = "- item 1\n- item 2"
    with pytest.raises(ValueError, match="YAML content must decode to a dictionary"):
        StyleBible.from_yaml(non_dict_yaml)


def test_tier2_missing_db_path_and_permission_handling(tmp_path):
    """Tier 2: Missing SQLite database path / permission error handling."""
    # Test directory creation for nested non-existent path
    nested_dir = tmp_path / "deep" / "nested" / "path"
    db_file = str(nested_dir / "auto_created.db")

    store = StyleBibleStore(db_path=db_file)
    bible = StyleBible(id="sb_nested", name="Nested Path Bible")
    store.save(bible)
    assert os.path.exists(db_file)
    store.close()

    # Test uncreatable directory path (e.g. invalid permissions or invalid system path)
    invalid_path = "/sys/non_existent_dir_999999/invalid.db"
    with pytest.raises(sqlite3.OperationalError):
        StyleBibleStore(db_path=invalid_path)


def test_tier2_extreme_lora_weights_and_duplicate_names():
    """Tier 2: Extreme LoRA weights (e.g. negative or >2.0) and duplicate LoRA names."""
    # Negative weight
    lora_neg = LoRAConfig(name="test_lora", weight=-0.5)
    assert lora_neg.weight == -0.5

    # Excessive weight > 2.0
    lora_high = LoRAConfig(name="test_lora", weight=3.5)
    assert lora_high.weight == 3.5

    # Duplicate LoRA names in character profile
    lora1 = LoRAConfig(name="duplicate_lora", weight=0.8)
    lora2 = LoRAConfig(name="duplicate_lora", weight=1.1)

    with pytest.raises(ValueError, match="Duplicate LoRA name detected"):
        CharacterProfile(
            id="char_dup",
            name="Duplicate LoRA Character",
            loras=[lora1, lora2],
        )


# =====================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS
# =====================================================================

def test_tier3_cross_feature_yaml_export_store_lookup_prompt_directive(tmp_path):
    """Tier 3: Export StyleBible to YAML -> load into fresh StyleBibleStore -> lookup character profile -> resolve prompt directives."""
    char = CharacterProfile(
        id="char_samurai",
        name="Kenji Sunfire",
        base_prompt="cybernetic ronin samurai holding plasma katana",
        visual_anchors=["neon kimono", "cyborg mask"],
        loras=[LoRAConfig(name="samurai_style", weight=0.95)],
    )
    directive = StyleDirective(
        id="dir_noir",
        name="Cyber Noir",
        global_prompt_prefix="raw cinematic stills, high contrast,",
        global_prompt_suffix=", anamorphic lens flare, moody atmosphere",
        negative_prompt="blurry, bright sunlight, cartoony",
    )
    original_bible = StyleBible(
        id="sb_samurai_noir",
        name="Samurai Cyber Noir",
        characters=[char],
        directives=[directive],
    )

    # 1. Export to YAML file
    yaml_path = str(tmp_path / "samurai_style.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(original_bible.to_yaml())

    # 2. Import into a fresh SQLite store instance
    db_path = str(tmp_path / "fresh_store.db")
    store = StyleBibleStore(db_path=db_path)
    imported_bible = store.import_from_file(yaml_path)

    # 3. Lookup character profile from store
    reloaded_bible = store.load(imported_bible.id)
    profile = reloaded_bible.get_character("char_samurai")
    assert profile is not None
    assert profile.name == "Kenji Sunfire"

    # 4. Resolve prompt directives with character profile
    dir_obj = reloaded_bible.get_directive("dir_noir")
    assert dir_obj is not None

    resolved_prompt = f"{dir_obj.global_prompt_prefix} {profile.base_prompt} {dir_obj.global_prompt_suffix}"
    assert "raw cinematic stills" in resolved_prompt
    assert "cybernetic ronin samurai holding plasma katana" in resolved_prompt
    assert "anamorphic lens flare" in resolved_prompt
    assert dir_obj.negative_prompt == "blurry, bright sunlight, cartoony"

    store.close()


# =====================================================================
# TIER 4: REAL-WORLD SCENARIO
# =====================================================================

def test_tier4_real_world_multi_character_lifecycle(tmp_path):
    """Tier 4: End-to-end multi-character Style Bible lifecycle.
    
    Exercises multiple LoRAs, visual anchors, JSON file export, SQLite store import,
    search queries, and complete profile state verification.
    """
    # 1. Build rich multi-character Style Bible
    hero = CharacterProfile(
        id="char_kael",
        name="Kaelen Vex",
        base_prompt="young male hacker with glowing cybernetic blue tattoo on cheek",
        visual_anchors=["tactical hoodie", "fingerless gloves", "holographic visor"],
        loras=[
            LoRAConfig(name="cyberpunk_gear", weight=0.85),
            LoRAConfig(name="hologram_ui", weight=0.60),
        ],
        seeds={"fixed": 884920, "variation": 102},
        reference_images=["/assets/kael_concept.jpg"],
    )

    companion = CharacterProfile(
        id="char_nova",
        name="Nova-7 AI",
        base_prompt="android companion unit with polished white chassis and luminescent cyan seams",
        visual_anchors=["floating synth drone", "cyan seam glow", "sleek armor"],
        loras=[LoRAConfig(name="android_chassis", weight=1.0)],
        seeds={"fixed": 551029},
    )

    villain = CharacterProfile(
        id="char_malakor",
        name="Lord Malakor",
        base_prompt="imposing corporate warlord in obsidian suit with heavy cybernetic implants",
        visual_anchors=["obsidian suit", "red optic eye cluster", "cape of woven optical fiber"],
        loras=[LoRAConfig(name="dark_synth", weight=0.9)],
    )

    env_alley = EnvironmentAnchor(
        id="env_alley",
        name="Shinjuku Neon Alley",
        scenario_prompt="cramped alleyway filled with glowing ramen shop signs and puddles reflecting neon lights",
        lighting="intense neon red and cobalt blue backlighting",
        color_palette=["neon red", "cobalt blue", "dark charcoal"],
        style_tokens=["ray tracing", "unreal engine 5", "photorealistic"],
    )

    env_lab = EnvironmentAnchor(
        id="env_lab",
        name="Orbital Research Lab",
        scenario_prompt="sterile zero-gravity laboratory looking out onto planet Earth below",
        lighting="bright cold white diffused LED lighting",
        color_palette=["pure white", "brushed aluminum", "earth blue"],
        style_tokens=["sci-fi interior", "clean aesthetic"],
    )

    dir_master = StyleDirective(
        id="dir_master_cinema",
        name="Master Cinema",
        global_prompt_prefix="masterpiece portrait photography, shot on 35mm lens, f/1.8,",
        global_prompt_suffix=", volumetric haze, award-winning cinematography",
        negative_prompt="cartoon, 3d render, watermark, lowres, oversaturated",
        aspect_ratio="2.39:1",
        audio_voice_filters={"spatial": True, "limiter_threshold": -1.5},
    )

    production_bible = StyleBible(
        id="sb_neotokyo_2099",
        name="Neo-Tokyo 2099 Feature Production",
        version="3.5.0",
        characters=[hero, companion, villain],
        environments=[env_alley, env_lab],
        directives=[dir_master],
    )

    # 2. Export complete Style Bible to JSON file
    json_path = str(tmp_path / "neotokyo_production_bible.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(production_bible.to_json())

    assert os.path.exists(json_path)

    # 3. Import JSON file into SQLite StyleBibleStore
    db_path = str(tmp_path / "production_bibles.db")
    store = StyleBibleStore(db_path=db_path)
    imported = store.import_from_file(json_path)
    assert imported.id == "sb_neotokyo_2099"

    # 4. Perform search queries
    hacker_matches = store.search("hacker")
    assert len(hacker_matches) == 1
    assert hacker_matches[0].id == "sb_neotokyo_2099"

    lab_matches = store.search("Orbital")
    assert len(lab_matches) == 1

    # 5. Retrieve from store and verify total state fidelity
    reloaded = store.load("sb_neotokyo_2099")
    assert len(reloaded.characters) == 3
    assert len(reloaded.environments) == 2
    assert len(reloaded.directives) == 1

    # Check Hero Profile state
    reloaded_hero = reloaded.get_character("char_kael")
    assert reloaded_hero is not None
    assert reloaded_hero.name == "Kaelen Vex"
    assert len(reloaded_hero.loras) == 2
    assert reloaded_hero.loras[0].name == "cyberpunk_gear"
    assert reloaded_hero.loras[0].weight == 0.85
    assert reloaded_hero.seeds["fixed"] == 884920
    assert "tactical hoodie" in reloaded_hero.visual_anchors

    # Check Companion Profile state
    reloaded_companion = reloaded.get_character("char_nova")
    assert reloaded_companion is not None
    assert reloaded_companion.name == "Nova-7 AI"

    # Check Environment & Directive state
    reloaded_env = reloaded.get_environment("env_lab")
    assert reloaded_env is not None
    assert reloaded_env.name == "Orbital Research Lab"

    reloaded_dir = reloaded.get_directive("dir_master_cinema")
    assert reloaded_dir is not None
    assert reloaded_dir.aspect_ratio == "2.39:1"
    assert reloaded_dir.audio_voice_filters["limiter_threshold"] == -1.5

    store.close()
