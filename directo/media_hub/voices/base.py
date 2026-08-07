"""Base classes and protocols for TTS drivers."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SpeechResult:
    audio_path: str
    duration: float
    sample_rate: int = 22050
    character_id: str = ""
    engine: str = "mock"
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


class TTSDriver(Protocol):
    def synthesize_speech(
        self,
        text: str,
        character_id: str = "",
        voice_settings: dict[str, Any] | None = None,
    ) -> SpeechResult:
        ...
