"""Cinema preset packs.

A preset is a complete bundle of parameters that reproduces a
specific visual style — a "vibe in a box". When you select a preset,
Directo knows:

- Which model / sampler / scheduler to use.
- Which LoRAs to apply.
- Which negative prompt to use.
- Which prompt template to wrap the user's input in.
- Whether to add a Cinema Prompt Engine pass first.

Inspired by the 67 live-action + 43 animation presets from
DirectorsConsole, but structured as composable building blocks.

The catalog ships with hand-picked starter packs across both
real-world cinematography eras and animation styles. Users can
extend with their own (JSON-serializable) presets.

This is a "starter set" — production users will replace it with
their own fine-tuned models + LoRAs.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

from directo.observability import get_logger

log = get_logger("directo.scale.presets")


@dataclass
class Preset:
    """A complete visual style bundle.

    Fields are intentionally a superset of what most ComfyUI /
    Stable Diffusion / FLUX workflows need. Any unknown field is
    forwarded to the underlying workflow as an extra input.
    """

    id: str
    name: str
    kind: str = "live_action"  # "live_action" | "animation" | "abstract" | "custom"
    era: str = ""              # e.g. "1927-1940", "1990s", "Ghibli"
    description: str = ""
    image_url: str = ""        # path or URL for preset thumbnail image

    # Model stack
    model: str = ""            # base model name (e.g. "flux-dev", "sdxl-base")
    loras: list[dict[str, Any]] = field(default_factory=list)
    # Each LoRA entry: {"name": "...", "weight": 0.8, "trigger": "optional phrase"}

    # Sampling
    sampler: str = "euler"
    scheduler: str = "normal"
    steps: int = 28
    cfg_scale: float = 4.5
    width: int = 1024
    height: int = 1024

    # Prompting
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative_prompt: str = "low quality, worst quality, blurry, deformed"

    # Post-processing
    upscaler: str | None = None
    upscale_factor: float = 1.0

    # Engine pass
    cinema_rules: list[str] = field(default_factory=list)  # rule IDs to apply

    # Misc
    tags: list[str] = field(default_factory=list)
    author: str = "directo"
    version: int = 1
    is_builtin: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("image_url"):
            d["image_url"] = f"/presets/{self.id}.jpg"
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Preset:
        # Drop any unknown keys for forward compatibility
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def render_prompt(self, user_prompt: str) -> str:
        """Wrap a user prompt with the preset's prefix/suffix."""
        parts = []
        if self.prompt_prefix:
            parts.append(self.prompt_prefix.strip())
        parts.append(user_prompt.strip())
        if self.prompt_suffix:
            parts.append(self.prompt_suffix.strip())
        return ", ".join(parts)


# =====================================================================
# Built-in catalog — starter set (live-action + animation)
# =====================================================================


