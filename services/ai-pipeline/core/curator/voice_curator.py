"""
Módulo de Curación de Muestras de Voz para Clonación (Voice Curator).
Extrae ventanas de habla limpias (sin solapamiento de otros interlocutores),
las concatena hasta alcanzar 30-60 segundos, las remuestrea a 24 kHz Mono
y las normaliza a -18 LUFS con prevención de clipping para modelos TTS (XTTS-v2 / F5-TTS).
"""

import os
from typing import Dict, List, Optional, Tuple
import numpy as np
import soundfile as sf
import torch
import torchaudio


class VoiceCurator:
    def __init__(self, target_sample_rate: int = 24000, target_lufs: float = -18.0):
        self.target_sample_rate = target_sample_rate
        self.target_lufs = target_lufs

    def normalize_loudness(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """
        Normaliza la sonoridad del audio a target_lufs usando pyloudnorm (ITU-R BS.1770-4)
        y evita el clipping digital asegurando un pico máximo de -0.5 dBFS (~0.94).
        """
        import pyloudnorm as pyln

        if len(audio_data) == 0:
            return audio_data

        # Si el audio es silencio absoluto o de muy bajo nivel
        peak = np.max(np.abs(audio_data))
        if peak < 1e-4:
            return audio_data

        meter = pyln.Meter(sample_rate)
        try:
            loudness = meter.integrated_loudness(audio_data)
            if np.isneginf(loudness) or np.isnan(loudness):
                return audio_data
            normalized = pyln.normalize.loudness(audio_data, loudness, self.target_lufs)
        except Exception:
            # Fallback a normalización de pico si falla el cálculo LUFS
            normalized = audio_data / peak * 0.7

        # Prevención de clipping (Peak limiting)
        norm_peak = np.max(np.abs(normalized))
        if norm_peak > 0.94:
            normalized = (normalized / norm_peak) * 0.94

        return normalized

    def curate_user_sample(
        self,
        user_id: str,
        audio_path: str,
        clean_intervals: List[Tuple[float, float]],
        output_dir: str,
        target_max_duration: float = 60.0,
        min_required_duration: float = 5.0,
    ) -> Optional[Dict[str, any]]:
        """
        Corta y ensambla los segmentos limpios del usuario, remuestrea a 24 kHz mono,
        normaliza a -18 LUFS y guarda en output_dir/<user_id>/sample_clean_60s.wav.
        """
        if not os.path.exists(audio_path) or not clean_intervals:
            return None

        # Cargar audio original
        waveform, sr = torchaudio.load(audio_path)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        total_samples = waveform.shape[1]
        extracted_chunks = []
        collected_duration = 0.0

        for start_sec, end_sec in clean_intervals:
            start_sample = int(start_sec * sr)
            end_sample = int(end_sec * sr)

            if start_sample >= total_samples:
                continue
            end_sample = min(end_sample, total_samples)

            chunk = waveform[:, start_sample:end_sample]
            duration = (end_sample - start_sample) / sr

            extracted_chunks.append(chunk)
            collected_duration += duration

            if collected_duration >= target_max_duration:
                break

        if not extracted_chunks or collected_duration < min_required_duration:
            # No hay suficiente audio limpio para una muestra de calidad
            return None

        combined_waveform = torch.cat(extracted_chunks, dim=1)

        # Remuestrear a 24 kHz si es necesario
        if sr != self.target_sample_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=self.target_sample_rate)
            combined_waveform = resampler(combined_waveform)

        # Convertir a numpy para normalización LUFS
        audio_np = combined_waveform.squeeze(0).cpu().numpy().astype(np.float32)
        normalized_audio = self.normalize_loudness(audio_np, self.target_sample_rate)

        # Crear directorio destino
        user_sample_dir = os.path.join(output_dir, user_id)
        os.makedirs(user_sample_dir, exist_ok=True)
        output_file = os.path.join(user_sample_dir, "sample_clean_60s.wav")

        # Guardar en formato 16-bit PCM WAV a 24 kHz
        sf.write(output_file, normalized_audio, self.target_sample_rate, subtype="PCM_16")

        actual_duration = round(len(normalized_audio) / self.target_sample_rate, 2)

        return {
            "user_id": user_id,
            "output_path": os.path.abspath(output_file),
            "duration_seconds": actual_duration,
            "sample_rate": self.target_sample_rate,
            "segments_used": len(extracted_chunks),
            "target_lufs": self.target_lufs,
        }
