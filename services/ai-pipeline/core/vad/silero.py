"""
Detector de Actividad de Voz (VAD) usando Silero VAD.
Convierte audio a 16 kHz Mono y extrae estampas de tiempo exactas (segundos)
donde existe actividad vocal humana.
"""

from typing import List, Tuple, Union, Optional
import os
import torch


class SileroVADDetector:
    def __init__(self, onnx: bool = True, threshold: float = 0.5):
        """
        Inicializa el detector Silero VAD.
        Usa ONNX por defecto para inferencia ultrarrápida sin consumir VRAM de GPU.
        """
        self.threshold = threshold
        self.onnx = onnx
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from silero_vad import load_silero_vad
                self._model = load_silero_vad(onnx=self.onnx)
            except Exception:
                # Fallback via torch.hub
                self._model, _ = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    onnx=self.onnx,
                )
        return self._model

    def detect_speech_intervals(
        self,
        audio_path: str,
        target_sample_rate: int = 16000,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 300,
    ) -> List[Tuple[float, float]]:
        """
        Analiza un archivo de audio y retorna una lista de intervalos de voz:
        [(start_sec, end_sec), ...]
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")

        # Si el archivo está vacío o es un encabezado WAV sin audio (<= 100 bytes)
        if os.path.getsize(audio_path) <= 100:
            return []

        from silero_vad import read_audio, get_speech_timestamps

        try:
            wav = read_audio(audio_path, sampling_rate=target_sample_rate)
        except Exception as e:
            # Si falla read_audio (ej. formato exótico), intentar con torchaudio / soundfile
            import torchaudio
            waveform, sr = torchaudio.load(audio_path)
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)
            if sr != target_sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sample_rate)
                waveform = resampler(waveform)
            wav = waveform.squeeze(0)

        # Si no hay muestras suficientes (< 0.1 seg)
        if wav.shape[-1] < target_sample_rate * 0.1:
            return []

        model = self._get_model()

        timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=target_sample_rate,
            threshold=self.threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
        )

        intervals: List[Tuple[float, float]] = []
        for item in timestamps:
            start_sec = round(float(item["start"]) / target_sample_rate, 3)
            end_sec = round(float(item["end"]) / target_sample_rate, 3)
            intervals.append((start_sec, end_sec))

        return intervals
