"""
Orquestador CLI del Pipeline de Inteligencia Artificial (Fase 2)
Procesa sesiones de audio de Discord:
1. Valida el Contrato A (session_metadata.json).
2. Ejecuta Silero VAD y detecta solapamientos entre pistas de audio.
3. Transcribe el habla con faster-whisper en CUDA FP16 con léxico uruguayo/rioplatense.
4. Genera el Contrato B (transcript.json) ordenado cronológicamente.
5. Cura y normaliza muestras de voz de 30-60s para clonación en Fase 5.
6. Libera la memoria VRAM de la GPU al finalizar.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Asegurar importación de core
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.contracts.models import (
    SessionMetadata,
    SessionTranscript,
    Utterance,
)
from core.curator.voice_curator import VoiceCurator
from core.stt.transcriber import WhisperTranscriber, release_gpu_memory
from core.vad.overlap_detector import (
    extract_non_overlapping_intervals,
    find_overlapping_speakers,
)
from core.vad.silero import SileroVADDetector

# Configurar stdout/stderr en UTF-8 para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def resolve_session_path(session_arg: str, base_storage_dir: str) -> str:
    """Resuelve la ruta absoluta al directorio de la sesión solicitada."""
    raw_sessions_dir = os.path.join(base_storage_dir, "raw_sessions")
    if not os.path.exists(raw_sessions_dir):
        raise FileNotFoundError(f"Directorio no encontrado: {raw_sessions_dir}")

    if session_arg == "latest":
        candidates = sorted(
            [
                d
                for d in glob.glob(os.path.join(raw_sessions_dir, "*"))
                if os.path.isdir(d) and os.path.exists(os.path.join(d, "session_metadata.json"))
            ]
        )
        if not candidates:
            raise FileNotFoundError(f"No se encontraron sesiones con metadata en {raw_sessions_dir}")
        return candidates[-1]

    # Si se pasó un ID de sesión o ruta directa
    if os.path.isdir(session_arg):
        return os.path.abspath(session_arg)

    session_path = os.path.join(raw_sessions_dir, session_arg)
    if os.path.isdir(session_path):
        return session_path

    raise FileNotFoundError(f"No se encontró la sesión: {session_arg}")


def process_session(
    session_dir: str,
    model_size: str = "large-v3",
    curate_samples: bool = True,
    base_storage_dir: str = "",
) -> SessionTranscript:
    """Ejecuta el pipeline completo de transcripción y curación para una sesión."""
    metadata_file = os.path.join(session_dir, "session_metadata.json")
    if not os.path.exists(metadata_file):
        raise FileNotFoundError(f"session_metadata.json no existe en {session_dir}")

    print("\n" + "=" * 65)
    print(f"🎙️  PROCESANDO SESION: {os.path.basename(session_dir)}")
    print("=" * 65)

    # 1. Cargar y validar Contrato A
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = SessionMetadata.model_validate_json(f.read())
    print(f"[1/5] Contrato A validado correctamente:")
    print(f"      Canal: #{metadata.channel_name} | Duracion: {metadata.duration_seconds:.1f}s")
    print(f"      Participantes: {len(metadata.participants)}")

    # 2. Silero VAD para cada participante
    print("\n[2/5] Ejecutando Silero VAD para detectar intervalos de actividad vocal...")
    vad_detector = SileroVADDetector()
    all_speakers_intervals: Dict[str, List[Tuple[float, float]]] = {}

    for participant in metadata.participants:
        user_id = participant.user_id
        audio_info = metadata.audio_files.get(user_id)
        if not audio_info:
            all_speakers_intervals[user_id] = []
            continue

        audio_file_path = os.path.join(session_dir, audio_info.filename)
        if not os.path.exists(audio_file_path) or audio_info.size_bytes <= 100:
            print(f"      • {participant.display_name} ({user_id}): Sin audio grabado")
            all_speakers_intervals[user_id] = []
            continue

        intervals = vad_detector.detect_speech_intervals(audio_file_path)
        all_speakers_intervals[user_id] = intervals
        print(f"      • {participant.display_name} ({user_id}): {len(intervals)} intervalos de voz detectados")

    # 3. Transcripción con faster-whisper en CUDA
    print(f"\n[3/5] Transcribiendo pistas de audio con faster-whisper ({model_size}) en CUDA...")
    participant_map = {p.user_id: p for p in metadata.participants}
    raw_utterances: List[Utterance] = []

    with WhisperTranscriber(model_size=model_size, device="cuda", compute_type="float16") as transcriber:
        for user_id, intervals in all_speakers_intervals.items():
            if not intervals:
                continue

            audio_info = metadata.audio_files[user_id]
            audio_file_path = os.path.join(session_dir, audio_info.filename)
            participant = participant_map[user_id]

            print(f"      Transcribiendo a {participant.display_name} ({participant.username})...")
            segments = transcriber.transcribe_file(audio_file_path)

            for seg in segments:
                # Detectar solapamiento con otros participantes
                overlapping = find_overlapping_speakers(
                    speaker_id=user_id,
                    start=seg["start"],
                    end=seg["end"],
                    all_speakers_intervals=all_speakers_intervals,
                )

                utterance = Utterance(
                    id=1,  # Asignado luego de ordenar
                    user_id=user_id,
                    username=participant.username,
                    start_time=seg["start"],
                    end_time=seg["end"],
                    duration=seg["duration"],
                    text=seg["text"],
                    confidence=seg["confidence"],
                    overlapping_speakers=overlapping,
                )
                raw_utterances.append(utterance)

    # 4. Ordenar cronológicamente y asignar IDs correlativos
    print("\n[4/5] Ensamblando y ordenando transcripción cronológica...")
    raw_utterances.sort(key=lambda u: u.start_time)
    for idx, u in enumerate(raw_utterances, start=1):
        u.id = idx

    transcript = SessionTranscript(
        version="1.0.0",
        session_id=metadata.session_id,
        processed_at=datetime.now(timezone.utc),
        model=f"faster-whisper/{model_size}",
        utterances=raw_utterances,
    )

    transcript_output_path = os.path.join(session_dir, "transcript.json")
    transcript.save_atomic(transcript_output_path)
    print(f"      [OK] transcript.json guardado ({len(transcript.utterances)} enunciados)")

    # 5. Curación de muestras de voz si se solicitó
    if curate_samples:
        print("\n[5/5] Curando muestras de voz de alta fidelidad para clonación...")
        curator = VoiceCurator(target_sample_rate=24000, target_lufs=-18.0)
        clean_samples_dir = os.path.join(base_storage_dir, "clean_samples")

        for user_id, intervals in all_speakers_intervals.items():
            if not intervals:
                continue

            audio_info = metadata.audio_files[user_id]
            audio_file_path = os.path.join(session_dir, audio_info.filename)
            participant = participant_map[user_id]

            # Extraer intervalos libres de solapamiento
            clean_intervals = extract_non_overlapping_intervals(
                target_speaker_id=user_id,
                all_speakers_intervals=all_speakers_intervals,
                min_duration=2.0,
                margin_seconds=0.15,
            )

            if not clean_intervals:
                print(f"      • {participant.display_name}: No cuenta con segmentos sin solapamiento suficientes.")
                continue

            res = curator.curate_user_sample(
                user_id=user_id,
                audio_path=audio_file_path,
                clean_intervals=clean_intervals,
                output_dir=clean_samples_dir,
                target_max_duration=60.0,
                min_required_duration=3.0,
            )

            if res:
                print(
                    f"      [OK] {participant.display_name}: {res['duration_seconds']}s guardados en "
                    f"storage/clean_samples/{user_id}/sample_clean_60s.wav"
                )
            else:
                print(f"      • {participant.display_name}: Audio limpio insuficiente (< 3s).")

    # Liberación explícita de VRAM
    release_gpu_memory()
    print("\n" + "=" * 65)
    print("✨ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
    print("=" * 65)
    return transcript


def main():
    parser = argparse.ArgumentParser(description="Orquestador STT y Curador de Voz para Discord Profiler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_parser = subparsers.add_parser("process", help="Procesa una sesión grabada")
    process_parser.add_argument(
        "--session",
        type=str,
        default="latest",
        help="ID de la sesión (ej. 2026-09-25_00-00-18) o 'latest'",
    )
    process_parser.add_argument(
        "--model-size",
        type=str,
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3", "turbo"],
        help="Tamaño del modelo faster-whisper (por defecto: medium para equilibrio óptimo)",
    )
    process_parser.add_argument(
        "--no-clean-samples",
        action="store_true",
        help="Omite la extracción de muestras limpias para clonación de voz",
    )
    process_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    args = parser.parse_args()

    if args.command == "process":
        # Determinar directorio base de almacenamiento (por defecto ../../storage)
        base_storage = args.storage_dir
        if not base_storage:
            base_storage = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "storage"))

        session_path = resolve_session_path(args.session, base_storage)
        process_session(
            session_dir=session_path,
            model_size=args.model_size,
            curate_samples=not args.no_clean_samples,
            base_storage_dir=base_storage,
        )


if __name__ == "__main__":
    main()
