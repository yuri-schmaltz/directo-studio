"""Scale module (Phase 2): production-grade technical infrastructure.

Modules:
- :mod:`directo.scale.nodes`  — ComfyUI node registry + health checks
- :mod:`directo.scale.vram`   — GPU detection + low-VRAM recommendations
- :mod:`directo.scale.presets` — Cinema preset packs (built-in + user)
- :mod:`directo.scale.enhance` — Multi-LLM prompt enhancement
"""

from directo.scale.nodes import (
    ComfyUINode,
    NodeHealth,
    NodeRegistry,
)
from directo.scale.vram import (
    GPUInfo,
    QuantLevel,
    VRAMProfile,
    detect_gpus,
    profile,
    recommend_quant_for_model,
    env_compat,
    apply_low_vram_env,
)
from directo.scale.presets import Preset, PresetStore
from directo.scale.enhance import (
    EnhancementResult,
    LLMProvider,
    PromptEnhancer,
    TargetModel,
    TemplateEnhancer,
)

__all__ = [
    # nodes
    "ComfyUINode", "NodeHealth", "NodeRegistry",
    # vram
    "GPUInfo", "QuantLevel", "VRAMProfile",
    "detect_gpus", "profile", "recommend_quant_for_model",
    "env_compat", "apply_low_vram_env",
    # presets
    "Preset", "PresetStore",
    # enhance
    "EnhancementResult", "LLMProvider", "PromptEnhancer", "TargetModel",
    "TemplateEnhancer",
]
