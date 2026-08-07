"""AudioDuckingEngine for sidechain compression during character narration."""

import math
from typing import Any


class AudioDuckingEngine:
    """Applies sidechain compression ducking to background music when speech is active."""

    def __init__(
        self,
        default_ducking_db: float = -12.0,
        attack_ms: float = 50.0,
        release_ms: float = 200.0,
    ) -> None:
        self.default_ducking_db = default_ducking_db
        self.attack_ms = attack_ms
        self.release_ms = release_ms

    def calculate_ducking_envelope(
        self,
        speech_intervals: list[tuple[float, float]],
        total_duration: float,
        attenuation_db: float | None = None,
    ) -> list[dict[str, Any]]:
        """Calculates volume envelope keyframes for BGM track given speech intervals."""
        atten_db = self.default_ducking_db if attenuation_db is None else attenuation_db

        # Convert dB to linear volume factor: 10^(dB / 20)
        ducked_gain = math.pow(10.0, atten_db / 20.0)

        envelope = []
        if not speech_intervals:
            envelope.append({"time": 0.0, "gain": 1.0})
            envelope.append({"time": total_duration, "gain": 1.0})
            return envelope

        prev_time = 0.0
        for start, end in sorted(speech_intervals):
            attack_sec = self.attack_ms / 1000.0
            release_sec = self.release_ms / 1000.0

            duck_start = max(0.0, start - attack_sec)
            duck_release_end = min(total_duration, end + release_sec)

            if duck_start > prev_time:
                envelope.append({"time": duck_start, "gain": 1.0})

            envelope.append({"time": start, "gain": ducked_gain})
            envelope.append({"time": end, "gain": ducked_gain})
            envelope.append({"time": duck_release_end, "gain": 1.0})

            prev_time = duck_release_end

        if prev_time < total_duration:
            envelope.append({"time": total_duration, "gain": 1.0})

        return envelope

    def apply_ducking(
        self,
        bgm_path: str,
        speech_intervals: list[tuple[float, float]],
        attenuation_db: float | None = None,
        output_path: str | None = None,
    ) -> str:
        if not bgm_path or not isinstance(bgm_path, str):
            raise ValueError("BGM path must be a valid non-empty string.")

        atten_db = self.default_ducking_db if attenuation_db is None else attenuation_db
        out_file = output_path or f"/tmp/ducked_{hash(bgm_path) & 0xFFFFFFFF}.wav"

        envelope = self.calculate_ducking_envelope(speech_intervals, total_duration=10.0, attenuation_db=atten_db)

        # Write mock ducked audio file
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(f"MOCK_DUCKED_AUDIO_DB_{atten_db}_ENVELOPE_COUNT_{len(envelope)}")

        return out_file
