"""Scale module (Phase 2): production-grade technical infrastructure.

Modules:
- :mod:`directo.scale.nodes`  — ComfyUI node registry + health checks
- :mod:`directo.scale.vram`   — GPU detection + low-VRAM recommendations
- :mod:`directo.scale.presets` — Cinema preset packs (built-in + user)
- :mod:`directo.scale.enhance` — Multi-LLM prompt enhancement
"""

from directo.scale.enhance import (
    EnhancementResult,
    LLMProvider,
    PromptEnhancer,
    TargetModel,
    TemplateEnhancer,
)
from directo.scale.nodes import (
    ComfyUINode,
    NodeHealth,
    NodeRegistry,
)
from directo.scale.presets import Preset, PresetStore
from directo.scale.vram import (
    GPUInfo,
    QuantLevel,
    VRAMProfile,
    apply_low_vram_env,
    detect_gpus,
    env_compat,
    profile,
    recommend_quant_for_model,
)

__all__ = [
    # nodes
    "ComfyUINode",
    # enhance
    "EnhancementResult",
    # vram
    "GPUInfo",
    "LLMProvider",
    "NodeHealth",
    "NodeRegistry",
    # presets
    "Preset",
    "PresetStore",
    "PromptEnhancer",
    "QuantLevel",
    "TargetModel",
    "TemplateEnhancer",
    "VRAMProfile",
    "apply_low_vram_env",
    "detect_gpus",
    "env_compat",
    "profile",
    "recommend_quant_for_model",
]
