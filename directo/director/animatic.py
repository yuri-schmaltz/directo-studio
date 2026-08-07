"""Animatic generator.

An animatic is a "moving storyboard" — each panel of a storyboard
becomes a short video clip, with optional music, narration, and
transitions. The output is an MP4 you can review with your team
or pitch to a client.

Two backends:

- **Ken Burns** (default) — pure PIL/ffmpeg, no AI. Each panel is
  panned/zoomed to create motion. Universal fallback.
- **AI video** (optional) — call into a video model (Wan 2.2,
  HunyuanVideo, CogVideoX, Runway Gen-3). Requires the model server
  to be running and a pluggable client.

This module is the **orchestrator**: it builds the timeline, calls
the backend for each clip, and stitches them together. The actual
video rendering uses ``ffmpeg`` via subprocess.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from directo.observability import get_logger

log = get_logger("directo.director.animatic")


# =====================================================================
# Domain
# =====================================================================


@dataclass
class AnimaticClip:
    """One clip in the animatic timeline."""

    image_path: str
    duration_s: float = 2.0
    # Ken Burns motion: (start_x, start_y, end_x, end_y) as fractions
    # of the image size (0,0 = top-left, 1,1 = bottom-right).
    pan_start: tuple[float, float] = (0.5, 0.5)
    pan_end: tuple[float, float] = (0.5, 0.5)
    zoom_start: float = 1.0
    zoom_end: float = 1.0
    # Optional audio: path to an audio file or TTS text
    narration: str | None = None
    narration_audio: str | None = None
    transition_in: str = "fade"  # "fade" | "cut" | "dissolve"


@dataclass
class AnimaticProject:
    """The full animatic project: clips + audio + metadata."""

    id: str
    title: str
    clips: list[AnimaticClip] = field(default_factory=list)
    music_path: str | None = None
    fps: int = 24
    resolution: tuple[int, int] = (1280, 720)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["resolution"] = list(self.resolution)
        return d


# =====================================================================
# Video backends
# =====================================================================


class VideoBackend(Protocol):
    name: str

    def is_available(self) -> bool: ...
    def render_clip(
        self,
        clip: AnimaticClip,
        output_path: str,
        *,
        fps: int,
        resolution: tuple[int, int],
    ) -> str: ...


class KenBurnsBackend:
    """Pure PIL/ffmpeg ken-burns pan-and-zoom.

    This is the universal fallback. It works without any model
    server. The visual quality is not as good as a real image-to-
    video model, but it lets you preview the timing/pacing of your
    storyboard without any GPU dependency.
    """

    name = "ken-burns"

    def is_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def render_clip(
        self,
        clip: AnimaticClip,
        output_path: str,
        *,
        fps: int,
        resolution: tuple[int, int],
    ) -> str:
        from PIL import Image, ImageDraw, ImageFont
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
            )
        except OSError:
            font = ImageFont.load_default()

        src = Image.open(clip.image_path).convert("RGB")
        sw, sh = src.size
        # Compute the scale that covers the target aspect ratio
        tw, th = resolution
        scale = max(tw / sw, th / sh)
        # Render each frame
        frames_dir = Path(output_path).with_suffix(".frames")
        frames_dir.mkdir(parents=True, exist_ok=True)
        n_frames = max(1, int(clip.duration_s * fps))
        for f in range(n_frames):
            t = f / max(1, n_frames - 1)  # 0..1
            cx = clip.pan_start[0] * (1 - t) + clip.pan_end[0] * t
            cy = clip.pan_start[1] * (1 - t) + clip.pan_end[1] * t
            zoom = clip.zoom_start * (1 - t) + clip.zoom_end * t
            # Compute crop
            crop_w = sw / (scale * zoom)
            crop_h = sh / (scale * zoom)
            x0 = int((sw - crop_w) * cx)
            y0 = int((sh - crop_h) * cy)
            x0 = max(0, min(sw - int(crop_w), x0))
            y0 = max(0, min(sh - int(crop_h), y0))
            crop = src.crop((x0, y0, x0 + int(crop_w), y0 + int(crop_h)))
            frame = crop.resize(resolution, Image.LANCZOS)
            # Burn in the narration as subtitle
            if clip.narration:
                overlay = Image.new("RGBA", resolution, (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                # Wrap text
                lines: list[str] = []
                words = clip.narration.split()
                line = ""
                for w in words:
                    if len(line) + len(w) + 1 > 60:
                        lines.append(line)
                        line = w
                    else:
                        line = (line + " " + w).strip()
                if line:
                    lines.append(line)
                # Render
                y = resolution[1] - 30 - 30 * len(lines)
                for ln in lines:
                    bbox = d.textbbox((0, 0), ln, font=font)
                    tw_txt = bbox[2] - bbox[0]
                    x = (resolution[0] - tw_txt) // 2
                    d.rectangle(
                        [(x - 10, y - 5), (x + tw_txt + 10, y + 30)],
                        fill=(0, 0, 0, 180),
                    )
                    d.text((x, y), ln, fill=(255, 255, 255), font=font)
                    y += 30
                frame = frame.convert("RGBA")
                frame.alpha_composite(overlay)
                frame = frame.convert("RGB")
            frame.save(frames_dir / f"f{f:05d}.jpg", quality=85)
        # Stitch with ffmpeg
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", str(frames_dir / "f%05d.jpg"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            output_path,
        ]
        subprocess.run(cmd, check=True)
        shutil.rmtree(frames_dir, ignore_errors=True)
        return output_path


class AIVideoBackend:
    """AI video generation backend.

    Calls out to an external video model server (e.g. Wan 2.2, HunyuanVideo,
    CogVideoX, Runway Gen-3) via HTTP REST. If configured with name="mock" or
    if no server is available, falls back to simulating video generation
    by applying a slight motion/zoom to the source image and adding overlay text.
    """

    def __init__(self, name: str = "mock", endpoint: str | None = None) -> None:
        self.name = name
        self.endpoint = endpoint or "http://localhost:8001/generate"

    def is_available(self) -> bool:
        if self.name == "mock":
            return True
        import shutil
        return shutil.which("ffmpeg") is not None

    def render_clip(
        self,
        clip: AnimaticClip,
        output_path: str,
        *,
        fps: int,
        resolution: tuple[int, int],
    ) -> str:
        if self.name == "mock":
            from PIL import Image, ImageDraw, ImageFont
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
                )
            except OSError:
                font = ImageFont.load_default()

            src = Image.open(clip.image_path).convert("RGB")
            sw, sh = src.size
            tw, th = resolution
            scale = max(tw / sw, th / sh)
            frames_dir = Path(output_path).with_suffix(".frames")
            frames_dir.mkdir(parents=True, exist_ok=True)
            n_frames = max(1, int(clip.duration_s * fps))
            for f in range(n_frames):
                t = f / max(1, n_frames - 1)
                cx = 0.5 + 0.1 * t
                cy = 0.5 + 0.1 * t
                zoom = 1.0 + 0.05 * t
                crop_w = sw / (scale * zoom)
                crop_h = sh / (scale * zoom)
                x0 = max(0, min(sw - int(crop_w), int((sw - crop_w) * cx)))
                y0 = max(0, min(sh - int(crop_h), int((sh - crop_h) * cy)))
                crop = src.crop((x0, y0, x0 + int(crop_w), y0 + int(crop_h)))
                frame = crop.resize(resolution, Image.LANCZOS)

                # Overlay AI Mock watermark
                overlay = Image.new("RGBA", resolution, (0, 0, 0, 0))
                d = ImageDraw.Draw(overlay)
                d.rectangle([(10, 10), (250, 45)], fill=(128, 0, 128, 180))
                d.text((20, 15), f"AI: {self.name.upper()}", fill=(255, 255, 255), font=font)

                if clip.narration:
                    lines = []
                    words = clip.narration.split()
                    line = ""
                    for w in words:
                        if len(line) + len(w) + 1 > 60:
                            lines.append(line)
                            line = w
                        else:
                            line = (line + " " + w).strip()
                    if line:
                        lines.append(line)
                    y = resolution[1] - 30 - 30 * len(lines)
                    for ln in lines:
                        bbox = d.textbbox((0, 0), ln, font=font)
                        tw_txt = bbox[2] - bbox[0]
                        x = (resolution[0] - tw_txt) // 2
                        d.rectangle(
                            [(x - 10, y - 5), (x + tw_txt + 10, y + 30)],
                            fill=(0, 0, 0, 180),
                        )
                        d.text((x, y), ln, fill=(255, 255, 255), font=font)
                        y += 30

                frame = frame.convert("RGBA")
                frame.alpha_composite(overlay)
                frame = frame.convert("RGB")
                frame.save(frames_dir / f"f{f:05d}.jpg", quality=85)

            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-framerate", str(fps),
                "-i", str(frames_dir / "f%05d.jpg"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                output_path,
            ]
            subprocess.run(cmd, check=True)
            shutil.rmtree(frames_dir, ignore_errors=True)
            return output_path

        else:
            import httpx
            log.info(f"requesting AI video from {self.endpoint} for {clip.image_path}")
            payload = {
                "image_path": str(Path(clip.image_path).absolute()),
                "duration_s": clip.duration_s,
                "model": self.name,
                "prompt": clip.narration or ""
            }
            response = httpx.post(self.endpoint, json=payload, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            video_url = data.get("video_url") or data.get("video_path")
            if not video_url:
                raise RuntimeError("AI video server did not return video_url or video_path")
            
            if video_url.startswith("http"):
                with httpx.stream("GET", video_url) as r:
                    r.raise_for_status()
                    with open(output_path, "wb") as f:
                        f.writelines(r.iter_bytes())
            else:
                shutil.copy(video_url, output_path)
            
            return output_path


# =====================================================================
# Builder
# =====================================================================


class AnimaticBuilder:
    """Compose an animatic from a list of clips.

    Typical usage::

        builder = AnimaticBuilder()
        project = AnimaticProject(
            id="...", title="...",
            clips=[
                AnimaticClip(image_path="shot1.png", duration_s=3,
                             pan_start=(0.5, 0.3), pan_end=(0.5, 0.7),
                             zoom_start=1.0, zoom_end=1.2),
                AnimaticClip(image_path="shot2.png", duration_s=2),
            ],
        )
        builder.build(project, "animatic.mp4")
    """

    def __init__(self, backend: VideoBackend | None = None) -> None:
        self._backend: VideoBackend = backend or KenBurnsBackend()
        if not self._backend.is_available():
            log.warning(
                f"backend {self._backend.name} not available; falling back to ken-burns"
            )
            self._backend = KenBurnsBackend()

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def build(
        self,
        project: AnimaticProject,
        output_path: str | Path,
    ) -> Path:
        """Render the full animatic.

        Each clip is rendered as its own MP4, then concatenated with
        ffmpeg's concat demuxer. The music track (if any) is mixed in
        with the last concat step.
        """
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._backend.is_available():
            raise RuntimeError(
                f"video backend {self._backend.name} is not available; install ffmpeg"
            )

        clip_dir = output_path.parent / f".{output_path.stem}.clips"
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: list[str] = []
        for i, clip in enumerate(project.clips):
            cp = clip_dir / f"clip_{i:04d}.mp4"
            log.bind(clip=i, image=clip.image_path).info(
                f"rendering clip ({clip.duration_s}s, {self._backend.name})"
            )
            self._backend.render_clip(
                clip, str(cp),
                fps=project.fps, resolution=project.resolution,
            )
            clip_paths.append(str(cp))
        # Concat
        list_file = clip_dir / "list.txt"
        with open(list_file, "w") as f:
            for cp in clip_paths:
                f.write(f"file '{cp}'\n")
        concat_path = clip_dir / "concat.mp4"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(concat_path),
        ]
        subprocess.run(cmd, check=True)
        # Mix music if provided
        if project.music_path and Path(project.music_path).exists():
            final = output_path
            cmd = [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(concat_path),
                "-i", project.music_path,
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                str(final),
            ]
            subprocess.run(cmd, check=True)
        else:
            shutil.move(str(concat_path), str(output_path))
        # Cleanup
        shutil.rmtree(clip_dir, ignore_errors=True)
        log.bind(output=str(output_path), clips=len(project.clips)).info(
            f"animatic rendered ({output_path.stat().st_size:,} bytes)"
        )
        return output_path


def from_gallery(
    gallery_records: Iterable[Any],
    *,
    title: str = "Animatic",
    clip_duration_s: float = 2.0,
    default_zoom: float = 1.1,
) -> AnimaticProject:
    """Convenience: build an animatic project from gallery records.

    Each record becomes a clip with a slight zoom-in (the simplest
    ken-burns effect).
    """
    clips: list[AnimaticClip] = []
    for rec in gallery_records:
        if not getattr(rec, "path", None):
            continue
        clips.append(AnimaticClip(
            image_path=rec.path,
            duration_s=clip_duration_s,
            zoom_start=1.0,
            zoom_end=default_zoom,
        ))
    return AnimaticProject(
        id=f"anim-{uuid.uuid4().hex[:8]}",
        title=title,
        clips=clips,
    )
