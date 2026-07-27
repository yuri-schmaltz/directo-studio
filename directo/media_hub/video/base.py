"""Base types and protocols for video generation drivers."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class VideoResult:
    video_path: str
    duration: float
    width: int = 1920
    height: int = 1080
    fps: int = 30
    status: str = "completed"
    metadata: Dict[str, Any] = field(default_factory=dict)


class VideoDriver(Protocol):
    def generate_video(
        self,
        prompt: str,
        loras: Optional[List[Dict[str, Any]]] = None,
        seed: int = 42,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
    ) -> VideoResult:
        ...
