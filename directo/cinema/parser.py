"""Script parser — turn a screenplay into a list of scenes.

Supports two formats out of the box:

- **Fountain** — the industry-standard plain-text screenwriting format.
  Scene headings (``INT. KITCHEN - DAY``), action, dialogue, transitions.
- **Plain text** — paragraph-based fallback. Each paragraph becomes a
  "scene candidate" (the engine decides).

PDF and DOCX are best-effort: we extract the text and treat it as
plain text. The mammoth / pdfplumber / pypdf deps are optional.

Output: a list of :class:`Scene` objects. Each scene has a
``slugline`` (e.g. ``INT. KITCHEN - DAY``), ``action`` (description
text), ``characters`` (who's in the scene), and ``dialogue``
(list of character + line pairs).

The :func:`scenes_to_prompts` helper turns each scene into a
cinema-prompt-ready description suitable for image generation.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from directo.observability import get_logger

log = get_logger("directo.cinema.parser")


# =====================================================================
# Domain model
# =====================================================================


@dataclass
class DialogueLine:
    character: str
    text: str
    parenthetical: str | None = None  # stage direction in parens


@dataclass
class Scene:
    """A single scene parsed from a script."""

    id: str
    number: int
    slugline: str                       # "INT. KITCHEN - DAY"
    location: str = ""                  # "INT. KITCHEN"
    time_of_day: str = ""               # "DAY" | "NIGHT" | "DUSK" | etc.
    interior: bool | None = None        # True for INT, False for EXT, None if unknown
    action: str = ""                    # action / description
    dialogue: list[DialogueLine] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)
    raw: str = ""                       # raw text of the scene
    line_range: tuple[int, int] = (0, 0)

    def to_prompt(self) -> str:
        """Build a cinema-prompt-ready description of this scene."""
        parts: list[str] = []
        if self.slugline:
            parts.append(self.slugline)
        if self.action:
            # Trim to the most evocative 200 chars
            text = self.action.strip()
            if len(text) > 400:
                text = text[:400].rsplit(".", 1)[0] + "."
            parts.append(text)
        if self.characters:
            parts.append(f"featuring {', '.join(self.characters[:4])}")
        return " — ".join(parts) if parts else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "number": self.number, "slugline": self.slugline,
            "location": self.location, "time_of_day": self.time_of_day,
            "interior": self.interior, "action": self.action,
            "dialogue": [{"character": d.character, "text": d.text,
                          "parenthetical": d.parenthetical} for d in self.dialogue],
            "characters": self.characters,
            "transitions": self.transitions, "raw": self.raw,
            "line_range": list(self.line_range),
        }


# =====================================================================
# Fountain parser
# =====================================================================


# A scene heading starts with INT./EXT./EST./I/E. (case-insensitive)
# e.g. "INT. KITCHEN - DAY"
_SCENE_RE = re.compile(
    r"^(?:INT|EXT|EST|INT\.\/EXT|I\/E)[\s\.\/]+(.+?)(?:\s*[-–—]\s*(.+))?$",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"^[A-Z\s]+TO:\s*$|^(?:FADE IN|CUT TO|DISSOLVE TO|SMASH CUT TO|MATCH CUT TO):?$",
    re.IGNORECASE,
)
# Character cue: line in ALL CAPS, possibly with (V.O.) / (O.S.) extension
_CHARACTER_RE = re.compile(r"^([A-Z][A-Z0-9 .\-'À-ſ]+)(\s*\([^)]+\))?\s*$")
_PARENTHETICAL_RE = re.compile(r"^\(.+\)\s*$")


def _classify_block(block: list[str]) -> tuple[str, str, str, list[DialogueLine]]:
    """Classify a block as (kind, value) where kind is one of:
    'action', 'character', 'dialogue', 'parenthetical', 'transition'.
    """
    if not block:
        return ("action", "", "", [])
    first = block[0].strip()
    # Transition
    if _TRANSITION_RE.match(first) and len(block) == 1:
        return ("transition", first, "", [])
    # Character
    if len(block) == 1 and _CHARACTER_RE.match(first) and first == first.upper():
        return ("character", first, "", [])
    # Parenthetical on its own
    if _PARENTHETICAL_RE.match(first) and len(block) == 1:
        return ("parenthetical", first, "", [])
    # Otherwise: action
    return ("action", "\n".join(block), "", [])


def parse_fountain(text: str) -> list[Scene]:
    """Parse a Fountain screenplay into a list of scenes."""
    lines = text.splitlines()
    scenes: list[Scene] = []
    current_action: list[str] = []
    current_dialogue: list[DialogueLine] = []
    current_char: str | None = None
    current_parenthetical: str | None = None
    current_transitions: list[str] = []
    current_characters: list[str] = []
    scene_start_line = 0
    scene_number = 0

    def flush_scene(end_line: int) -> None:
        nonlocal current_action, current_dialogue, current_char, current_parenthetical
        nonlocal current_transitions, current_characters, scene_start_line
        if not (current_action or current_dialogue):
            return
        scene_number_local = len(scenes) + 1
        slugline = (current_action[0] if current_action else "").strip() or "UNTITLED SCENE"
        # Parse slugline for location and time
        loc, tod, interior = _parse_slugline(slugline)
        scene_id = uuid.uuid4().hex[:12]
        scenes.append(Scene(
            id=scene_id,
            number=scene_number_local,
            slugline=slugline,
            location=loc,
            time_of_day=tod,
            interior=interior,
            action="\n".join(current_action[1:] if current_action else []).strip(),
            dialogue=current_dialogue,
            characters=sorted(set(current_characters)),
            transitions=current_transitions,
            raw="\n".join(current_action + [
                f"{d.character}: {d.text}" for d in current_dialogue
            ]),
            line_range=(scene_start_line, end_line),
        ))
        current_action = []
        current_dialogue = []
        current_char = None
        current_parenthetical = None
        current_transitions = []
        current_characters = []
        scene_start_line = 0

    # Skip Fountain title page: lines at the top of the file that are
    # "Key: value" pairs (Title:, Author:, Draft date:, etc).
    title_page_done = False
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        # Title page: "Key: value" or blank at top
        if not title_page_done:
            if not stripped:
                i += 1
                continue
            if (":" in stripped and not _SCENE_RE.match(stripped)
                    and i < 20):  # title page is at the top
                # Likely title page metadata; skip
                i += 1
                continue
            title_page_done = True
        if _SCENE_RE.match(stripped):
            # Flush previous
            if current_action or current_dialogue:
                flush_scene(i - 1)
            current_action = [stripped]
            scene_start_line = i
        elif _TRANSITION_RE.match(stripped):
            if stripped == stripped.upper() or stripped.endswith(":"):
                current_transitions.append(stripped)
        elif stripped and stripped == stripped.upper() and _CHARACTER_RE.match(stripped):
            # Character cue
            char_match = _CHARACTER_RE.match(stripped)
            current_char = (char_match.group(1) if char_match else stripped).strip()
            current_parenthetical = None
            current_characters.append(current_char)
            # Next non-blank line is dialogue
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                if _PARENTHETICAL_RE.match(next_line):
                    current_parenthetical = next_line
                    j += 1
                    if j < len(lines):
                        next_line = lines[j].strip()
                # Collect dialogue lines until blank
                dialogue_lines = [next_line]
                k = j + 1
                while k < len(lines) and lines[k].strip() and not _CHARACTER_RE.match(lines[k].strip()):
                    dialogue_lines.append(lines[k].strip())
                    k += 1
                current_dialogue.append(DialogueLine(
                    character=current_char,
                    text="\n".join(dialogue_lines),
                    parenthetical=current_parenthetical,
                ))
                i = k - 1
        elif stripped:
            current_action.append(stripped)
        i += 1
    # Flush
    if current_action or current_dialogue:
        flush_scene(len(lines) - 1)
    log.info(f"parsed Fountain: {len(scenes)} scenes")
    return scenes


def _parse_slugline(slug: str) -> tuple[str, str, bool | None]:
    """Extract location, time-of-day, interior/exterior from a slugline."""
    m = _SCENE_RE.match(slug)
    if not m:
        return slug, "", None
    location = m.group(1).strip() if m.group(1) else slug
    tod = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else ""
    interior = True if slug.upper().startswith("INT") else (False if slug.upper().startswith("EXT") else None)
    return location, tod, interior


# =====================================================================
# Plain text fallback
# =====================================================================


def parse_plain_text(text: str, *, paragraphs_per_scene: int = 1) -> list[Scene]:
    """Parse plain text into scenes by paragraph.

    Without scene headings, we treat every ``paragraphs_per_scene``
    paragraphs as a scene. Useful for prose / treatment / synopsis.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []
    scenes: list[Scene] = []
    for idx, start in enumerate(range(0, len(paragraphs), paragraphs_per_scene)):
        chunk = paragraphs[start:start + paragraphs_per_scene]
        scene_id = uuid.uuid4().hex[:12]
        scenes.append(Scene(
            id=scene_id,
            number=idx + 1,
            slugline=f"SCENE {idx + 1}",
            location="", time_of_day="", interior=None,
            action="\n\n".join(chunk),
            dialogue=[], characters=[], transitions=[],
            raw="\n\n".join(chunk),
            line_range=(0, 0),
        ))
    log.info(f"parsed plain text: {len(scenes)} scenes")
    return scenes


