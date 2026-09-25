"""
Módulo TTS (Text-To-Speech) y Clonación de Voz Zero-Shot Local.
Acelerado por GPU NVIDIA RTX 4070 (12GB VRAM).
"""

from core.tts.cloner import BaseVoiceCloner, F5TTSVoiceCloner, MockVoiceCloner, get_voice_cloner, release_tts_gpu_memory
from core.tts.normalizer import chunk_text_by_sentences, normalize_text_for_tts
from core.tts.player import play_audio_file

__all__ = [
    "BaseVoiceCloner",
    "F5TTSVoiceCloner",
    "MockVoiceCloner",
    "get_voice_cloner",
    "release_tts_gpu_memory",
    "normalize_text_for_tts",
    "chunk_text_by_sentences",
    "play_audio_file",
]
