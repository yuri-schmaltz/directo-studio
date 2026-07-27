"""LocalMediaOrchestrator async facade connecting video, voice, subtitle, and audio engines."""

import asyncio
from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional

from directo.media_hub.audio.ducking import AudioDuckingEngine
from directo.media_hub.audio.mixer import AudioMixer
from directo.media_hub.subtitles.whisper import WhisperSubtitleGenerator
from directo.media_hub.video.ffmpeg import FFmpegRenderer
from directo.media_hub.video.mock import MockVideoDriver
from directo.media_hub.voices.mock import MockTTSDriver


@dataclass
class OrchestrationRequest:
    prompt: str
    character_ids: List[str] = field(default_factory=list)
    environment_id: Optional[str] = None
    script_events: List[Dict[str, Any]] = field(default_factory=list)
    aspect_ratio: str = "16:9"
    duration: float = 5.0
    bgm_path: Optional[str] = None
    ducking_db: float = -12.0
    output_dir: str = "/tmp"


@dataclass
class OrchestrationResult:
    video_path: str
    audio_path: str
    subtitle_path: str
    final_output_path: str
    duration: float
    status: str = "completed"
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalMediaOrchestrator:
    """Asynchronous facade coordinating full script-to-video production pipeline."""

    def __init__(
        self,
        video_driver: Any = None,
        tts_driver: Any = None,
        subtitle_gen: Any = None,
        audio_mixer: Any = None,
        ffmpeg_renderer: Any = None,
    ) -> None:
        self.video_driver = video_driver or MockVideoDriver()
        self.tts_driver = tts_driver or MockTTSDriver()
        self.subtitle_gen = subtitle_gen or WhisperSubtitleGenerator()
        self.audio_mixer = audio_mixer or AudioMixer()
        self.ffmpeg_renderer = ffmpeg_renderer or FFmpegRenderer()

    async def generate_media(self, request: OrchestrationRequest) -> OrchestrationResult:
        if not request.prompt or not request.prompt.strip():
            raise ValueError("OrchestrationRequest prompt cannot be empty.")
        if request.duration <= 0:
            raise ValueError(f"OrchestrationRequest duration must be positive, got {request.duration}")

        os.makedirs(request.output_dir, exist_ok=True)

        # Step 1: Synthesize speech for script dialogue events (TTS)
        speech_results = []
        speech_intervals = []
        current_time = 0.0

        if request.script_events:
            for ev in request.script_events:
                text = ev.get("text", "")
                speaker = ev.get("speaker", "")
                if text:
                    # Run CPU/IO bound synthesis
                    speech_res = await asyncio.to_thread(
                        self.tts_driver.synthesize_speech,
                        text=text,
                        character_id=speaker,
                    )
                    speech_results.append(speech_res.audio_path)
                    speech_intervals.append((current_time, current_time + speech_res.duration))
                    current_time += speech_res.duration + 0.2

        # Step 2: Generate subtitles (.srt, .vtt, .json alignment)
        ref_audio = speech_results[0] if speech_results else "/tmp/dummy_ref_audio.wav"
        sub_res = await asyncio.to_thread(
            self.subtitle_gen.generate_subtitles,
            speech_audio_path=ref_audio,
            dialogue_events=request.script_events,
            output_dir=request.output_dir,
        )

        # Step 3: Multi-track audio mixing with BGM sidechain ducking
        mix_res = await asyncio.to_thread(
            self.audio_mixer.mix_tracks,
            speech_tracks=speech_results,
            bgm_track=request.bgm_path,
            speech_intervals=speech_intervals,
            ducking_config={"attenuation_db": request.ducking_db},
            output_path=os.path.join(request.output_dir, f"orchestration_mix_{hash(request.prompt) & 0xFFFFFFFF}.wav"),
        )

        # Step 4: Render video frames via Video Driver (ComfyUI / Mock)
        video_res = await asyncio.to_thread(
            self.video_driver.generate_video,
            prompt=request.prompt,
            seed=42,
            duration=request.duration,
            aspect_ratio=request.aspect_ratio,
        )

        # Step 5: Final FFmpeg composite render (video + audio + subtitle burn-in)
        final_path = await asyncio.to_thread(
            self.ffmpeg_renderer.render_video,
            raw_video=video_res.video_path,
            audio_track=mix_res.output_path,
            subtitles_srt=sub_res.srt_path,
            aspect_ratio=request.aspect_ratio,
            output_path=os.path.join(request.output_dir, f"final_production_{hash(request.prompt) & 0xFFFFFFFF}.mp4"),
        )

        return OrchestrationResult(
            video_path=video_res.video_path,
            audio_path=mix_res.output_path,
            subtitle_path=sub_res.srt_path,
            final_output_path=final_path,
            duration=request.duration,
            status="completed",
            metadata={
                "aspect_ratio": request.aspect_ratio,
                "dialogue_events_count": len(request.script_events),
                "ducking_applied": mix_res.ducking_applied,
            },
        )
