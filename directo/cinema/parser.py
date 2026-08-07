"""Script parser — turn a screenplay into a list of scenes.

Supports Fountain, Markdown, Portuguese/English sluglines, plain text, and PDF/DOCX.
Includes OCR fallback for scanned PDFs and multi-core parallel batch processing.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    slugline: str                       # "INT. KITCHEN - DAY" or "CENA 1 - INT"
    location: str = ""                  # "INT. KITCHEN"
    time_of_day: str = ""               # "DAY" | "NIGHT" | "DUSK" | etc.
    interior: bool | None = None        # True for INT/INTERIOR, False for EXT/EXTERIOR, None if unknown
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
            text = self.action.strip()
            if len(text) > 400:
                text = text[:400].rsplit(".", 1)[0] + "."
            parts.append(text)
        return " — ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "number": self.number, "slugline": self.slugline,
            "heading": self.slugline,
            "location": self.location, "time_of_day": self.time_of_day,
            "interior": self.interior, "action": self.action,
            "prompt": self.to_prompt(),
            "dialogue": [{"character": d.character, "text": d.text, "line": d.text,
                          "parenthetical": d.parenthetical} for d in self.dialogue],
            "characters": self.characters,
            "transitions": self.transitions, "raw": self.raw,
            "line_range": list(self.line_range),
        }


# =====================================================================
# Fountain / Markdown / Multi-language parser
# =====================================================================

# Extended Scene Heading regex: INT, EXT, EST, INT/EXT, INTERIOR, EXTERIOR, CENA \d+
_SCENE_RE = re.compile(
    r"^(?:#+\s*)?(?:INT|EXT|EST|INT\.\/EXT|INT\/EXT|I\/E|INTERIOR|EXTERIOR|CENA\s+\d+|CENA|ESTÚDIO|ESTUDIO)[\s\.\/\-\:]+(.+?)(?:\s*[-–—:]\s*(.+))?$",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"^[A-Z\s]+TO:\s*$|^(?:FADE IN|CUT TO|DISSOLVE TO|SMASH CUT TO|MATCH CUT TO|CORTE PARA|CORTE):?$",
    re.IGNORECASE,
)
# Character cue: line in ALL CAPS, with (V.O.) / (O.S.) extension
_CHARACTER_RE = re.compile(r"^([A-Z][A-Z0-9 .\-'À-ſ]+)(\s*\([^)]+\))?\s*$")
_PARENTHETICAL_RE = re.compile(r"^\(.+\)\s*$")

# Noise filter for character cue deduplication
NOISE_CHARACTERS = {
    "SIM", "NÃO", "NAO", "CONTINUA", "CORREDOR", "SALA", "FIM", "CORTE", "FADE",
    "FADE IN", "FADE OUT", "CUT TO", "DISSOLVE TO", "DIÁLOGO", "DIALOGO", "VERSO",
    "NOTA", "OBS", "VOZ", "TODOS", "AMBOS", "GERAL", "VISÃO", "VISAO", "CENA",
    "PÁGINA", "PAGINA", "CHAPTER", "CAPÍTULO", "CAPITULO", "VOL", "PARTE", "EXT", "INT"
}


def _clean_character_name(name: str) -> str | None:
    """Sanitize character name and return None if it is a noise word."""
    if not name:
        return None
    clean = re.sub(r"\s*\([^)]*\)", "", name).strip().upper()
    clean = re.sub(r"^[0-9\.\-\s]+", "", clean)
    if not clean or len(clean) < 2:
        return None
    if clean in NOISE_CHARACTERS:
        return None
    if not re.search(r"[A-ZÀ-ÿ]", clean):
        return None
    return clean


def parse_fountain(text: str) -> list[Scene]:
    """Parse a Fountain / Markdown screenplay into a list of scenes."""
    lines = text.splitlines()
    scenes: list[Scene] = []
    current_action: list[str] = []
    current_dialogue: list[DialogueLine] = []
    current_chars: set[str] = set()
    current_slug: str = ""
    scene_start_line: int = 0
    header_buffer: list[str] = []

    def flush_scene(end_line: int) -> None:
        nonlocal current_action, current_dialogue, current_chars, current_slug, scene_start_line, header_buffer
        if not current_slug and not current_action and not current_dialogue:
            return
        
        # If no slugline exists and no scenes have been parsed yet, buffer initial title metadata
        if not current_slug and not scenes:
            header_buffer.extend(current_action)
            current_action = []
            return

        clean_slug = current_slug.lstrip("#").strip() if current_slug else ""
        loc, tod, interior = _parse_slugline(clean_slug) if clean_slug else ("", "", None)

        action_lines = list(header_buffer) + current_action
        header_buffer = []
        action_text = "\n".join(action_lines).strip()

        filtered_chars = sorted({_clean_character_name(c) for c in current_chars if _clean_character_name(c)})

        scenes.append(Scene(
            id=uuid.uuid4().hex[:12],
            number=len(scenes) + 1,
            slugline=clean_slug or f"SCENE {len(scenes) + 1}",
            location=loc,
            time_of_day=tod,
            interior=interior,
            action=action_text,
            dialogue=list(current_dialogue),
            characters=filtered_chars,
            transitions=[],
            raw=action_text,
            line_range=(scene_start_line, end_line),
        ))
        current_action = []
        current_dialogue = []
        current_chars = set()
        current_slug = ""
        scene_start_line = end_line + 1

    i = 0
    pending_char: str | None = None
    pending_paren: str | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue

        if _SCENE_RE.match(stripped):
            flush_scene(i - 1)
            current_slug = stripped
            i += 1
            continue

        m_char = _CHARACTER_RE.match(stripped)
        if m_char and stripped == stripped.upper() and i + 1 < len(lines) and lines[i + 1].strip():
            char_name = m_char.group(1).strip()
            cleaned_char = _clean_character_name(char_name)
            if cleaned_char:
                pending_char = char_name
                current_chars.add(cleaned_char)
                i += 1
                if i < len(lines) and _PARENTHETICAL_RE.match(lines[i].strip()):
                    pending_paren = lines[i].strip().strip("()")
                    i += 1
                if i < len(lines) and lines[i].strip():
                    current_dialogue.append(DialogueLine(
                        character=pending_char,
                        text=lines[i].strip(),
                        parenthetical=pending_paren,
                    ))
                    pending_char = None
                    pending_paren = None
                i += 1
                continue

        current_action.append(stripped)
        i += 1

    if current_slug or current_action or current_dialogue:
        flush_scene(len(lines) - 1)

    log.info(f"parsed Fountain: {len(scenes)} scenes")
    return scenes


def _parse_slugline(slug: str) -> tuple[str, str, bool | None]:
    """Extract location, time-of-day, interior/exterior from a slugline."""
    clean = slug.lstrip("#").strip()
    clean_prefix = re.sub(r"^CENA\s+\d+[\s\.\/\-\:]*", "", clean, flags=re.IGNORECASE).strip() or clean
    m = _SCENE_RE.match(clean_prefix)
    if not m:
        m = _SCENE_RE.match(clean)
    if not m:
        return clean_prefix, "", None
    location = m.group(1).strip() if m.group(1) else clean_prefix
    tod = (m.group(2) or "").strip() if m.lastindex and m.lastindex >= 2 else ""
    upper_clean = clean.upper()
    interior: bool | None = None
    if "INTERIOR" in upper_clean or "INT." in upper_clean or "INT/" in upper_clean or upper_clean.startswith("INT"):
        interior = True
    elif "EXTERIOR" in upper_clean or "EXT." in upper_clean or "EXT/" in upper_clean or upper_clean.startswith("EXT"):
        interior = False
    return location, tod, interior


# =====================================================================
# Plain text fallback
# =====================================================================


def parse_plain_text(text: str, *, paragraphs_per_scene: int = 1) -> list[Scene]:
    """Parse plain text into scenes by paragraph."""
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
# Top-level facade & Multi-core Batch Processing
# =====================================================================


def parse_script(path: str | Path) -> list[Scene]:
    """Parse a script file. Detects format by extension; falls back to plain text."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"script not found: {path}")
    text = load_text_from_file(path)
    return parse_script_text(text, hint=path.suffix.lower())


