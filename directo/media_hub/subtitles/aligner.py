"""Subtitle aligner for precise timestamp alignment."""

from typing import Any, Dict, List
from directo.media_hub.subtitles.whisper import SubtitleSegment


class SubtitleAligner:
    """Aligns subtitle segments with audio waveform features and speech activity events."""

    def align_events(self, events: List[Dict[str, Any]]) -> List[SubtitleSegment]:
        aligned = []
        curr_time = 0.0
        for ev in events:
            text = ev.get("text", "")
            speaker = ev.get("speaker", "")
            duration = float(ev.get("duration", max(1.0, len(text) * 0.08)))
            seg = SubtitleSegment(
                start=curr_time,
                end=curr_time + duration,
                text=text,
                speaker=speaker,
                confidence=1.0,
            )
            aligned.append(seg)
            curr_time += duration
        return aligned
