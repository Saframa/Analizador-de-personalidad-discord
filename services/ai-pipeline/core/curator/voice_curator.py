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

        # Cargar audio original de forma robusta
        waveform = None
        sr = 48000
        try:
            waveform, sr = torchaudio.load(audio_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
        except Exception:
            pass

        if waveform is None:
            import av
            try:
                container = av.open(audio_path)
                stream = container.streams.audio[0]
                sr = stream.rate or 48000
                resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
                chunks = []
                for packet in container.demux(stream):
                    if packet.size == 0:
                        continue
                    try:
                        for f in packet.decode():
                            for rf in resampler.resample(f):
                                chunks.append(rf.to_ndarray())
                    except Exception:
                        continue
                container.close()
                if chunks:
                    audio_np = np.concatenate(chunks, axis=1)
                    waveform = torch.from_numpy(audio_np)
            except Exception:
                return None

        if waveform is None:
            return None

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

    def generate_prompt_and_transcripts(
        self,
        user_id: str,
        output_dir: str,
        transcriber=None,
    ) -> Dict[str, str]:
        """
        Genera la transcripción de sample_clean_60s.wav y crea sample_clean_prompt.wav (5-12s)
        con su transcripción correspondiente para optimizar la síntesis F5-TTS.
        """
        user_sample_dir = os.path.join(output_dir, user_id)
        wav_60s = os.path.join(user_sample_dir, "sample_clean_60s.wav")
        txt_60s = os.path.join(user_sample_dir, "sample_clean_60s.txt")
        wav_prompt = os.path.join(user_sample_dir, "sample_clean_prompt.wav")
        txt_prompt = os.path.join(user_sample_dir, "sample_clean_prompt.txt")

        if not os.path.exists(wav_60s):
            return {}

        results = {}
        if transcriber is None:
            try:
                from core.stt.transcriber import WhisperTranscriber
                transcriber = WhisperTranscriber(model_size="base")
            except Exception:
                pass

        full_text = ""
        segs = []
        if transcriber is not None:
            try:
                segs = transcriber.transcribe_file(wav_60s)
                full_text = " ".join(s["text"].strip() for s in segs if s.get("text")).strip()
            except Exception:
                pass

        if full_text and (not os.path.exists(txt_60s) or os.path.getsize(txt_60s) == 0):
            with open(txt_60s, "w", encoding="utf-8") as f:
                f.write(full_text)
            results["txt_60s"] = txt_60s

        if not os.path.exists(wav_prompt) or not os.path.exists(txt_prompt):
            try:
                data, sr = sf.read(wav_60s)
                best_start = 0.0
                best_end = min(8.0, len(data) / sr)
                prompt_text = ""

                # 1. Buscar un segmento único autocontenido de 4.5s a 10.0s con buena densidad de habla
                if segs:
                    for s in segs:
                        dur = s["end"] - s["start"]
                        text_words = len(s.get("text", "").strip().split())
                        if 4.5 <= dur <= 10.0 and text_words >= 6:
                            best_start = s["start"]
                            best_end = s["end"]
                            prompt_text = s["text"].strip()
                            break

                    # 2. Si no hay un solo segmento, acumular desde el inicio hasta alcanzar 5 a 9s en límite de oración
                    if not prompt_text:
                        for s in segs:
                            if s["end"] >= 5.0:
                                best_end = min(s["end"], 10.0)
                                prompt_text = " ".join(item["text"].strip() for item in segs if item["end"] <= best_end + 0.1).strip()
                                break

                if not prompt_text and full_text:
                    prompt_text = full_text[:120]

                s_sample = int(best_start * sr)
                e_sample = min(len(data), int(best_end * sr))
                prompt_data = data[s_sample:e_sample]

                sf.write(wav_prompt, prompt_data, sr, subtype="PCM_16")
                with open(txt_prompt, "w", encoding="utf-8") as f:
                    f.write(prompt_text or full_text or "Hola, buenas.")
                results["wav_prompt"] = wav_prompt
                results["txt_prompt"] = txt_prompt
            except Exception:
                pass

        return results
