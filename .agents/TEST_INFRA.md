# E2E Test Infra: Directo Studio Local Media & Style Bible

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---------|---------------------|:------:|:------:|:------:|:------:|
| 1 | Style Bible Data Models & Storage | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 2 | Prompt Builder with Anchors & Tokens | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | ✓ |
| 3 | Video Generation Driver & Overlays | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 4 | TTS Speech Synthesis & Voice Selection | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 5 | Whisper Subtitles & Alignment | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 6 | BGM/SFX Audio Mixer & Sidechain Ducking | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 7 | Local Media Orchestrator Pipeline | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | ✓ |
| 8 | FastAPI Endpoints & WebSocket Events | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |
| 9 | UI TypeScript Schemas & Integration | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- Test runner: pytest (`.venv/bin/pytest`)
- Required test targets:
  - `tests/test_style_bible.py`
  - `tests/test_prompt_builder.py`
  - `tests/test_local_media_orchestrator.py`
  - `tests/test_local_gen_api.py`

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Script-to-Video Production Pipeline | F1, F2, F3, F4, F5, F6, F7 | High |
| 2 | Multi-Character Style Bible Export/Import & Generation | F1, F2, F3, F4, F8 | Medium |
| 3 | Audio Narration with Dynamic Ducking & Subtitle Burn-In | F4, F5, F6, F7 | High |
| 4 | Offline ComfyUI Node Fallback & Mock Execution | F3, F7, F8 | Medium |
| 5 | REST API Style Bible CRUD & Generation Trigger | F1, F8, F9 | Medium |

## Coverage Thresholds
- Tier 1: ≥5 per feature
- Tier 2: ≥5 per feature (where boundaries exist)
- Tier 3: pairwise coverage of major feature interactions
- Tier 4: ≥5 realistic application scenarios
