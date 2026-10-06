"""
Motor de Clonación de Voz Zero-Shot Local y Gestión de Memoria GPU.
Optimizado para NVIDIA GeForce RTX 4070 (12GB VRAM) y 24kHz Mono 16-bit PCM.
"""

from abc import ABC, abstractmethod
import datetime
import gc
import logging
import math
import os
import struct
import wave
from typing import List, Optional, Tuple

import numpy as np
import requests
import soundfile as sf
import torch

from core.tts.normalizer import chunk_text_by_sentences, normalize_text_for_tts

logger = logging.getLogger(__name__)


def setup_tts_gpu_environment() -> None:
    """Configura el entorno de memoria y aceleración TF32 para RTX 4070."""
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    # Integración transparente de ffmpeg para pydub y transformers
    try:
        import imageio_ffmpeg
        import shutil

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        if not os.path.exists(target_ffmpeg):
            shutil.copyfile(ffmpeg_exe, target_ffmpeg)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        try:
            import pydub
            pydub.AudioSegment.converter = target_ffmpeg
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"No se pudo configurar ffmpeg: {e}")


# Inicializar entorno TTS tempranamente
setup_tts_gpu_environment()


def _safe_transcribe_fallback(ref_audio, language=None):
    """
    Fallback ultra-robusto para transcripción de audio de referencia.
    Utiliza faster-whisper nativo en CUDA/CPU evitando invocar el pipeline de transformers
    y eliminando el error WinError 127 / FileNotFoundError en Windows.
    """
    try:
        from core.stt.transcriber import WhisperTranscriber
        transcriber = WhisperTranscriber(model_size="base")
        segs = transcriber.transcribe_file(ref_audio, language=language or "es")
        text = " ".join(s["text"].strip() for s in segs if s.get("text")).strip()
        if text:
            return text
    except Exception as e:
        logger.warning(f"Fallback faster-whisper no pudo transcribir {ref_audio}: {e}")
    return "Hola, buenas."


try:
    import f5_tts.infer.utils_infer as utils_infer
    utils_infer.transcribe = _safe_transcribe_fallback
except Exception:
    pass


def release_tts_gpu_memory(model=None) -> None:
    """
    Protocolo de Liberación de VRAM:
    Elimina referencias al modelo de síntesis, fuerza recolección de basura
    y purga la caché de tensores en CUDA.
    """
    if model is not None:
        del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


