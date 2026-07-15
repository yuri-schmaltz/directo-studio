"""GPU VRAM detection and low-VRAM mode configuration.

Two responsibilities:

1. **Detect** the available VRAM on the local machine (nvidia-smi
   first, falls back to PyTorch if available).
2. **Recommend** a quantization strategy (NF4, GGUF Q-level) and
   model loading order based on the available headroom.

The recommendation is what :class:`directo.scale.presets.Preset` uses
to choose between full-precision and quantized checkpoints.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

from directo.observability import get_logger

log = get_logger("directo.scale.vram")

QuantLevel = Literal["fp16", "fp8", "nf4", "gguf-q8", "gguf-q5", "gguf-q4", "gguf-q3", "gguf-q2"]


@dataclass
class GPUInfo:
    """Information about a single GPU."""

    index: int
    name: str
    vram_total_mb: int
    vram_free_mb: int | None = None  # None if not currently measurable
    driver: str | None = None
    cuda: str | None = None


@dataclass
class VRAMProfile:
    """The orchestrator's view of available compute."""

    gpus: list[GPUInfo]
    total_vram_mb: int
    free_vram_mb: int | None
    recommended_quant: QuantLevel
    recommended_max_model_mb: int  # rough budget per model
    notes: list[str]


# Quantization thresholds. Bigger models need more aggressive quantization.
_QUANT_TABLE: list[tuple[int, QuantLevel, int]] = [
    # (min_free_mb, quant_level, max_model_size_mb)
    (0,    "gguf-q2", 1000),    # < 4GB total: tiny models only
    (4000, "gguf-q3", 3000),    # 4-8GB
    (8000, "gguf-q4", 6000),    # 8-12GB
    (12000, "gguf-q5", 8000),   # 12-16GB
    (16000, "gguf-q8", 10000),  # 16-24GB
    (24000, "fp8", 14000),      # 24-40GB
    (40000, "fp16", 24000),     # 40GB+ (A100 80GB, etc.)
]


def detect_gpus() -> list[GPUInfo]:
    """Detect local GPUs.

    Tries `nvidia-smi` first (the most reliable). Falls back to
    `torch.cuda.device_count()` if PyTorch is installed but the
    smi tool is missing. Returns an empty list if no GPU is detected.
    """
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=index,name,memory.total,memory.free,driver_version",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5.0,
            )
            if out.returncode == 0:
                gpus: list[GPUInfo] = []
                for line in out.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append(GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            vram_total_mb=int(float(parts[2])),
                            vram_free_mb=int(float(parts[3])),
                            driver=parts[4],
                        ))
                if gpus:
                    return gpus
        except Exception as exc:  # noqa: BLE001
            log.warning(f"nvidia-smi failed: {exc}")

    # Fallback: torch
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            gpus = []
            for i in range(count):
                props = torch.cuda.get_device_properties(i)
                free = None
                try:
                    free = torch.cuda.mem_get_info(i)[0] // (1024 * 1024)
                except Exception:
                    pass
                gpus.append(GPUInfo(
                    index=i, name=props.name,
                    vram_total_mb=props.total_memory // (1024 * 1024),
                    vram_free_mb=free,
                    cuda=torch.version.cuda,
                ))
            return gpus
    except ImportError:
        pass

    log.info("no GPU detected; CPU-only mode")
    return []


def profile() -> VRAMProfile:
    """Build a :class:`VRAMProfile` for the local machine.

    Aggregates total + free VRAM across all GPUs and produces a
    recommendation for the right quantization level.
    """
    gpus = detect_gpus()
    notes: list[str] = []
    if not gpus:
        notes.append("no GPU detected — Directo will run in CPU mode (slow)")
        return VRAMProfile(
            gpus=[], total_vram_mb=0, free_vram_mb=None,
            recommended_quant="gguf-q2",
            recommended_max_model_mb=500,
            notes=notes,
        )
    total = sum(g.vram_total_mb for g in gpus)
    free_vals = [g.vram_free_mb for g in gpus if g.vram_free_mb is not None]
    free = sum(free_vals) if free_vals else None
    # Pick recommendation based on the largest single GPU's free VRAM
    largest_free = max(free_vals) if free_vals else total
    quant: QuantLevel = "gguf-q2"
    max_model = 1000
    for threshold, q, mx in _QUANT_TABLE:
        if largest_free >= threshold:
            quant = q
            max_model = mx
    if len(gpus) > 1:
        notes.append(f"{len(gpus)} GPUs detected; some workflows can shard across them")
    return VRAMProfile(
        gpus=gpus, total_vram_mb=total, free_vram_mb=free,
        recommended_quant=quant, recommended_max_model_mb=max_model,
        notes=notes,
    )


def recommend_quant_for_model(model_size_mb: int, free_vram_mb: int) -> QuantLevel:
    """Pick the best quantization for a specific model + available VRAM.

    Returns the most aggressive quantization that still allows the
    model to fit with a 20% headroom for activations.
    """
    # Target: model + 20% buffer for activations
    target = int(model_size_mb * 1.2)
    if free_vram_mb >= target:
        return "fp16"
    # Walk quant table backwards
    for threshold, q, _ in reversed(_QUANT_TABLE):
        if threshold <= free_vram_mb:
            return q
    return "gguf-q2"


def env_compat() -> dict[str, str]:
    """Return env vars that enable low-VRAM mode for various backends.

    These are the canonical flags used by diffusers, ComfyUI, and
    SD.Next for low-VRAM operation. Set them in your worker env.
    """
    return {
        # diffusers / transformers
        "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
        "DIFFUSERS_ENABLE_XFORMERS_MEMORY_EFFICIENT_ATTENTION": "1",
        # ComfyUI
        "COMFYUI_FORCE_FP16": "1",
        "COMFYUI_LOW_VRAM": "1",
        # torch
        "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:512,expandable_segments:True",
    }


def apply_low_vram_env() -> None:
    """Apply all low-VRAM env vars in-process (use carefully)."""
    for k, v in env_compat().items():
        os.environ.setdefault(k, v)
