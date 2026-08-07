"""Mock TTS Driver for offline testing."""

from typing import Any

from directo.media_hub.voices.base import SpeechResult


class MockTTSDriver:
    """Mock TTS driver for fast, deterministic speech synthesis during testing."""

    def __init__(self, sample_rate: int = 22050) -> None:
        self.sample_rate = sample_rate

    def synthesize_speech(
        self,
        text: str,
        character_id: str = "",
        voice_settings: dict[str, Any] | None = None,
    ) -> SpeechResult:
        if not text or not text.strip():
            raise ValueError("Text string for Mock speech synthesis cannot be empty.")

        duration = max(0.5, len(text.strip()) * 0.08)
        out_path = f"/tmp/mock_tts_{character_id or 'anon'}_{hash(text) & 0xFFFFFFFF}.wav"

        return SpeechResult(
            audio_path=out_path,
            duration=duration,
            sample_rate=self.sample_rate,
            character_id=character_id,
            engine="mock",
            status="completed",
            metadata={"voice_settings": voice_settings or {}},
        )