class BaseVoiceCloner(ABC):
    """Interfaz base para motores de síntesis y clonación de voz."""

    @abstractmethod
    def clone_speech(
        self,
        target_text: str,
        reference_audio_path: str,
        output_path: str,
        reference_text: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Sintetiza target_text con la voz clonada de reference_audio_path."""
        pass

    def clone_for_user(
        self,
        user_id: str,
        target_text: str,
        base_storage_dir: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Localiza la muestra curada del amigo en storage/clean_samples/<user_id>/
        y sintetiza la respuesta del Gemelo Digital.
        """
        user_sample_dir = os.path.join(base_storage_dir, "clean_samples", user_id)
        
        # Priorizar muestra corta y alineada para máxima claridad fonética
        prompt_wav = os.path.join(user_sample_dir, "sample_clean_prompt.wav")
        standard_wav = os.path.join(user_sample_dir, "sample_clean_60s.wav")
        if os.path.exists(prompt_wav):
            ref_wav = prompt_wav
        elif os.path.exists(standard_wav):
            ref_wav = standard_wav
        else:
            raise FileNotFoundError(
                f"No se encontró la muestra de voz curada para el usuario {user_id} en {user_sample_dir}. "
                f"Ejecuta primero: python main.py process --session latest"
            )

        ref_txt = None
        prompt_txt = os.path.join(user_sample_dir, "sample_clean_prompt.txt")
        standard_txt = os.path.join(user_sample_dir, "sample_clean_60s.txt")
        if os.path.exists(prompt_txt):
            try:
                with open(prompt_txt, "r", encoding="utf-8") as f:
                    ref_txt = f.read().strip()
            except Exception as e:
                logger.warning(f"No se pudo leer {prompt_txt}: {e}")
        elif os.path.exists(standard_txt):
            try:
                with open(standard_txt, "r", encoding="utf-8") as f:
                    ref_txt = f.read().strip()
            except Exception as e:
                logger.warning(f"No se pudo leer {standard_txt}: {e}")

        # Si aún no tenemos texto de referencia, auto-generar con faster-whisper y guardar
        if not ref_txt:
            try:
                from core.stt.transcriber import WhisperTranscriber
                logger.info(f"Auto-generando transcripción de referencia para {ref_wav}...")
                transcriber = WhisperTranscriber(model_size="base")
                segs = transcriber.transcribe_file(ref_wav)
                ref_txt = " ".join(s["text"].strip() for s in segs if s.get("text")).strip()
                if ref_txt:
                    target_txt_file = prompt_txt if ref_wav == prompt_wav else standard_txt
                    with open(target_txt_file, "w", encoding="utf-8") as f:
                        f.write(ref_txt)
                    logger.info(f"Transcripción guardada en {target_txt_file}")
            except Exception as e:
                logger.warning(f"No se pudo auto-generar texto de referencia para {ref_wav}: {e}")
                ref_txt = "Hola, buenas."

        if not output_path:
            out_dir = os.path.join(base_storage_dir, "twin_outputs", user_id)
            os.makedirs(out_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_path = os.path.join(out_dir, f"reply_{timestamp}.wav")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Calibrar velocidad de habla según cadencia del perfil para mayor realismo
        user_speed = 0.98
        profile_path = os.path.join(base_storage_dir, "profiles", f"{user_id}.json")
        if os.path.exists(profile_path):
            try:
                import json
                with open(profile_path, "r", encoding="utf-8") as pf:
                    pdata = json.load(pf)
                    cadence = pdata.get("communication_style", {}).get("cadence", "")
                    if cadence == "rapido":
                        user_speed = 1.02
                    elif cadence == "pausado":
                        user_speed = 0.94
            except Exception:
                pass

        return self.clone_speech(
            target_text=target_text,
            reference_audio_path=ref_wav,
            output_path=output_path,
            reference_text=ref_txt,
            speed=user_speed,
        )


class MockVoiceCloner(BaseVoiceCloner):
    """
    Clonador Mock para tests unitarios rápidos y entornos sin GPU.
    Genera un archivo WAV válido a 24.000 Hz Mono 16-bit PCM con una onda armónica suave.
    """

    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate

    def clone_speech(
        self,
        target_text: str,
        reference_audio_path: str,
        output_path: str,
        reference_text: Optional[str] = None,
        **kwargs,
    ) -> str:
        clean_text = normalize_text_for_tts(target_text)
        duration_sec = max(0.5, min(10.0, len(clean_text) * 0.05))
        total_samples = int(self.sample_rate * duration_sec)

        # Generar una onda sinusoidal suave atenuada a 440 Hz (La)
        t = np.linspace(0, duration_sec, total_samples, endpoint=False)
        audio_data = (np.sin(2 * np.pi * 440 * t) * 0.15).astype(np.float32)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        sf.write(output_path, audio_data, self.sample_rate, subtype="PCM_16")
        return output_path


class F5TTSVoiceCloner(BaseVoiceCloner):
    """
    Motor de Clonación Zero-Shot F5-TTS adaptado y optimizado para Español (jpgallegoar/F5-Spanish).
    Acelerado con Tensor Cores en RTX 4070 (12GB VRAM).
    """

    def __init__(
        self,
        model_name: str = "F5TTS_Base",
        repo_id: str = "jpgallegoar/F5-Spanish",
        device: Optional[str] = None,
        sample_rate: int = 24000,
        cfg_strength: float = 2.3,
        nfe_step: int = 48,
        speed: float = 0.98,
    ):
        setup_tts_gpu_environment()
        self.model_name = model_name
        self.repo_id = repo_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.sample_rate = sample_rate
        self.cfg_strength = cfg_strength
        self.nfe_step = nfe_step
        self.speed = speed
        self._model = None

    def _get_model(self):
        if self._model is None:
            from f5_tts.api import F5TTS
            from huggingface_hub import hf_hub_download

            logger.info(f"Cargando modelo F5-TTS Spanish '{self.repo_id}' ({self.model_name}) en '{self.device}'...")
            ckpt_path = hf_hub_download(repo_id=self.repo_id, filename="model_1200000.safetensors")
            vocab_path = hf_hub_download(repo_id=self.repo_id, filename="vocab.txt")
            self._model = F5TTS(
                model=self.model_name,
                ckpt_file=ckpt_path,
                vocab_file=vocab_path,
                device=self.device,
            )
        return self._model

    def clone_speech(
        self,
        target_text: str,
        reference_audio_path: str,
        output_path: str,
        reference_text: Optional[str] = None,
        cfg_strength: Optional[float] = None,
        nfe_step: Optional[int] = None,
        speed: Optional[float] = None,
        **kwargs,
    ) -> str:
        if not os.path.exists(reference_audio_path):
            raise FileNotFoundError(f"Audio de referencia no encontrado: {reference_audio_path}")

        # Garantizar que reference_text nunca sea None ni vacío para evitar caídas en F5-TTS
        if not reference_text or not reference_text.strip():
            try:
                from core.stt.transcriber import WhisperTranscriber
                transcriber = WhisperTranscriber(model_size="base")
                segs = transcriber.transcribe_file(reference_audio_path)
                reference_text = " ".join(s["text"].strip() for s in segs if s.get("text")).strip()
            except Exception as e:
                logger.warning(f"Error auto-transcribiendo reference_audio_path: {e}")
            if not reference_text:
                reference_text = "Hola, buenas."

        clean_text = normalize_text_for_tts(target_text)
        if not clean_text:
            clean_text = "..."

        # Si la respuesta es de longitud conversacional estándar (<= 25 palabras),
        # sintetizar en una sola pasada continua para preservar la melodía rioplatense y evitar truncamientos
        words = clean_text.split()
        if len(words) <= 25:
            chunks = [clean_text]
        else:
            chunks = chunk_text_by_sentences(clean_text, max_words_per_chunk=25)

        model = self._get_model()

        cfg = cfg_strength if cfg_strength is not None else self.cfg_strength
        nfe = nfe_step if nfe_step is not None else self.nfe_step
        spd = speed if speed is not None else self.speed

        generated_chunks = []
        sr = self.sample_rate

        with torch.inference_mode():
            for idx, chunk in enumerate(chunks):
                wav, sample_rate, _ = model.infer(
                    ref_file=reference_audio_path,
                    ref_text=reference_text,
                    gen_text=chunk,
                    cfg_strength=cfg,
                    nfe_step=nfe,
                    speed=spd,
                    target_rms=0.10,
                )
                generated_chunks.append(wav)
                sr = sample_rate

        # Si hay más de un fragmento, concatenamos con 200ms de silencio
        if len(generated_chunks) == 1:
            final_audio = generated_chunks[0]
        else:
            silence_samples = int(0.20 * sr)
            silence = np.zeros(silence_samples, dtype=generated_chunks[0].dtype)
            assembled = []
            for i, chunk_wav in enumerate(generated_chunks):
                assembled.append(chunk_wav)
                if i < len(generated_chunks) - 1:
                    assembled.append(silence)
            final_audio = np.concatenate(assembled)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        sf.write(output_path, final_audio, sr, subtype="PCM_16")

        return output_path

    def release(self) -> None:
        """Libera los recursos del modelo F5-TTS de la GPU."""
        if self._model is not None:
            self._model = None
        release_tts_gpu_memory()


class VoiceStudioCloner(BaseVoiceCloner):
    """
    Motor de Clonación y Síntesis de Voz conectado a VoiceStudio local (puerto 3900).
    Aprovecha la API REST OpenAI-compatible (/v1/audio/speech) y los perfiles locales (/profiles)
    de VoiceStudio, impulsados por OmniVoice y CosyVoice 3 en GPU local (RTX 4070).
    Incluye fallback transparente a F5-TTS o Mock si VoiceStudio no está en ejecución.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        model: str = "omnivoice",
        timeout_seconds: float = 90.0,
        fallback_cloner: Optional[BaseVoiceCloner] = None,
        device: Optional[str] = None,
    ):
        self.api_url = (api_url or os.getenv("VOICESTUDIO_API_URL", "http://127.0.0.1:3900")).rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._fallback_cloner = fallback_cloner
        self.device = device
        self._profiles_cache = {}

    @property
    def fallback_cloner(self) -> BaseVoiceCloner:
        """Inicializa el clonador fallback de forma perezosa para no acaparar VRAM innecesariamente."""
        if self._fallback_cloner is None:
            try:
                logger.info("Inicializando motor fallback F5-TTS...")
                self._fallback_cloner = F5TTSVoiceCloner(device=self.device) if torch.cuda.is_available() else MockVoiceCloner()
            except Exception as e:
                logger.warning(f"No se pudo inicializar F5TTS fallback: {e}. Usando Mock.")
                self._fallback_cloner = MockVoiceCloner()
        return self._fallback_cloner

    def is_available(self) -> bool:
        """Verifica si el servidor local de VoiceStudio está activo y respondiendo."""
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _get_or_create_profile(self, user_name: str, reference_audio_path: str, reference_text: Optional[str] = None) -> str:
        """Garantiza que exista un perfil de voz sincronizado en VoiceStudio para el usuario/muestra."""
        if user_name in self._profiles_cache:
            return self._profiles_cache[user_name]

        # 1. Consultar perfiles existentes
        try:
            resp = requests.get(f"{self.api_url}/profiles", timeout=5.0)
            if resp.status_code == 200:
                profiles = resp.json()
                for p in profiles:
                    if p.get("name") == user_name:
                        # Si el texto de referencia cambió, renovar el perfil para evitar desincronización
                        if reference_text and p.get("ref_text") and p.get("ref_text").strip() != reference_text.strip():
                            logger.info(f"Texto de referencia actualizado para '{user_name}'. Recreando perfil...")
                            requests.delete(f"{self.api_url}/profiles/{p['id']}", timeout=5.0)
                            break
                        pid = p["id"]
                        self._profiles_cache[user_name] = pid
                        return pid
        except Exception as e:
            logger.warning(f"Error consultando perfiles en VoiceStudio: {e}")

        # 2. Registrar perfil con la muestra de audio y transcripción fiel
        try:
            with open(reference_audio_path, "rb") as f:
                files = {"ref_audio": (os.path.basename(reference_audio_path), f, "audio/wav")}
                data = {
                    "name": user_name,
                    "ref_text": reference_text or "",
                    "language": "Spanish",
                    "kind": "clone",
                }
                resp = requests.post(f"{self.api_url}/profiles", files=files, data=data, timeout=15.0)
                if resp.status_code in (200, 201):
                    pdata = resp.json()
                    pid = pdata.get("id") or user_name
                    self._profiles_cache[user_name] = pid
                    logger.info(f"Perfil de voz '{user_name}' registrado en VoiceStudio con ID: {pid}")
                    return pid
                else:
                    logger.warning(f"VoiceStudio respondió {resp.status_code} al crear perfil: {resp.text}")
        except Exception as e:
            logger.warning(f"Fallo al registrar perfil '{user_name}' en VoiceStudio: {e}")

        return user_name

    def clone_speech(
        self,
        target_text: str,
        reference_audio_path: str,
        output_path: str,
        reference_text: Optional[str] = None,
        speed: float = 1.0,
        **kwargs,
    ) -> str:
        if not self.is_available():
            logger.warning("VoiceStudio no responde en 127.0.0.1:3900. Usando motor fallback...")
            return self.fallback_cloner.clone_speech(
                target_text=target_text,
                reference_audio_path=reference_audio_path,
                output_path=output_path,
                reference_text=reference_text,
                speed=speed,
                **kwargs,
            )

        clean_text = normalize_text_for_tts(target_text)
        if not clean_text:
            clean_text = "..."

        user_folder = os.path.basename(os.path.dirname(os.path.abspath(reference_audio_path)))
        profile_name = f"user_{user_folder}" if user_folder and user_folder != "." else "clone_user"
        voice_id = self._get_or_create_profile(profile_name, reference_audio_path, reference_text)

        logger.info(f"Sintetizando voz en VoiceStudio (perfil='{profile_name}', voice_id='{voice_id}', pasos=32)...")
        payload = {
            "model": self.model,
            "input": clean_text,
            "voice": voice_id,
            "response_format": "wav",
            "speed": float(speed),
            "language": "es",
            "num_step": 32,
            "guidance_scale": 2.5,
            "preprocess_prompt": True,
            "denoise": True,
        }

        resp = requests.post(
            f"{self.api_url}/v1/audio/speech",
            json=payload,
            timeout=self.timeout_seconds,
        )

        if resp.status_code != 200:
            err_msg = f"VoiceStudio API error ({resp.status_code}): {resp.text}"
            logger.error(err_msg)
            logger.warning("Intentando fallback ante error de VoiceStudio...")
            return self.fallback_cloner.clone_speech(
                target_text=target_text,
                reference_audio_path=reference_audio_path,
                output_path=output_path,
                reference_text=reference_text,
                speed=speed,
                **kwargs,
            )

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)

        return output_path

    def release(self) -> None:
        """VoiceStudio gestiona su propia memoria en su proceso independiente."""
        if self._fallback_cloner is not None:
            self._fallback_cloner.release()
            self._fallback_cloner = None


def get_voice_cloner(
    engine: str = "auto",
    mock: bool = False,
    device: Optional[str] = None,
) -> BaseVoiceCloner:
    """
    Factory que retorna la instancia adecuada de clonador de voz.
    Si mock es True, retorna MockVoiceCloner.
    Respeta la variable de entorno TTS_ENGINE (voicestudio, f5-tts, mock, auto).
    """
    if mock:
        return MockVoiceCloner()

    env_engine = os.getenv("TTS_ENGINE", engine).lower()

    # Si se pide explícitamente VoiceStudio
    if env_engine in ("voicestudio", "voice-studio"):
        return VoiceStudioCloner(device=device)

    # Modo automático inteligente: prioriza VoiceStudio con fallback perezoso
    if env_engine == "auto":
        vs_cloner = VoiceStudioCloner(device=device)
        if vs_cloner.is_available():
            logger.info("VoiceStudio detectado en http://127.0.0.1:3900 - Activando como motor TTS principal.")
        else:
            logger.info("VoiceStudio no detectado al inicio; VoiceStudioCloner gestionará fallback si no responde.")
        return vs_cloner

    if env_engine in ("f5-tts", "f5_tts", "f5"):
        try:
            return F5TTSVoiceCloner(device=device)
        except Exception as e:
            logger.warning(f"No se pudo inicializar F5TTSVoiceCloner: {e}. Usando MockVoiceCloner.")
            return MockVoiceCloner()

    return MockVoiceCloner()
