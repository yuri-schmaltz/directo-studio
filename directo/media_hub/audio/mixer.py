"""AudioMixer for multi-track mixing and sidechain ducking integration."""

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Tuple

from directo.media_hub.audio.ducking import AudioDuckingEngine


@dataclass
class MixedAudioResult:
    output_path: str
    duration: float
    ducking_applied: bool
    channels: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


class AudioMixer:
    """Manages multi-track audio mixing (speech, background music, sound effects) with sidechain ducking."""

    def __init__(self, ducking_engine: Optional[AudioDuckingEngine] = None) -> None:
        self.ducking_engine = ducking_engine or AudioDuckingEngine()

    def mix_tracks(
        self,
        speech_tracks: Optional[List[str]] = None,
        bgm_track: Optional[str] = None,
        sfx_tracks: Optional[List[str]] = None,
        speech_intervals: Optional[List[Tuple[float, float]]] = None,
        ducking_config: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> MixedAudioResult:
        speech_tracks = speech_tracks or []
        sfx_tracks = sfx_tracks or []
        ducking_config = ducking_config or {}

        attenuation_db = ducking_config.get("attenuation_db", -12.0)
        ducking_applied = False

        out_path = output_path or f"/tmp/mixed_audio_{hash(str(speech_tracks)) & 0xFFFFFFFF}.wav"

        if bgm_track and speech_intervals:
            # Apply sidechain compression ducking to BGM
            ducked_bgm = self.ducking_engine.apply_ducking(
                bgm_path=bgm_track,
                speech_intervals=speech_intervals,
                attenuation_db=attenuation_db,
            )
            ducking_applied = True

        # Simulate audio mix duration based on inputs
        duration = 10.0

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"MOCK_MIXED_AUDIO_SPEECH_{len(speech_tracks)}_SFX_{len(sfx_tracks)}_DUCKING_{ducking_applied}")

        return MixedAudioResult(
            output_path=out_path,
            duration=duration,
            ducking_applied=ducking_applied,
            channels=2,
            metadata={
                "speech_count": len(speech_tracks),
                "has_bgm": bool(bgm_track),
                "sfx_count": len(sfx_tracks),
                "attenuation_db": attenuation_db,
            },
        )