def _builtin_presets() -> list[Preset]:
    """Hand-picked starter presets. Replaceable by user uploads."""
    presets: list[Preset] = []

    # ---------- Live-action eras ----------

    presets += [
        # 1927-1940: German Expressionism / early cinema
        Preset(
            id="live-silent-german-expressionism",
            name="Silent Era — German Expressionism",
            kind="live_action", era="1927-1940",
            description="High-contrast black & white, distorted angles, dramatic shadows (Metropolis 1927, Cabinet of Dr. Caligari 1920).",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=30, cfg_scale=5.0,
            prompt_prefix="1920s german expressionist silent film still, high contrast black and white, dramatic chiaroscuro lighting, distorted angular composition, low angle dutch tilt",
            prompt_suffix="grain, monochrome, deep shadows, theatrical lighting, orthochromatic film stock",
            negative_prompt="color, modern, digital, smooth, plastic, shallow depth of field",
            tags=["bw", "silent-era", "expressionism", "high-contrast"],
            is_builtin=True,
        ),
        # 1930-1950: Classic Hollywood noir
        Preset(
            id="live-classic-noir-1940s",
            name="Classic Film Noir (1940s)",
            kind="live_action", era="1940-1950",
            description="Low-key lighting, venetian blind shadows, urban night scenes (The Maltese Falcon 1941, Double Indemnity 1944).",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=28, cfg_scale=4.5,
            prompt_prefix="1940s film noir cinematography, low-key hard lighting, venetian blind shadows, urban night scene, fedoras and trench coats, period-accurate mise-en-scène",
            prompt_suffix="silver gelatin print, deep focus, dramatic shadows, smoke, rain-slicked streets",
            negative_prompt="color, digital, modern clothing, neon, high-key lighting",
            tags=["noir", "1940s", "low-key", "urban"],
            is_builtin=True,
        ),
        # 1950-1970: Technicolor
        Preset(
            id="live-technicolor-1950s",
            name="Technicolor Era (1950s)",
            kind="live_action", era="1950-1970",
            description="Saturated, three-strip Technicolor palette; mid-century modern; epic scope.",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=32, cfg_scale=4.0,
            prompt_prefix="1950s three-strip technicolor film still, saturated mid-century palette, widescreen cinemaScope composition, period-accurate costuming and set design",
            prompt_suffix="technicolor saturation, fine film grain, anamorphic lens, deep depth of field",
            negative_prompt="digital, desaturated, modern, plastic",
            tags=["1950s", "technicolor", "widescreen", "saturated"],
            is_builtin=True,
        ),
        # 1970s: New Hollywood / grainy
        Preset(
            id="live-new-hollywood-1970s",
            name="New Hollywood (1970s)",
            kind="live_action", era="1970-1980",
            description="Gritty 35mm grain, natural light, anamorphic flares (Taxi Driver 1976, The Godfather 1972).",
            model="flux-dev", sampler="euler_a", scheduler="karras",
            steps=28, cfg_scale=4.5,
            prompt_prefix="1970s new hollywood cinematography, gritty 35mm kodak film stock, naturalistic lighting, anamorphic lens flares, period-accurate costuming",
            prompt_suffix="visible film grain, warm color grade, shallow depth of field, lens distortion",
            negative_prompt="digital, clean, modern, plastic",
            tags=["1970s", "new-hollywood", "gritty", "anamorphic"],
            is_builtin=True,
        ),
        # 1990s: Indie / Tarantino
        Preset(
            id="live-90s-indie-1990s",
            name="90s Indie Cinema",
            kind="live_action", era="1990-2000",
            description="Saturated cross-processed look; handheld; 16mm grain (Clerks 1994, Pulp Fiction 1994).",
            model="flux-dev", sampler="dpmpp_2m", scheduler="karras",
            steps=26, cfg_scale=5.0,
            prompt_prefix="1990s indie film still, 16mm cross-processed look, saturated colors, handheld camera, period-accurate details",
            prompt_suffix="16mm grain, high contrast, naturalistic lighting, slightly desaturated highlights",
            negative_prompt="digital, modern, clean, plastic, sterile",
            tags=["1990s", "indie", "16mm", "cross-processed"],
            is_builtin=True,
        ),
        # 2000s: Digital cinema transition
        Preset(
            id="live-2000s-digital",
            name="Early Digital Cinema (2000s)",
            kind="live_action", era="2000-2010",
            description="HD video look, slight oversaturation, shallow DOF (Collateral 2004, Slumdog Millionaire 2008).",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=28, cfg_scale=4.5,
            prompt_prefix="2000s HD digital cinematography, slightly oversaturated, shallow depth of field, period-accurate tech",
            prompt_suffix="HD sharpness, modern color grade, clean digital grain",
            negative_prompt="film grain (excessive), VHS, analog distortion",
            tags=["2000s", "digital", "hd"],
            is_builtin=True,
        ),
        # 2010s+: Modern anamorphic
        Preset(
            id="live-modern-anamorphic",
            name="Modern Anamorphic (2010s+)",
            kind="live_action", era="2010+",
            description="Anamorphic bokeh, teal-and-orange grade, modern sensors (Blade Runner 2049, Dune 2021).",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=30, cfg_scale=4.5,
            prompt_prefix="modern anamorphic cinematography, oval bokeh, teal and orange color grade, cinematic composition",
            prompt_suffix="2.39:1 aspect ratio, anamorphic lens flares, shallow depth of field, modern sensor look",
            negative_prompt="VHS, analog, low resolution, plastic",
            tags=["modern", "anamorphic", "teal-orange", "widescreen"],
            is_builtin=True,
        ),
        # Parasite 2019 specific
        Preset(
            id="live-parasite-2019",
            name="Parasite (2019) — Hong",
            kind="live_action", era="2010+",
            description="Bong Joon-ho's precise framing, cool/warm color contrast, social-class visual language.",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=32, cfg_scale=4.5,
            prompt_prefix="precise symmetrical framing in the style of bong joon-ho, cool blue-grey for poor household vs warm yellow for rich household, social-class visual contrast, period-accurate Korean setting",
            prompt_suffix="modern anamorphic, fine detail, naturalistic lighting, Korean production design",
            tags=["parasite", "korean", "2019", "social-contrast"],
            is_builtin=True,
        ),
        # Cyberpunk Neon Noir (Wong Kar-wai)
        Preset(
            id="live-neon-noir-wong",
            name="Neon Noir — Cyberpunk Realism",
            kind="live_action", era="1990s-Present",
            description="Steeped in Wong Kar-wai & Christopher Doyle style; neon reflections, rain-slicked streets, step-printing shutter.",
            model="flux-dev", sampler="euler", scheduler="karras",
            steps=30, cfg_scale=4.5,
            prompt_prefix="wong kar-wai cinematography, neon-soaked urban night scene, slow shutter motion blur, vivid red and cyan lighting contrast, rain-slicked pavement",
            prompt_suffix="35mm film grain, atmospheric haze, step-printing effect, deep shadow detail",
            negative_prompt="bright daylight, clean studio lighting, 3d render, sharp focus",
            tags=["neon-noir", "wong-kar-wai", "cyberpunk", "night"],
            is_builtin=True,
        ),
        # Modern Brutalist Sci-Fi (Villeneuve / Deakins)
        Preset(
            id="live-brutalist-scifi",
            name="Brutalist Sci-Fi (Villeneuve)",
            kind="live_action", era="2015+",
            description="Denis Villeneuve & Roger Deakins style; monumental architecture, diffuse hazy sunlight, amber/monochrome scale.",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=32, cfg_scale=4.0,
            prompt_prefix="denis villeneuve cinema style, massive scale brutalist architecture, hazy diffused atmospheric sunlight, minimalist composition, monochrome amber tone",
            prompt_suffix="extreme wide angle shot, volumetric dust rays, 70mm IMAX aesthetic, crisp contrast",
            negative_prompt="cluttered scene, oversaturated neon, busy background, lens flare",
            tags=["villeneuve", "brutalist", "scifi", "imax"],
            is_builtin=True,
        ),
        # Pastel Symmetry (Wes Anderson)
        Preset(
            id="live-pastel-symmetry",
            name="Pastel Symmetry (Wes Anderson)",
            kind="live_action", era="1970s Aesthetic",
            description="One-point perspective, pastel palette, vintage 1970s interior production design, flat lighting.",
            model="flux-dev", sampler="euler", scheduler="normal",
            steps=28, cfg_scale=5.0,
            prompt_prefix="wes anderson aesthetic, perfectly centered one-point perspective composition, pastel color palette, vintage 1970s interior production design",
            prompt_suffix="flat lighting, crisp detail, whimsical set dress, kodachrome 64 film stock",
            negative_prompt="dramatic lighting, dutch tilt, dark shadows, modern digital texture",
            tags=["wes-anderson", "symmetry", "pastel", "vintage"],
            is_builtin=True,
        ),
        # A24 Folk Horror / Moody Naturalism
        Preset(
            id="live-a24-moody-naturalism",
            name="A24 Folk & Moody Naturalism",
            kind="live_action", era="2015+",
            description="Overcast natural lighting, desaturated earthy tones, eerie quietness (The Witch, Midsommar).",
            model="flux-dev", sampler="euler_a", scheduler="karras",
            steps=30, cfg_scale=4.5,
            prompt_prefix="A24 indie film screenshot, overcast natural lighting, desaturated earthy tones, moody atmospheric tension, remote rural setting",
            prompt_suffix="natural skin texture, organic materials, shallow depth of field, 35mm matte finish",
            negative_prompt="high contrast, glossy, studio lights, artificial colors, vibrant",
            tags=["a24", "folk-horror", "desaturated", "moody"],
            is_builtin=True,
        ),
    ]

    # ---------- Animation styles ----------

    presets += [
        # Studio Ghibli
        Preset(
            id="anim-ghibli",
            name="Studio Ghibli",
            kind="animation",
            description="Soft watercolor backgrounds, expressive character animation, gentle naturalistic lighting.",
            model="sdxl", sampler="euler_a", scheduler="karras",
            steps=30, cfg_scale=7.0,
            loras=[{"name": "ghibli-style", "weight": 0.85, "trigger": ""}],
            prompt_prefix="studio ghibli style anime illustration, soft watercolor background, hand-drawn aesthetic, gentle expressionistic lighting",
            prompt_suffix="cel-shaded, detailed natural elements, hayao miyazaki inspired composition",
            tags=["ghibli", "anime", "watercolor", "hand-drawn"],
            is_builtin=True,
        ),
        # Pixar
        Preset(
            id="anim-pixar",
            name="Pixar 3D Animation",
            kind="animation",
            description="Polished 3D, expressive characters, vibrant lighting, cinematic camera.",
            model="sdxl", sampler="dpmpp_2m", scheduler="karras",
            steps=28, cfg_scale=6.5,
            prompt_prefix="pixar 3d animation still, polished cg render, expressive stylized character, vibrant cinematic lighting, detailed production design",
            prompt_suffix="physically based rendering, subsurface scattering, depth of field, ambient occlusion",
            tags=["pixar", "3d", "cg", "polished"],
            is_builtin=True,
        ),
        # Spider-Verse
        Preset(
            id="anim-spiderverse",
            name="Spider-Verse Style",
            kind="animation",
            description="Comic-book inspired, halftone dots, chromatic aberration, mixed media aesthetic.",
            model="sdxl", sampler="euler_a", scheduler="karras",
            steps=30, cfg_scale=7.0,
            loras=[{"name": "spiderverse", "weight": 0.9, "trigger": ""}],
            prompt_prefix="spider-verse style, comic book panel inspired, halftone dots, chromatic aberration, mixed 2d and 3d elements, bold linework",
            prompt_suffix="comic book aesthetic, risograph texture, vibrant saturated palette, motion blur",
            tags=["spiderverse", "comic", "halftone", "mixed-media"],
            is_builtin=True,
        ),
        # Arcane
        Preset(
            id="anim-arcane",
            name="Arcane (Fortiche) Style",
            kind="animation",
            description="Painterly oil-on-canvas, hand-painted textures, dramatic rim lighting.",
            model="sdxl", sampler="euler", scheduler="karras",
            steps=30, cfg_scale=6.5,
            loras=[{"name": "arcane-style", "weight": 0.85, "trigger": ""}],
            prompt_prefix="arcane fortiche animation style, painterly oil-painted texture, hand-painted backgrounds, dramatic rim lighting, stylized character design",
            prompt_suffix="visible brush strokes, painterly rendering, dramatic contrast, rich saturated palette",
            tags=["arcane", "fortiche", "painterly", "oil-painted"],
            is_builtin=True,
        ),
        # Anime (general)
        Preset(
            id="anim-anime-90s",
            name="90s Anime Cel",
            kind="animation",
            description="Hand-painted cel animation, screencap aesthetic, golden-age anime style.",
            model="sdxl", sampler="euler_a", scheduler="karras",
            steps=28, cfg_scale=6.5,
            loras=[{"name": "anime-cel", "weight": 0.8, "trigger": ""}],
            prompt_prefix="1990s anime cel animation still, hand-painted look, screencap aesthetic, golden age anime visual style",
            prompt_suffix="cel-shaded, limited animation feel, film grain, vibrant flat colors",
            tags=["anime", "90s", "cel", "hand-painted"],
            is_builtin=True,
        ),
        # 1988 Cyberpunk Anime (Akira / Ghost in the Shell)
        Preset(
            id="anim-80s-cyberpunk",
            name="80s Cyberpunk Anime (Akira Style)",
            kind="animation",
            description="Classic hand-drawn 1980s anime cel art, dense mechanical details, retro CRT aesthetic.",
            model="sdxl", sampler="euler_a", scheduler="karras",
            steps=30, cfg_scale=7.0,
            prompt_prefix="1980s retro anime cel screenshot, hand-painted background, high detail cyberpunk aesthetic, dense mechanical details, classic cel shading",
            prompt_suffix="analog CRT video artifacts, vivid hand-painted highlights, film grain, vintage japanese animation",
            negative_prompt="modern 3d render, digital smooth gradient, soft blur, disney style",
            tags=["80s", "cyberpunk", "anime", "akira"],
            is_builtin=True,
        ),
        # Stylized 2.5D Concept Art (Klaus / Stylized 3D)
        Preset(
            id="anim-stylized-25d",
            name="2.5D Painted Stylized Art",
            kind="animation",
            description="Rich painterly brushstroke textures on 3D forms with dramatic edge lighting.",
            model="sdxl", sampler="dpmpp_2m", scheduler="karras",
            steps=30, cfg_scale=6.5,
            prompt_prefix="stylized 3D animation still, hand-painted brush stroke texture, dramatic stylized rim lighting, rich color palette, cinematic character framing",
            prompt_suffix="subsurface scattering, 2.5D illustration aesthetic, crisp edge highlights, artistic concept art",
            negative_prompt="photorealistic, hyperrealistic photorealism, low poly, default blender render",
            tags=["stylized", "2.5d", "concept-art", "painterly"],
            is_builtin=True,
        ),
        # French/European Graphic Novel (Moebius Line & Wash)
        Preset(
            id="anim-moebius-ink",
            name="European Graphic Novel (Moebius)",
            kind="animation",
            description="Fine ink cross-hatching linework, clean watercolor color wash, surreal sci-fi aesthetic.",
            model="sdxl", sampler="euler", scheduler="normal",
            steps=28, cfg_scale=6.5,
            prompt_prefix="moebius comic book illustration, fine ink cross-hatching linework, clean watercolor color wash, surreal sci-fi landscape",
            prompt_suffix="vintage graphic novel print texture, high detail line art, matte paper finish",
            negative_prompt="photorealism, heavy shadows, smooth gradients, 3d render",
            tags=["moebius", "ink", "line-art", "graphic-novel"],
            is_builtin=True,
        ),
    ]

    return presets


