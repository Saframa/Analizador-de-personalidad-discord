"""
Transcripción Speech-to-Text de alta precisión con faster-whisper.
Optimizado para NVIDIA RTX 4070 (FP16 / Tensor Cores) con calibración léxica
uruguaya/rioplatense y protocolo estricto de liberación de memoria VRAM.
"""

import gc
import math
import os
from typing import Any, Dict, List, Optional
import torch

DEFAULT_URUGUAYAN_PROMPT = (
    "Transcripción de conversación informal entre amigos de Uruguay y el Río de la Plata. "
    "Léxico común y modismos: bo, ta, salado, de menos, posta, che, pará, zarpado, fiera, gurí, mirá, viste."
)


def release_gpu_memory(model=None) -> None:
    """
    Protocolo de Seguridad de Hardware:
    Purga explícitamente los pesos de memoria en CUDA y fuerza recolección de basura.
    Nunca se debe proceder a otras tareas pesadas de GPU sin ejecutar este protocolo.
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


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        initial_prompt: Optional[str] = None,
        cpu_threads: int = 4,
        num_workers: int = 2,
    ):
        """
        Inicializa el modelo de transcripción faster-whisper.
        Por defecto usa large-v3 en float16 sobre CUDA 0 (~4 GB VRAM).
        """
        self.model_size = model_size
        self.device = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        # En CPU, float16 no es soportado por ctranslate2, usar float32 o int8
        if self.device == "cpu" and compute_type == "float16":
            self.compute_type = "int8"
        else:
            self.compute_type = compute_type

        self.initial_prompt = initial_prompt or DEFAULT_URUGUAYAN_PROMPT
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                device_index=0 if self.device == "cuda" else 0,
                cpu_threads=self.cpu_threads,
                num_workers=self.num_workers,
            )
        return self._model

    def transcribe_file(
        self,
        audio_path: str,
        language: str = "es",
        beam_size: int = 5,
        word_timestamps: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Transcribe un archivo de audio (.wav u .ogg).
        Retorna lista de segmentos:
        [
            {
                "start": float,
                "end": float,
                "text": str,
                "confidence": float,
                "words": List[dict]
            }, ...
        ]
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Archivo de audio no existe: {audio_path}")

        # Evitar archivos vacíos o con sólo cabecera WAV
        if os.path.getsize(audio_path) <= 100:
            return []

        model = self._get_model()

        segments_iter, info = model.transcribe(
            audio_path,
            language=language,
            initial_prompt=self.initial_prompt,
            beam_size=beam_size,
            vad_filter=False,  # Manejamos VAD con Silero para quirúrgica precisión
            word_timestamps=word_timestamps,
        )

        results: List[Dict[str, Any]] = []

        for seg in segments_iter:
            clean_text = seg.text.strip()
            if not clean_text:
                continue

            # Calcular confianza aproximada desde avg_logprob: P = exp(logprob)
            try:
                confidence = round(min(1.0, max(0.0, math.exp(seg.avg_logprob))), 4)
            except (OverflowError, ValueError):
                confidence = 0.5

            words_data = []
            if seg.words:
                for w in seg.words:
                    words_data.append(
                        {
                            "word": w.word.strip(),
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                            "probability": round(w.probability, 4),
                        }
                    )

            results.append(
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "duration": round(seg.end - seg.start, 3),
                    "text": clean_text,
                    "confidence": confidence,
                    "words": words_data,
                }
            )

        return results

    def close(self) -> None:
        """Libera la GPU y descarga el modelo de la memoria."""
        if self._model is not None:
            self._model = None
        release_gpu_memory()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
