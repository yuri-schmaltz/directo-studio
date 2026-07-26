"""Creative Director Agent — a stateful LLM agent that holds the project's
creative vision and guides all downstream generations.

The agent has memory: it remembers the project's concept, characters,
style, and every decision the user has made. Every generation in the
project can be grounded in this context.

The agent can:

- Plan a sequence of generations for a goal ("a 24-frame storyboard
  for a 30s commercial").
- Enrich a raw user prompt with the project's creative context.
- Answer creative questions in-character ("what should the lighting
  look like for the reveal scene?").
- Track decisions and update memory when a variant is locked.

The :class:`CreativeDirector` is a thin orchestrator around any
LLM provider. The default backend is the :class:`TemplateEnhancer`
(offline) but the same interface works for any provider from
:mod:`directo.scale.enhance`.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from directo.observability import get_logger

log = get_logger("directo.director.agent")


# =====================================================================
# Domain
# =====================================================================


@dataclass
class Character:
    name: str
    description: str
    visual_traits: list[str] = field(default_factory=list)
    voice: str = ""
    arc: str = ""


@dataclass
class StyleGuide:
    palette: list[str] = field(default_factory=list)        # e.g. ["#2c1810", "#d4a574"]
    lighting: str = ""
    camera: str = ""
    mood: str = ""
    references: list[str] = field(default_factory=list)     # paths or names
    notes: str = ""


@dataclass
class Decision:
    """A creative decision the user has made and committed to."""

    id: str
    decision_key: str
    choice: str
    rationale: str = ""
    decided_at: float = field(default_factory=time.time)
    decided_by: str = "user"
    payload: dict[str, Any] = field(default_factory=dict)


class LLMBackend(Protocol):
    """The agent only needs `complete` and `is_available`."""

    def is_available(self) -> bool: ...
    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...


# =====================================================================
# Project memory
# =====================================================================


class ProjectMemory:
    """Persistent state for a single creative project.

    Holds:
    - The project's concept / logline
    - Character sheets
    - Style guide
    - Decision log (what was chosen, when, by whom)
    """

    def __init__(self, db_path: str | Path = "directo_memory.db") -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    concept         TEXT NOT NULL DEFAULT '',
                    logline         TEXT NOT NULL DEFAULT '',
                    characters_json TEXT NOT NULL DEFAULT '[]',
                    style_json      TEXT NOT NULL DEFAULT '{}',
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    created_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at      REAL NOT NULL DEFAULT (unixepoch('now'))
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id              TEXT PRIMARY KEY,
                    project_id      TEXT NOT NULL,
                    decision_key    TEXT NOT NULL,
                    choice          TEXT NOT NULL,
                    rationale       TEXT NOT NULL DEFAULT '',
                    decided_at      REAL NOT NULL DEFAULT (unixepoch('now')),
                    decided_by      TEXT NOT NULL DEFAULT 'user',
                    payload_json    TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_decisions_project
                    ON decisions (project_id, decision_key);
                """
            )

    # ----------------- Projects -----------------

    def create_project(
        self, name: str, concept: str = "", logline: str = ""
    ) -> str:
        pid = f"proj-{uuid.uuid4().hex[:10]}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO projects (id, name, concept, logline) VALUES (?, ?, ?, ?)",
                (pid, name, concept, logline),
            )
        log.bind(project=pid).info(f"project created: {name}")
        return pid

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["characters"] = json.loads(d.pop("characters_json"))
        d["style"] = json.loads(d.pop("style_json"))
        d["metadata"] = json.loads(d.pop("metadata_json"))
        return d

    def update_project(self, project_id: str, **fields: Any) -> None:
        if not fields:
            return
        # JSON-encode list/dict fields
        for k in ("characters", "style", "metadata"):
            if k in fields and not isinstance(fields[k], str):
                fields[k + "_json"] = json.dumps(fields.pop(k), default=str)
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [project_id]
        with self._lock:
            self._conn.execute(f"UPDATE projects SET {cols} WHERE id = ?", params)

    def list_projects(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, concept, updated_at FROM projects "
                "ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_project(self, project_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.execute("DELETE FROM decisions WHERE project_id = ?", (project_id,))

    # ----------------- Decisions -----------------

    def record_decision(self, d: Decision) -> str:
        if not d.id:
            d.id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO decisions (id, project_id, decision_key, choice, rationale, decided_by, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (d.id, "", d.decision_key, d.choice, d.rationale, d.decided_by,
                 json.dumps(d.payload, default=str)),
            )
        log.bind(decision=d.id, key=d.decision_key).info(f"decision recorded: {d.choice[:60]}")
        return d.id

    def get_decisions(self, project_id: str) -> list[Decision]:
        # Note: project_id is informational; we store all decisions globally
        # keyed by decision_key. (We can scope per project later.)
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM decisions ORDER BY decided_at DESC LIMIT 200"
            ).fetchall()
        return [
            Decision(
                id=r["id"], decision_key=r["decision_key"], choice=r["choice"],
                rationale=r["rationale"], decided_at=r["decided_at"],
                decided_by=r["decided_by"],
                payload=json.loads(r["payload_json"]) if r["payload_json"] else {},
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "ProjectMemory":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# =====================================================================
# The director agent
# =====================================================================


_SYSTEM_PROMPT = """You are the Creative Director of an AI-assisted film project.
You hold the project's vision in your head: its concept, characters, style,
and the decisions the team has made so far. Every generation is grounded in
this context so the entire project feels coherent.

Your job:
- When asked to enrich a prompt, weave the project's style, character
  descriptions, and recent decisions into the prompt naturally.
- When asked to plan a sequence of generations, output a structured
  shot list (one shot per line: angle, framing, action).
- When asked a creative question, answer in-character with the
  project's voice.

Always preserve the user's intent. Never invent details that contradict
the established concept. If you need to make a creative choice, explain
it in one sentence.
"""


class CreativeDirector:
    """The user-facing facade. Combines a project memory and an LLM backend.

    Typical usage::

        mem = ProjectMemory()
        llm = TemplateBackend()       # or any LLMBackend
        director = CreativeDirector(mem, llm)

        # Create a project
        pid = director.new_project(
            name="Dragon's Perch",
            concept="A dragon perches on a cliff at dawn, watching a village below",
            logline="A short about a dragon deciding whether to intervene."
        )

        # Add a character
        director.add_character(pid, Character(
            name="The Dragon",
            description="old, scarred, with green scales and one torn wing",
            visual_traits=["green scales", "scarred face", "torn left wing"],
        ))

        # Enrich a prompt with the project context
        enriched = director.enrich_prompt(pid, "dragon on a cliff")
    """

    def __init__(self, memory: ProjectMemory, llm: LLMBackend) -> None:
        self.memory = memory
        self.llm = llm

    # ----------------- Project setup -----------------

    def new_project(
        self, name: str, concept: str = "", logline: str = ""
    ) -> str:
        return self.memory.create_project(name, concept, logline)

    def set_concept(self, project_id: str, concept: str, logline: str = "") -> None:
        fields: dict[str, Any] = {"concept": concept}
        if logline:
            fields["logline"] = logline
        self.memory.update_project(project_id, **fields)

    def add_character(self, project_id: str, char: Character) -> None:
        proj = self.memory.get_project(project_id)
        if not proj:
            return
        chars = proj["characters"]
        # Replace if same name, else append
        for i, c in enumerate(chars):
            if c.get("name") == char.name:
                chars[i] = asdict(char)
                break
        else:
            chars.append(asdict(char))
        self.memory.update_project(project_id, characters=chars)
        log.bind(project=project_id, char=char.name).info("character added")

    def set_style(self, project_id: str, style: StyleGuide) -> None:
        self.memory.update_project(project_id, style=asdict(style))

    def list_decisions(self, project_id: str) -> list[Decision]:
        return self.memory.get_decisions(project_id)

    # ----------------- Generation guidance -----------------

    def _build_context(self, project_id: str) -> str:
        proj = self.memory.get_project(project_id)
        if not proj:
            return ""
        parts: list[str] = []
        if proj.get("concept"):
            parts.append(f"Concept: {proj['concept']}")
        if proj.get("logline"):
            parts.append(f"Logline: {proj['logline']}")
        if proj.get("characters"):
            char_lines = []
            for c in proj["characters"]:
                line = f"- {c.get('name', '?')}: {c.get('description', '')}"
                if c.get("visual_traits"):
                    line += f" (visuals: {', '.join(c['visual_traits'])})"
                char_lines.append(line)
            parts.append("Characters:\n" + "\n".join(char_lines))
        style = proj.get("style") or {}
        if style and (style.get("lighting") or style.get("camera") or style.get("palette")):
            style_lines = []
            if style.get("palette"):
                style_lines.append(f"Palette: {', '.join(style['palette'])}")
            if style.get("lighting"):
                style_lines.append(f"Lighting: {style['lighting']}")
            if style.get("camera"):
                style_lines.append(f"Camera: {style['camera']}")
            if style.get("mood"):
                style_lines.append(f"Mood: {style['mood']}")
            parts.append("Style:\n" + "\n".join(style_lines))
        # Recent decisions
        decisions = self.memory.get_decisions(project_id)
        if decisions:
            recent = decisions[:5]
            dec_lines = [f"- {d.decision_key}: {d.choice}" for d in recent]
            parts.append("Recent decisions:\n" + "\n".join(dec_lines))
        return "\n\n".join(parts)

    def enrich_prompt(
        self, project_id: str, raw_prompt: str, *, model_hint: str = "flux-dev"
    ) -> str:
        """Rewrite ``raw_prompt`` in the project's voice."""
        ctx = self._build_context(project_id)
        if not ctx:
            return raw_prompt
        user_msg = (
            f"Project context:\n{ctx}\n\n"
            f"Target model: {model_hint}\n\n"
            f"Raw prompt: {raw_prompt}\n\n"
            "Rewrite this as a single optimized prompt for the target model, "
            "fully grounded in the project context. Output only the prompt."
        )
        # If the LLM is a no-op template (always available but useless for
        # creative synthesis), use the offline fusion instead.
        if not self.llm.is_available() or self.llm.name == "template":
            return self._offline_enrich(ctx, raw_prompt)
        return self.llm.complete(user_msg, system=_SYSTEM_PROMPT, temperature=0.6, max_tokens=400)

    def _offline_enrich(self, ctx: str, raw: str) -> str:
        # Pull palette + lighting from context
        palette_match = re.search(r"Palette:\s*([^\n]+)", ctx)
        lighting_match = re.search(r"Lighting:\s*([^\n]+)", ctx)
        camera_match = re.search(r"Camera:\s*([^\n]+)", ctx)
        suffix_bits = []
        if camera_match:
            suffix_bits.append(camera_match.group(1).strip())
        if lighting_match:
            suffix_bits.append(lighting_match.group(1).strip())
        if palette_match:
            suffix_bits.append(f"color palette: {palette_match.group(1).strip()}")
        if not suffix_bits:
            return raw
        return raw.strip().rstrip(",") + ", " + ", ".join(suffix_bits)

    def plan_shot_list(
        self, project_id: str, goal: str, *, num_shots: int = 8
    ) -> list[dict[str, str]]:
        """Ask the LLM to plan a shot list for a goal.

        Returns a list of dicts: [{"shot": "1", "description": "..."}, ...]
        Falls back to a simple plan if the LLM is unavailable.
        """
        ctx = self._build_context(project_id)
        user_msg = (
            f"Project context:\n{ctx}\n\n"
            f"Goal: {goal}\n\n"
            f"Plan a {num_shots}-shot shot list. Output one shot per line as JSON: "
            '{"shot": "1", "angle": "...", "framing": "...", "action": "...", "notes": "..."}'
        )
        if not self.llm.is_available():
            return self._offline_shot_list(num_shots, goal)
        raw = self.llm.complete(user_msg, system=_SYSTEM_PROMPT, temperature=0.7, max_tokens=1500)
        return self._parse_shot_list_json(raw, num_shots)

    def _offline_shot_list(self, n: int, goal: str) -> list[dict[str, str]]:
        angles = ["establishing wide", "low angle", "high angle", "over-the-shoulder",
                  "close-up", "tracking", "POV", "crane up", "dolly in", "two-shot"]
        framings = ["wide", "medium", "medium close-up", "extreme close-up", "full"]
        import random
        rng = random.Random(goal)
        return [
            {
                "shot": str(i + 1),
                "angle": angles[i % len(angles)],
                "framing": framings[i % len(framings)],
                "action": f"shot {i+1}: continue the scene per the goal",
                "notes": "",
            }
            for i in range(n)
        ]

    def _parse_shot_list_json(self, raw: str, expected: int) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        # Try to find a JSON array
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    for item in data[:expected]:
                        if isinstance(item, dict):
                            out.append({k: str(v) for k, v in item.items()})
            except json.JSONDecodeError:
                pass
        if not out:
            # Fallback: parse lines starting with a number
            for line in raw.splitlines():
                line = line.strip().lstrip("-* ")
                if re.match(r"^\d+[.)]\s+", line):
                    out.append({
                        "shot": str(len(out) + 1),
                        "angle": "", "framing": "",
                        "action": line,
                        "notes": "",
                    })
        return out[:expected] if out else self._offline_shot_list(expected, raw[:50])

    def ask(
        self, project_id: str, question: str
    ) -> str:
        """Ask the director a creative question. Returns the answer."""
        ctx = self._build_context(project_id)
        if not self.llm.is_available():
            return f"[offline mode] project '{project_id}' context: {ctx[:200]}..."
        user_msg = (
            f"Project context:\n{ctx}\n\n"
            f"Question: {question}\n\n"
            "Answer in 1-3 sentences, in the voice of the project's creative director."
        )
        return self.llm.complete(user_msg, system=_SYSTEM_PROMPT, temperature=0.7, max_tokens=400)

    def record_decision(
        self,
        project_id: str,
        decision_key: str,
        choice: str,
        *,
        rationale: str = "",
        decided_by: str = "user",
        payload: dict[str, Any] | None = None,
    ) -> str:
        d = Decision(
            id=uuid.uuid4().hex,
            decision_key=decision_key,
            choice=choice,
            rationale=rationale,
            decided_by=decided_by,
            payload=payload or {},
        )
        return self.memory.record_decision(d)