# =====================================================================
# Persistence
# =====================================================================


class PresetStore:
    """SQLite-backed preset catalog.

    Built-in presets are seeded on first init. User-uploaded presets
    are stored alongside them and are first-class citizens in the API
    (you can update, delete, and rate them just like builtins).
    """

    def __init__(self, db_path: str | Path = "directo_presets.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        self._seed_builtins()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS presets (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    kind            TEXT NOT NULL DEFAULT 'live_action',
                    era             TEXT NOT NULL DEFAULT '',
                    description     TEXT NOT NULL DEFAULT '',
                    image_url       TEXT NOT NULL DEFAULT '',
                    model           TEXT NOT NULL DEFAULT '',
                    loras_json      TEXT NOT NULL DEFAULT '[]',
                    sampler         TEXT NOT NULL DEFAULT 'euler',
                    scheduler       TEXT NOT NULL DEFAULT 'normal',
                    steps           INTEGER NOT NULL DEFAULT 28,
                    cfg_scale       REAL NOT NULL DEFAULT 4.5,
                    width           INTEGER NOT NULL DEFAULT 1024,
                    height          INTEGER NOT NULL DEFAULT 1024,
                    prompt_prefix   TEXT NOT NULL DEFAULT '',
                    prompt_suffix   TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    upscaler        TEXT,
                    upscale_factor  REAL NOT NULL DEFAULT 1.0,
                    cinema_rules_json TEXT NOT NULL DEFAULT '[]',
                    tags_json       TEXT NOT NULL DEFAULT '[]',
                    author          TEXT NOT NULL DEFAULT 'directo',
                    version         INTEGER NOT NULL DEFAULT 1,
                    is_builtin      INTEGER NOT NULL DEFAULT 0,
                    use_count       INTEGER NOT NULL DEFAULT 0,
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_presets_kind ON presets (kind);
                CREATE INDEX IF NOT EXISTS idx_presets_era ON presets (era);
                """
            )

    def _seed_builtins(self) -> None:
        """Insert built-in presets if they don't already exist."""
        for p in _builtin_presets():
            with self._lock:
                cur = self._conn.execute(
                    "SELECT 1 FROM presets WHERE id = ?", (p.id,)
                ).fetchone()
                if cur is None:
                    self._conn.execute(
                        """
                        INSERT INTO presets (
                            id, name, kind, era, description, model, loras_json,
                            sampler, scheduler, steps, cfg_scale, width, height,
                            prompt_prefix, prompt_suffix, negative_prompt,
                            upscaler, upscale_factor, cinema_rules_json, tags_json,
                            author, version, is_builtin
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            p.id, p.name, p.kind, p.era, p.description,
                            p.model, json.dumps(p.loras),
                            p.sampler, p.scheduler, p.steps, p.cfg_scale,
                            p.width, p.height,
                            p.prompt_prefix, p.prompt_suffix, p.negative_prompt,
                            p.upscaler, p.upscale_factor,
                            json.dumps(p.cinema_rules), json.dumps(p.tags),
                            p.author, p.version,
                        ),
                    )

    # ----------------- CRUD -----------------

    def add(self, preset: Preset) -> str:
        """Insert a user preset. Built-ins cannot be modified by this method."""
        if not preset.id:
            preset.id = f"user-{uuid.uuid4().hex[:12]}"
        preset.is_builtin = False
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO presets (
                    id, name, kind, era, description, model, loras_json,
                    sampler, scheduler, steps, cfg_scale, width, height,
                    prompt_prefix, prompt_suffix, negative_prompt,
                    upscaler, upscale_factor, cinema_rules_json, tags_json,
                    author, version, is_builtin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    preset.id, preset.name, preset.kind, preset.era,
                    preset.description, preset.model, json.dumps(preset.loras),
                    preset.sampler, preset.scheduler, preset.steps,
                    preset.cfg_scale, preset.width, preset.height,
                    preset.prompt_prefix, preset.prompt_suffix,
                    preset.negative_prompt, preset.upscaler,
                    preset.upscale_factor, json.dumps(preset.cinema_rules),
                    json.dumps(preset.tags), preset.author, preset.version,
                ),
            )
        log.bind(preset_id=preset.id).info(f"preset added: {preset.name}")
        return preset.id

    def get(self, preset_id: str) -> Preset | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM presets WHERE id = ?", (preset_id,)
            ).fetchone()
        return self._row_to_preset(row) if row else None

    def list(
        self,
        kind: str | None = None,
        era: str | None = None,
        tag: str | None = None,
        limit: int = 200,
    ) -> list[Preset]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if era:
            clauses.append("era = ?")
            params.append(era)
        if tag:
            clauses.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM presets WHERE {where} ORDER BY name LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_preset(r) for r in rows]

    def delete(self, preset_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT is_builtin FROM presets WHERE id = ?", (preset_id,)
            ).fetchone()
            if row is None or row["is_builtin"]:
                return False  # don't allow deleting builtins
            self._conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
        return True

    def increment_use_count(self, preset_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE presets SET use_count = use_count + 1 WHERE id = ?",
                (preset_id,),
            )

    def search(self, query: str, limit: int = 50) -> list[Preset]:
        """Substring search across name, description, tags, and era."""
        like = f"%{query}%"
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM presets
                WHERE name LIKE ? OR description LIKE ? OR era LIKE ? OR tags_json LIKE ?
                ORDER BY use_count DESC LIMIT ?
                """,
                (like, like, like, like, limit),
            ).fetchall()
        return [self._row_to_preset(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) AS n FROM presets").fetchone()["n"]

    def _row_to_preset(self, row: sqlite3.Row) -> Preset:
        return Preset(
            id=row["id"], name=row["name"], kind=row["kind"],
            era=row["era"], description=row["description"],
            image_url=row["image_url"] if row["image_url"] else f"/presets/{row['id']}.jpg",
            model=row["model"], loras=json.loads(row["loras_json"]),
            sampler=row["sampler"], scheduler=row["scheduler"],
            steps=row["steps"], cfg_scale=row["cfg_scale"],
            width=row["width"], height=row["height"],
            prompt_prefix=row["prompt_prefix"], prompt_suffix=row["prompt_suffix"],
            negative_prompt=row["negative_prompt"],
            upscaler=row["upscaler"], upscale_factor=row["upscale_factor"],
            cinema_rules=json.loads(row["cinema_rules_json"]),
            tags=json.loads(row["tags_json"]),
            author=row["author"], version=row["version"],
            is_builtin=bool(row["is_builtin"]),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
