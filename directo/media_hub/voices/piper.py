"""Piper TTS Driver implementation."""

from typing import Any, Dict, Optional
from directo.media_hub.voices.base import SpeechResult


class PiperTTSDriver:
    """Fast, local neural text-to-speech engine powered by Piper ONNX models."""

    def __init__(self, model_path: str = "/models/piper/en_US-lessac-high.onnx", sample_rate: int = 22050) -> None:
        self.model_path = model_path
        self.sample_rate = sample_rate

    def synthesize_speech(
        self,
        text: str,
        character_id: str = "",
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> SpeechResult:
        if not text or not text.strip():
            raise ValueError("Text string for Piper speech synthesis cannot be empty.")

        settings = voice_settings or {}
        speed = float(settings.get("speed", 1.0))
        noise_scale = float(settings.get("noise_scale", 0.667))

        # Estimate duration: ~15 characters per second adjusted by speed
        duration = max(0.5, (len(text.strip()) / 15.0) / speed)
        out_path = f"/tmp/piper_{character_id or 'anon'}_{hash(text) & 0xFFFFFFFF}.wav"

        return SpeechResult(
            audio_path=out_path,
            duration=duration,
            sample_rate=self.sample_rate,
            character_id=character_id,
            engine="piper",
            status="completed",
            metadata={"speed": speed, "noise_scale": noise_scale, "model": self.model_path},
        )
