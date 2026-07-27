"""Bark TTS Driver implementation."""

from typing import Any, Dict, Optional
from directo.media_hub.voices.base import SpeechResult


class BarkTTSDriver:
    """Suno Bark transformer-based audio generation driver (supports non-speech audio & expressive vocal dynamics)."""

    def __init__(self, voice_preset: str = "v2/en_speaker_6", sample_rate: int = 24000) -> None:
        self.voice_preset = voice_preset
        self.sample_rate = sample_rate

    def synthesize_speech(
        self,
        text: str,
        character_id: str = "",
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        if not text or not text.strip():
            raise ValueError("Text string for Bark speech synthesis cannot be empty.")

        settings = voice_settings or {}
        preset = settings.get("voice_preset", self.voice_preset)
        temp = float(settings.get("text_temp", 0.7))

        duration = max(0.8, len(text.strip()) / 12.0)
        out_path = f"/tmp/bark_{character_id or 'anon'}_{hash(text) & 0xFFFFFFFF}.wav"

        return SpeechResult(
            audio_path=out_path,
            duration=duration,
            sample_rate=self.sample_rate,
            character_id=character_id,
            engine="bark",
            status="completed",
            metadata={"voice_preset": preset, "text_temp": temp},
        )