# =====================================================================
# Top-level facade
# =====================================================================


def parse_script(path: str | Path) -> list[Scene]:
    """Parse a script file. Detects format by extension; falls back to plain text."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"script not found: {path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    return parse_script_text(text, hint=path.suffix.lower())


def parse_script_text(text: str, hint: str = "") -> list[Scene]:
    """Parse script text. ``hint`` is the file extension hint (.fountain, .txt, etc)."""
    if hint in (".fountain", ".spmd"):
        return parse_fountain(text)
    # Try Fountain first (it's plain text anyway, so safe to attempt)
    if any(_SCENE_RE.match(l.strip()) for l in text.splitlines() if l.strip()):
        return parse_fountain(text)
    return parse_plain_text(text)


def scenes_to_prompts(scenes: Iterable[Scene]) -> list[dict[str, Any]]:
    """Turn a list of scenes into a list of prompt-ready dicts."""
    out: list[dict[str, Any]] = []
    for s in scenes:
        out.append({
            "scene_id": s.id,
            "number": s.number,
            "slugline": s.slugline,
            "prompt": s.to_prompt(),
            "characters": s.characters,
            "location": s.location,
            "time_of_day": s.time_of_day,
        })
    return out


# =====================================================================
# PDF / DOCX best-effort loaders
# =====================================================================


def load_text_from_file(path: str | Path) -> str:
    """Load text from a file. Tries PDF, DOCX, then plain text."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".fountain", ".spmd", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in (".docx", ".doc"):
        return _load_docx(path)
    # default
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_pdf(path: Path) -> str:
    try:
        # Try pypdf first (pure Python)
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        pass
    log.warning("no PDF library installed; install pypdf or pdfplumber for PDF support")
    return ""


def _load_docx(path: Path) -> str:
    try:
        import mammoth  # type: ignore
        with open(path, "rb") as f:
            result = mammoth.extract_raw_text(f)
            return result.value
    except ImportError:
        pass
    # python-docx fallback
    try:
        from docx import Document  # type: ignore
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        pass
    log.warning("install mammoth or python-docx for DOCX support")
    return ""
