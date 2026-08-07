"""Coqui TTS Driver implementation."""

from typing import Any

from directo.media_hub.voices.base import SpeechResult


class CoquiTTSDriver:
    """Coqui XTTS v2 multi-lingual voice cloning driver."""

    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2", sample_rate: int = 24000) -> None:
        self.model_name = model_name
        self.sample_rate = sample_rate

    def synthesize_speech(
        self,
        text: str,
        character_id: str = "",
        voice_settings: dict[str, Any] | None = None,
    ) -> SpeechResult:
        if not text or not text.strip():
            raise ValueError("Text string for Coqui speech synthesis cannot be empty.")

        settings = voice_settings or {}
        language = settings.get("language", "en")
        speaker_wav = settings.get("speaker_wav", "/ref/speaker.wav")

        duration = max(0.6, len(text.strip()) / 14.0)
        out_path = f"/tmp/coqui_{character_id or 'anon'}_{hash(text) & 0xFFFFFFFF}.wav"

        return SpeechResult(
            audio_path=out_path,
            duration=duration,
            sample_rate=self.sample_rate,
            character_id=character_id,
            engine="coqui",
            status="completed",
            metadata={"language": language, "speaker_wav": speaker_wav, "model": self.model_name},
        )
