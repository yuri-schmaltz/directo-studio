"""Cinema Prompt Engine — rule-based prompt validation and enhancement.

A "rule" checks a user prompt against cinema / physics / historical
constraints. Rules are pure functions of the prompt and optional
context. They return a :class:`RuleResult` describing what to do.

Inspired by DirectorsConsole's 56+ rules system.

Rule types:
- :class:`RuleKind.BLOCK`  — fail the prompt if the rule fires.
- :class:`RuleKind.WARN`   — emit a warning but allow the prompt.
- :class:`RuleKind.SUGGEST` — emit a suggestion to add to the prompt.
- :class:`RuleKind.INJECT` — automatically inject a phrase.

Built-in rule packs:
- ``era``: historical anachronism (smartphones in 1920, etc.)
- ``physics``: physical impossibilities (submerged in fire, etc.)
- ``cinematography``: missing lens / lighting / aspect ratio cues
- ``consistency``: cross-prompt character consistency hints

Users can add their own rules via :meth:`CinemaEngine.add_rule`.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

from directo.observability import get_logger

log = get_logger("directo.cinema.engine")


# =====================================================================
# Domain model
# =====================================================================


class RuleKind(str, enum.Enum):
    BLOCK = "block"
    WARN = "warn"
    SUGGEST = "suggest"
    INJECT = "inject"


@dataclass
class RuleResult:
    """The outcome of evaluating one rule against one prompt."""

    rule_id: str
    rule_name: str
    kind: RuleKind
    message: str
    suggestion: str | None = None  # for SUGGEST
    injection: str | None = None   # for INJECT
    matched_text: str | None = None


@dataclass
class EngineReport:
    """The full report of running all rules against one prompt."""

    prompt: str
    results: list[RuleResult]
    blocked: bool
    warnings: list[str]
    suggestions: list[str]
    injections: list[str]
    augmented_prompt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "blocked": self.blocked,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "injections": self.injections,
            "augmented_prompt": self.augmented_prompt,
            "results": [
                {**asdict(r), "kind": r.kind.value}
                for r in self.results
            ],
        }


# A rule is a callable: (prompt, context) -> list[RuleResult]
Rule = Callable[[str, dict[str, Any]], list[RuleResult]]


# =====================================================================
# Built-in rule packs
# =====================================================================


# ---------- Era pack ----------
# 56+ rules total in DirectorsConsole; we ship a representative starter set.
# Each rule fires when the context era is BEFORE the rule's "before_year" AND
# the prompt contains a forbidden token.

_ERA_BLOCKS: list[tuple[str, int, str, list[str]]] = [
    # (rule_id, before_year, message, forbidden_tokens)
    ("pre-1900", 1900, "photography not invented yet", ["photograph", "camera lens", "35mm", "dslr"]),
    ("pre-1927", 1927, "no synchronized sound in film", ["talking", "speaks to", "dialogue", "voice over"]),
    ("pre-1935", 1935, "no three-strip Technicolor", ["technicolor", "3-strip technicolor", "saturated color film"]),
    ("pre-1948", 1948, "no television sets", ["television", "tv set", "cathode ray", "broadcast"]),
    ("pre-1973", 1973, "no mobile phones", ["cell phone", "mobile phone", "iphone", "android", "smartphone", "texting"]),
    ("pre-1985", 1985, "no consumer digital cameras", ["digital camera", "dslr", "mirrorless camera", "memory card"]),
    ("pre-2007", 2007, "no iPhones", ["iphone", "ios phone", "facetime"]),
    ("pre-2010", 2010, "no widespread LED lighting in film", ["led panel lighting", "rgb led"]),
]

def _era_years(ctx_era: Any) -> list[int]:
    """Extract integer years from a context era value.
    
    "1920-1930" -> [1920, 1930]
    "pre-1973" -> [1900, 1972]
    "1970s" -> [1970, 1979]
    1970 -> [1970, 1970]
    """
    if ctx_era is None:
        return []
    if isinstance(ctx_era, int):
        return [ctx_era, ctx_era]
    s = str(ctx_era).strip().lower()
    if not s:
        return []
    if s.startswith("pre-"):
        rest = s[4:].rstrip("s")
        try:
            return [1900, int(rest) - 1]
        except ValueError:
            return []
    if "-" in s:
        try:
            a, b = s.split("-", 1)
            a = a.rstrip("s")
            b = b.rstrip("s")
            return [int(a), int(b)]
        except ValueError:
            return []
    if s.endswith("s") and len(s) == 5:  # "1970s"
        try:
            base = int(s[:4])
            return [base, base + 9]
        except ValueError:
            return []
    try:
        y = int(s)
        return [y, y]
    except ValueError:
        return []


# Each rule fires when a forbidden token is in the prompt AND the context
# era is fully before the rule's threshold.
def make_era_rule(rule_id: str, before_year: int, message: str, tokens: list[str]) -> Rule:
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in tokens) + r")\b", re.IGNORECASE)
    def rule(prompt: str, context: dict[str, Any]) -> list[RuleResult]:
        years = _era_years(context.get("era"))
        if not years:
            return []
        # The rule fires if the LATEST year in the context era is before the threshold
        if years[1] >= before_year:
            return []
        for m in pattern.finditer(prompt):
            return [RuleResult(
                rule_id=f"era-{rule_id}",
                rule_name=f"era:{rule_id}",
                kind=RuleKind.BLOCK,
                message=f"era={rule_id} (before {before_year}): {message} (found '{m.group(0)}')",
                matched_text=m.group(0),
            )]
        return []
    return rule


# ---------- Physics pack ----------

_PHYSICS_RULES: list[tuple[str, str, str, RuleKind]] = [
    ("fire-underwater", "fire and water together is impossible",
     r"\b(fire|burning|flame|blaze)\b.*\b(underwater|submerged|under the water|underwater)\b|\b(underwater|submerged)\b.*\b(fire|burning|flame)\b",
     RuleKind.BLOCK),
    ("smoke-in-vacuum", "smoke cannot exist in vacuum",
     r"\bsmoke\b.*\b(space|vacuum|outer space)\b|\b(space|vacuum)\b.*\bsmoke\b",
     RuleKind.BLOCK),
    ("sound-in-space", "no sound propagation in vacuum",
     r"\b(sound|roar|explosion|music)\b.*\b(space|vacuum|moon)\b|\b(space|vacuum|moon)\b.*\b(sound|roar|explosion)\b",
     RuleKind.WARN),
    ("shadow-occlusion", "occluded light source cannot cast shadow",
     r"\b(shadow|shadows)\b.*\b(no light|completely dark|occluded)\b",
     RuleKind.WARN),
]


def make_physics_rule(rule_id: str, message: str, pattern: str, kind: RuleKind) -> Rule:
    rx = re.compile(pattern, re.IGNORECASE)
    def rule(prompt: str, context: dict[str, Any]) -> list[RuleResult]:
        for m in rx.finditer(prompt):
            return [RuleResult(
                rule_id=f"physics-{rule_id}",
                rule_name=f"physics:{rule_id}",
                kind=kind,
                message=message,
                matched_text=m.group(0),
            )]
        return []
    return rule


# ---------- Cinematography pack ----------
# These are SUGGEST rules: not blocking, but recommending what's missing

_CINEMA_SUGGESTS: list[tuple[str, str, str, str]] = [
    # (id, message, missing_token_pattern, suggestion_to_add)
    ("missing-lighting", "no lighting cue — suggest adding one",
     r"^(?!.*\b(lighting|light|illuminat|shadow|chiaroscuro|rim light|backlight|golden hour|blue hour|cinematic|overcast)\b).*$",
     "cinematic lighting"),
    ("missing-lens", "no lens/camera cue — suggest adding one",
     r"^(?!.*\b(lens|focal|mm|mm lens|anamorphic|wide angle|telephoto|macro|fish.?eye|tilt.?shift|prime|zoom)\b).*$",
     "shot on 35mm lens"),
    ("missing-camera", "no camera angle cue — suggest adding",
     r"^(?!.*\b(angle|aerial|low angle|high angle|top.?down|over.?the.?shoulder|close.?up|wide|medium|pan|tilt|dolly|tracking|crane|handheld|steadicam|POV)\b).*$",
     "low angle cinematic shot"),
    ("missing-aspect", "no aspect ratio cue — suggest",
     r"^(?!.*\b(aspect|widescreen|cinemascope|anamorphic|2\.39|16:9|21:9|4:3|1\.85)\b).*$",
     "2.39:1 anamorphic widescreen"),
    ("missing-grade", "no color grade cue — suggest",
     r"^(?!.*\b(grade|grading|color grade|warm|cool|teal|orange|desaturated|muted|pastel)\b).*$",
     "warm cinematic color grade"),
]


def make_cinema_suggest(rule_id: str, message: str, missing_pattern: str, suggestion: str) -> Rule:
    """Suggest a missing cinematography cue."""
    rx = re.compile(missing_pattern, re.IGNORECASE | re.DOTALL)

    def rule(prompt: str, context: dict[str, Any]) -> list[RuleResult]:
        # If user disabled suggests via context, skip
        if context.get("skip_suggests"):
            return []
        # If prompt is too short (< 5 words), definitely suggest
        short = len(prompt.split()) < 5
        # If the missing pattern matches, suggest
        if short or rx.match(prompt):
            return [RuleResult(
                rule_id=f"cinema-{rule_id}",
                rule_name=f"cinema:{rule_id}",
                kind=RuleKind.SUGGEST,
                message=message,
                suggestion=suggestion,
            )]
        return []
    return rule


# ---------- Consistency pack ----------
# Injects character/continuity hints

def make_consistency_inject(context_key: str, template: str) -> Rule:
    def rule(prompt: str, context: dict[str, Any]) -> list[RuleResult]:
        val = context.get(context_key)
        if not val:
            return []
        return [RuleResult(
            rule_id=f"consistency-{context_key}",
            rule_name=f"consistency:{context_key}",
            kind=RuleKind.INJECT,
            message=f"injecting {context_key} context",
            injection=template.format(value=val),
        )]
    return rule


def _builtin_rules() -> list[Rule]:
    rules: list[Rule] = []
    for rid, before_year, msg, toks in _ERA_BLOCKS:
        rules.append(make_era_rule(rid, before_year, msg, toks))
    for rid, msg, pat, kind in _PHYSICS_RULES:
        rules.append(make_physics_rule(rid, msg, pat, kind))
    for rid, msg, pat, sug in _CINEMA_SUGGESTS:
        rules.append(make_cinema_suggest(rid, msg, pat, sug))
    rules.append(make_consistency_inject(
        "character", "{value}, consistent character design across frames"))
    rules.append(make_consistency_inject(
        "lighting_style", "lighting: {value}"))
    return rules


# =====================================================================
# Engine
# =====================================================================


class CinemaEngine:
    """The rule evaluator.

    Usage::

        engine = CinemaEngine()
        report = engine.evaluate("a dragon underwater with fire", context={"era": "pre-1900"})
        if report.blocked:
            print("Blocked:", report.warnings)
        else:
            prompt_to_use = report.augmented_prompt
    """

    def __init__(self, rules: Iterable[Rule] | None = None) -> None:
        self._rules: list[Rule] = list(rules) if rules is not None else _builtin_rules()
        log.info(f"CinemaEngine initialized with {len(self._rules)} rules")

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def remove_rule(self, predicate: Callable[[Rule], bool]) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if not predicate(r)]
        return before - len(self._rules)

    def evaluate(self, prompt: str, context: dict[str, Any] | None = None) -> EngineReport:
        """Run all rules against ``prompt`` and produce a report."""
        context = context or {}
        results: list[RuleResult] = []
        for rule in self._rules:
            try:
                rs = rule(prompt, context)
                results.extend(rs)
            except Exception as exc:  # noqa: BLE001
                log.warning(f"rule raised {exc!r}; skipped")

        blocked = any(r.kind == RuleKind.BLOCK for r in results)
        warnings = [r.message for r in results if r.kind in (RuleKind.BLOCK, RuleKind.WARN)]
        suggestions = [r.suggestion for r in results if r.kind == RuleKind.SUGGEST and r.suggestion]
        injections = [r.injection for r in results if r.kind == RuleKind.INJECT and r.injection]

        # Build the augmented prompt
        augmented = prompt.strip().rstrip(",").rstrip()
        if injections:
            augmented = augmented + ", " + ", ".join(injections)
        if suggestions and context.get("auto_apply_suggests", True):
            augmented = augmented + ", " + ", ".join(suggestions)

        return EngineReport(
            prompt=prompt,
            results=results,
            blocked=blocked,
            warnings=warnings,
            suggestions=suggestions,
            injections=injections,
            augmented_prompt=augmented,
        )
