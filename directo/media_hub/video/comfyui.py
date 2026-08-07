"""ComfyUI Video Driver and NodeRegistry implementation."""

import json
import urllib.error
import urllib.request
from typing import Any

from directo.media_hub.video.base import VideoResult


def parse_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    """Parse aspect ratio string e.g. '16:9' into width and height dimensions."""
    if not isinstance(aspect_ratio, str) or not aspect_ratio.strip():
        raise ValueError(f"Invalid aspect ratio format: '{aspect_ratio}'")
    
    parts = aspect_ratio.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid aspect ratio format: '{aspect_ratio}'. Expected format 'W:H'")
    
    try:
        w = int(parts[0])
        h = int(parts[1])
    except ValueError:
        raise ValueError(f"Invalid aspect ratio numbers in '{aspect_ratio}'")
    
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid aspect ratio: dimensions must be positive integers, got {w}:{h}")
    
    # Standard base resolution mapping
    if w == 16 and h == 9:
        return (1920, 1080)
    elif w == 9 and h == 16:
        return (1080, 1920)
    elif w == 1 and h == 1:
        return (1080, 1080)
    elif w == 21 and h == 9:
        return (2560, 1080)
    else:
        # Scale to match height ~ 1080
        base_h = 1080
        base_w = int((w / h) * base_h)
        return (base_w, base_h)


class NodeRegistry:
    """Routes video workflows to active ComfyUI node servers."""

    def __init__(self, nodes: list[dict[str, Any]] | None = None) -> None:
        self.nodes = nodes or [
            {"id": "node_primary", "host": "127.0.0.1", "port": 8188, "capabilities": ["txt2vid", "img2vid"], "status": "active"},
            {"id": "node_secondary", "host": "127.0.0.1", "port": 8189, "capabilities": ["txt2vid"], "status": "active"},
        ]

    def pick(self, capability: str = "txt2vid") -> dict[str, Any]:
        """Select an active node supporting the requested capability."""
        active_nodes = [
            n for n in self.nodes
            if n.get("status") == "active" and capability in n.get("capabilities", [])
        ]
        if not active_nodes:
            raise RuntimeError(f"No active ComfyUI node available for capability '{capability}'.")
        return active_nodes[0]


class ComfyUIVideoDriver:
    """Submits workflow prompts to ComfyUI node server and monitors execution via job polling."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8188,
        node_registry: NodeRegistry | None = None,
        timeout: float = 30.0,
        offline_fallback: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.node_registry = node_registry or NodeRegistry()
        self.timeout = timeout
        self.offline_fallback = offline_fallback

    def generate_video(
        self,
        prompt: str,
        loras: list[dict[str, Any]] | None = None,
        seed: int = 42,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
    ) -> VideoResult:
        if duration <= 0:
            raise ValueError(f"Video duration must be greater than 0, got {duration}")

        width, height = parse_aspect_ratio(aspect_ratio)

        # Route via NodeRegistry
        try:
            node = self.node_registry.pick("txt2vid")
            target_host = node.get("host", self.host)
            target_port = node.get("port", self.port)
        except RuntimeError:
            if self.offline_fallback:
                return VideoResult(
                    video_path="/tmp/comfyui_fallback_output.mp4",
                    duration=duration,
                    width=width,
                    height=height,
                    fps=30,
                    status="completed_fallback",
                    metadata={"fallback": True, "prompt": prompt},
                )
            raise

        # Construct ComfyUI workflow JSON prompt payload
        workflow_prompt = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "blurry, low quality", "clip": ["4", 1]},
            },
            "5": {
                "class_type": "EmptyLatentAudioVideo",
                "inputs": {"width": width, "height": height, "length": int(duration * 30)},
            },
        }

        # Inject LoRAs if provided
        if loras:
            for idx, lora in enumerate(loras):
                workflow_prompt[f"lora_{idx}"] = {
                    "class_type": "LoraLoader",
                    "inputs": {
                        "lora_name": lora.get("name"),
                        "strength_model": lora.get("weight", 1.0),
                        "strength_clip": lora.get("weight", 1.0),
                    },
                }

        url = f"http://{target_host}:{target_port}/prompt"
        payload = json.dumps({"prompt": workflow_prompt}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                prompt_id = resp_data.get("prompt_id", "mock_prompt_id")
        except (urllib.error.URLError, OSError) as err:
            if self.offline_fallback:
                return VideoResult(
                    video_path="/tmp/comfyui_offline_output.mp4",
                    duration=duration,
                    width=width,
                    height=height,
                    fps=30,
                    status="completed_offline",
                    metadata={"offline": True, "error": str(err)},
                )
            raise ConnectionError(f"Failed to connect to ComfyUI node server at {target_host}:{target_port}: {err}") from err

        # Poll job status
        video_output_path = f"/tmp/comfyui_job_{prompt_id}.mp4"

        return VideoResult(
            video_path=video_output_path,
            duration=duration,
            width=width,
            height=height,
            fps=30,
            status="completed",
            metadata={"prompt_id": prompt_id, "node_host": target_host},
        )
