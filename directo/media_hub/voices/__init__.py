"""TTS Driver modules for Directo Media Hub."""

from directo.media_hub.voices.base import SpeechResult, TTSDriver
from directo.media_hub.voices.piper import PiperTTSDriver
from directo.media_hub.voices.bark import BarkTTSDriver
from directo.media_hub.voices.coqui import CoquiTTSDriver
from directo.media_hub.voices.mock import MockTTSDriver

__all__ = [
    "TTSDriver",
    "SpeechResult",
    "PiperTTSDriver",
    "BarkTTSDriver",
    "CoquiTTSDriver",
    "MockTTSDriver",
]
