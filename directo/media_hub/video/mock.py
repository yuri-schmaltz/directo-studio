"""Mock Video Driver for testing."""

from typing import Any, Dict, List, Optional
from directo.media_hub.video.base import VideoResult
from directo.media_hub.video.comfyui import parse_aspect_ratio


class MockVideoDriver:
    """Mock video generation driver producing deterministic VideoResult outputs."""

    def __init__(self, output_dir: str = "/tmp") -> None:
        self.output_dir = output_dir
        self.generated_jobs: List[Dict[str, Any]] = []

    def generate_video(
        self,
        prompt: str,
        loras: Optional[List[Dict[str, Any]]] = None,
        seed: int = 42,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
    ) -> VideoResult:
        if duration <= 0:
            raise ValueError(f"Video duration must be greater than 0, got {duration}")

        width, height = parse_aspect_ratio(aspect_ratio)

        job_id = len(self.generated_jobs) + 1
        video_path = f"{self.output_dir}/mock_video_job_{job_id}.mp4"

        record = {
            "job_id": job_id,
            "prompt": prompt,
            "loras": loras or [],
            "seed": seed,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "video_path": video_path,
        }
        self.generated_jobs.append(record)

        return VideoResult(
            video_path=video_path,
            duration=duration,
            width=width,
            height=height,
            fps=30,
            status="completed",
            metadata={"job_id": job_id, "driver": "MockVideoDriver"},
        )