def parse_script_text(text: str, hint: str = "") -> list[Scene]:
    """Parse script text. ``hint`` is the file extension hint (.fountain, .md, .txt, etc)."""
    if hint in (".fountain", ".spmd", ".md", ".markdown"):
        return parse_fountain(text)
    if any(_SCENE_RE.match(l.strip()) for l in text.splitlines() if l.strip()):
        return parse_fountain(text)
    return parse_plain_text(text)


def _parse_single_file_worker(path_str: str) -> dict[str, Any]:
    """Worker function for ProcessPoolExecutor batch script parsing."""
    path = Path(path_str)
    start_t = time.time()
    try:
        text = load_text_from_file(path)
        scenes = parse_script_text(text, hint=path.suffix.lower())
        return {
            "path": str(path),
            "status": "SUCCESS" if text.strip() else "EMPTY_TEXT",
            "char_count": len(text),
            "scene_count": len(scenes),
            "duration_s": round(time.time() - start_t, 3),
        }
    except Exception as exc:
        return {
            "path": str(path),
            "status": f"ERROR: {exc}",
            "char_count": 0,
            "scene_count": 0,
            "duration_s": round(time.time() - start_t, 3),
        }


def parse_scripts_batch(paths: Iterable[str | Path], max_workers: int | None = None) -> list[dict[str, Any]]:
    """Parse multiple script files in parallel using ProcessPoolExecutor."""
    path_strs = [str(p) for p in paths]
    if not path_strs:
        return []
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_parse_single_file_worker, p): p for p in path_strs}
        for future in as_completed(futures):
            results.append(future.result())
    return results


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
# PDF / DOCX best-effort loaders with OCR Fallback
# =====================================================================


def load_text_from_file(path: str | Path) -> str:
    """Load text from a file. Tries PDF (with OCR fallback), DOCX, then plain text."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".txt", ".fountain", ".spmd", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in (".docx", ".doc"):
        return _load_docx(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_pdf(path: Path) -> str:
    """Extract text from PDF using pypdf -> pdfplumber -> pytesseract OCR fallback."""
    text = ""
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        pass

    if text.strip():
        return text

    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        pass

    if text.strip():
        return text

    # OCR Fallback (for scanned / image-based PDFs)
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_path  # type: ignore
        images = convert_from_path(str(path), first_page=1, last_page=5)
        ocr_pages = [pytesseract.image_to_string(img, lang="por+eng") for img in images]
        text = "\n".join(ocr_pages)
    except Exception as exc:
        log.debug(f"OCR fallback unavailable for {path}: {exc}")

    return text


def _load_docx(path: Path) -> str:
    try:
        import mammoth  # type: ignore
        with open(path, "rb") as f:
            result = mammoth.extract_raw_text(f)
            return result.value
    except ImportError:
        pass
    try:
        from docx import Document  # type: ignore
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        pass
    return ""
