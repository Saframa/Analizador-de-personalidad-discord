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
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Asegurar importación de core
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.contracts.models import (
    SessionMetadata,
    SessionTranscript,
    UserProfile,
    Utterance,
)
from core.curator.voice_curator import VoiceCurator
from core.profiler.gemini_analyzer import GeminiProfiler
from core.profiler.metrics import compute_user_metrics
from core.profiler.profile_synthesizer import ProfileSynthesizer
from core.stt.transcriber import WhisperTranscriber, release_gpu_memory
from core.tts.cloner import get_voice_cloner, release_tts_gpu_memory
from core.tts.player import play_audio_file
from core.twin.chat_session import DigitalTwinChat
from core.twin.compiler import compile_twin_prompt, extract_few_shot_dialogues
from core.vad.overlap_detector import (
    extract_non_overlapping_intervals,
    find_overlapping_speakers,
)
from core.vad.silero import SileroVADDetector

# Cargar variables de entorno (.env)
from dotenv import load_dotenv

load_dotenv(os.path.join(CURRENT_DIR, ".env"))
load_dotenv(os.path.join(CURRENT_DIR, "..", "..", ".env"))
load_dotenv(os.path.join(CURRENT_DIR, "..", "voice-recorder", ".env"))

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

    if session_arg == "all":
        return "all"

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


def cleanup_session_audio(session_dir: str) -> int:
    """
    Elimina los archivos pesados de audio en raw_sessions/<session_id>/audio/
    luego de que la sesión fue completamente transcripta, curada y analizada.
    Conserva transcript.json, session_metadata.json y las muestras de referencia en storage/clean_samples/.
    Retorna la cantidad de bytes liberados.
    """
    audio_dir = os.path.join(session_dir, "audio")
    if not os.path.exists(audio_dir):
        return 0

    purged_bytes = 0
    count = 0
    for filename in os.listdir(audio_dir):
        fp = os.path.join(audio_dir, filename)
        if os.path.isfile(fp) and not filename.startswith("."):
            purged_bytes += os.path.getsize(fp)
            os.remove(fp)
            count += 1

    if count > 0:
        receipt_path = os.path.join(audio_dir, ".purged")
        with open(receipt_path, "w", encoding="utf-8") as f:
            f.write(
                f"Audio purgado exitosamente tras transcripción y perfilado el {datetime.now(timezone.utc).isoformat()}.\n"
                f"Archivos eliminados: {count} ({purged_bytes / (1024**2):.2f} MB liberados de disco).\n"
            )
        print(f"\n[LIMPIEZA DE DISCO] Audio raw purgado: {count} archivos eliminados ({purged_bytes / (1024**2):.2f} MB liberados).")
        print(f"                   Las transcripciones y muestras limpias de referencia (60s) se preservan intactas.")

    return purged_bytes


def profile_session(
    session_dir: str,
    base_storage_dir: str,
    model_name: str = "gemini-flash-latest",
    mock: bool = False,
    target_user_id: Optional[str] = None,
    cleanup_audio: bool = True,
) -> List[UserProfile]:
    """
    Ejecuta el análisis de personalidad y perfilado psicológico con Gemini API
    para los participantes de la sesión y genera/actualiza los perfiles acumulados.
    """
    metadata_file = os.path.join(session_dir, "session_metadata.json")
    transcript_file = os.path.join(session_dir, "transcript.json")

    if not os.path.exists(metadata_file):
        raise FileNotFoundError(f"session_metadata.json no existe en {session_dir}")
    if not os.path.exists(transcript_file):
        raise FileNotFoundError(
            f"transcript.json no existe en {session_dir}. Ejecuta primero: python main.py process --session {os.path.basename(session_dir)}"
        )

    print("\n" + "=" * 65)
    print(f"🧠 PERFILADO PSICOLOGICO Y CONDUCTUAL: {os.path.basename(session_dir)}")
    print("=" * 65)

    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = SessionMetadata.model_validate_json(f.read())
    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript = SessionTranscript.model_validate_json(f.read())

    profiler = GeminiProfiler(model_name=model_name, mock=mock)
    synthesizer = ProfileSynthesizer(storage_dir=base_storage_dir)
    updated_profiles: List[UserProfile] = []

    for participant in metadata.participants:
        user_id = participant.user_id
        if target_user_id and user_id != target_user_id:
            continue

        print(f"\n[ANALISIS] Evaluando a {participant.display_name} (@{participant.username})...")

        # 1. Métricas cuantitativas
        metrics = compute_user_metrics(transcript, user_id)
        if metrics.turn_count == 0:
            print(f"      • Sin intervenciones habladas en esta sesión. Omitiendo perfilado profundo.")
            continue

        print(f"      • Métricas: {metrics.turn_count} turnos, {metrics.total_words} palabras, "
              f"{metrics.avg_words_per_turn:.1f} pal/turno, cadencia '{metrics.cadence}', "
              f"interrupciones: {metrics.interruption_ratio*100:.1f}%")

        # 2. Inferencia cualitativa / Gemini
        print(f"      • Ejecutando análisis sociolingüístico y Big Five (modelo: {model_name} | mock={profiler.mock})...")
        evaluation = profiler.analyze_user_session(transcript, user_id, participant.display_name, metrics)

        # 3. Síntesis acumulada
        profile = synthesizer.synthesize_profile(
            user_id=user_id,
            username=participant.username,
            session_id=metadata.session_id,
            session_metrics=metrics,
            evaluation=evaluation,
        )
        updated_profiles.append(profile)

        # 4. Reporte amigable en consola
        bf = profile.big_five
        print(f"      [OK] Perfil sintetizado (Sesión #{profile.total_sessions_analyzed}, {profile.total_speaking_seconds:.1f}s acumulados):")
        print(f"         - Rol en el grupo: {profile.group_role.primary_role}")
        print(f"         - Humor y estilo:  {profile.communication_style.humor_type}")
        print(f"         - Big Five:")
        print(f"           • Apertura:        {bf.openness.score:.2f} (confianza: {bf.openness.confidence:.2f})")
        print(f"           • Responsabilidad: {bf.conscientiousness.score:.2f} (confianza: {bf.conscientiousness.confidence:.2f})")
        print(f"           • Extraversión:    {bf.extraversion.score:.2f} (confianza: {bf.extraversion.confidence:.2f})")
        print(f"           • Amabilidad:      {bf.agreeableness.score:.2f} (confianza: {bf.agreeableness.confidence:.2f})")
        print(f"           • Neuroticismo:    {bf.neuroticism.score:.2f} (confianza: {bf.neuroticism.confidence:.2f})")
        print(f"         - Jerga rioplatense: {', '.join(profile.dialect_markers.favorite_slang) or 'ninguna'}")
        sample_cite = bf.openness.evidence_quotes[0].quote if bf.openness.evidence_quotes else 'N/A'
        print(f"         - Cita de evidencia: \"{sample_cite}\"")
        print(f"         - Guardado en: storage/profiles/{user_id}/profile.json")

    # Limpieza automática del audio raw para ahorrar espacio si está habilitado
    if cleanup_audio:
        cleanup_session_audio(session_dir)

    print("\n" + "=" * 65)
    print("🎉 PERFILADO COMPLETADO CON EXITO")
    print("=" * 65)
    return updated_profiles


def interactive_chat(
    base_storage_dir: str,
    target_user_id: Optional[str] = None,
    model_name: str = "gemini-flash-latest",
    mock: bool = False,
    single_turn_prompt: Optional[str] = None,
    enable_voice: bool = False,
    play_audio: bool = False,
) -> None:
    """
    Inicia una sesión interactiva de conversación en consola con el Gemelo Digital de un amigo.
    Opcionalmente sintetiza la voz (TTS) con F5-TTS y la reproduce por altavoces.
    """
    profiles_dir = os.path.join(base_storage_dir, "profiles")
    if not os.path.exists(profiles_dir):
        print(f"❌ Error: No se encontró el directorio de perfiles en {profiles_dir}.")
        print("   Ejecuta primero: python main.py process --session latest --profile")
        return

    profile_files = glob.glob(os.path.join(profiles_dir, "*", "profile.json"))
    if not profile_files:
        print("❌ Error: No hay perfiles guardados. Analiza primero una llamada de Discord.")
        return

    profiles: List[UserProfile] = []
    for pf in profile_files:
        try:
            with open(pf, "r", encoding="utf-8") as f:
                profiles.append(UserProfile.model_validate_json(f.read()))
        except Exception:
            pass

    if not profiles:
        print("❌ Error: No se pudieron cargar los perfiles existentes.")
        return

    selected_profile: Optional[UserProfile] = None

    if target_user_id:
        for p in profiles:
            if p.user_id == target_user_id or p.username.lower() == target_user_id.lower():
                selected_profile = p
                break
        if not selected_profile:
            print(f"❌ No se encontró un perfil para el usuario '{target_user_id}'.")
            return
    elif len(profiles) == 1 or single_turn_prompt:
        selected_profile = profiles[0]
    else:
        print("\n" + "=" * 65)
        print("👥 SELECCIONA UN GEMELO DIGITAL PARA CONVERSAR:")
        print("=" * 65)
        for idx, p in enumerate(profiles, start=1):
            print(f"[{idx}] {p.username} (ID: {p.user_id})")
            print(f"    Rol: {p.group_role.primary_role} | {p.total_sessions_analyzed} llamadas ({p.total_speaking_seconds:.1f}s)")
        print("-" * 65)
        try:
            choice_str = input("Elige un número: ").strip()
            choice_idx = int(choice_str) - 1
            if 0 <= choice_idx < len(profiles):
                selected_profile = profiles[choice_idx]
            else:
                print("Opción inválida. Seleccionando el primero por defecto.")
                selected_profile = profiles[0]
        except Exception:
            selected_profile = profiles[0]

    # Extraer diálogos reales few-shot de las sesiones guardadas
    few_shots = []
    raw_sessions_dir = os.path.join(base_storage_dir, "raw_sessions")
    if os.path.exists(raw_sessions_dir):
        for t_file in glob.glob(os.path.join(raw_sessions_dir, "*", "transcript.json")):
            try:
                with open(t_file, "r", encoding="utf-8") as f:
                    t_obj = SessionTranscript.model_validate_json(f.read())
                    pairs = extract_few_shot_dialogues(t_obj, selected_profile.user_id, max_pairs=3)
                    few_shots.extend(pairs)
                    if len(few_shots) >= 5:
                        break
            except Exception:
                pass

    chat = DigitalTwinChat(
        profile=selected_profile,
        few_shot_dialogues=few_shots,
        model_name=model_name,
        mock=mock,
    )

    cloner = None
    if enable_voice:
        try:
            cloner = get_voice_cloner(mock=mock)
        except Exception as e:
            print(f"⚠️ No se pudo inicializar el clonador de voz: {e}")

    comm = selected_profile.communication_style
    print("\n" + "=" * 65)
    print(f"🤖 GEMELO DIGITAL: {selected_profile.username} (@{selected_profile.user_id})")
    print("=" * 65)
    print(f"🎭 Rol en el grupo:    {selected_profile.group_role.primary_role}")
    print(f"💬 Estilo de humor:    {comm.humor_type}")
    print(f"⏱️  Cadencia y turno:   {comm.cadence} (~{comm.avg_words_per_turn:.0f} palabras/turno)")
    print(f"🇺🇾 Modismos preferidos: {', '.join(selected_profile.dialect_markers.favorite_slang) or 'bo, ta, flama'}")
    print(f"🔥 Temperatura modelo: {chat.temperature} (calibrada por Big Five)")
    print(f"🧠 Backend:            {chat.model_name} (mock={chat.mock})")
    print(f"🎙️ Clonación de voz:  {'ACTIVA (F5-TTS)' if cloner else 'Desactivada'}")
    if play_audio and cloner:
        print("🔊 Reproducción audio: ACTIVA (Altavoces)")
    print("-" * 65)
    print("Escribe tu mensaje y presiona Enter. (Escribe 'salir' para terminar).")
    print("=" * 65 + "\n")

    def _speak_reply(text_reply: str) -> None:
        if cloner:
            try:
                out_wav = cloner.clone_for_user(
                    user_id=selected_profile.user_id,
                    target_text=text_reply,
                    base_storage_dir=base_storage_dir,
                )
                print(f"   🔊 [Audio clonado: {out_wav}]")
                if play_audio:
                    play_audio_file(out_wav)
            except Exception as e:
                print(f"   ⚠️ [Error en síntesis de voz: {e}]")

    if single_turn_prompt:
        print(f"Tú: {single_turn_prompt}")
        reply = chat.send_message(single_turn_prompt)
        print(f"{selected_profile.username}: {reply}\n")
        _speak_reply(reply)
        if cloner:
            release_tts_gpu_memory()
        return

    while True:
        try:
            user_msg = input("Tú: ").strip()
            if not user_msg:
                continue
            if user_msg.lower() in ["salir", "exit", "quit", "chau"]:
                farewell = "¡Nos vemos, bo! Cuidate."
                print(f"\n{selected_profile.username}: {farewell}\n")
                _speak_reply(farewell)
                break

            reply = chat.send_message(user_msg)
            print(f"\n{selected_profile.username}: {reply}\n")
            _speak_reply(reply)
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{selected_profile.username}: ¡Chau che, nos vemos!\n")
            break

    if cloner:
        release_tts_gpu_memory()


def synthesize_user_voice(
    user_id: str,
    text: str,
    base_storage_dir: str,
    output_path: Optional[str] = None,
    mock: bool = False,
    play: bool = False,
) -> str:
    """
    Sintetiza cualquier texto con la voz curada de un amigo utilizando F5-TTS en la GPU.
    """
    print("\n" + "=" * 65)
    print(f"🎙️ SINTETIZADOR DE VOZ CLONADA (ZERO-SHOT): Usuario @{user_id}")
    print("=" * 65)
    cloner = get_voice_cloner(mock=mock)
    try:
        out_wav = cloner.clone_for_user(
            user_id=user_id,
            target_text=text,
            base_storage_dir=base_storage_dir,
            output_path=output_path,
        )
        print(f"✅ Audio sintetizado con éxito: {out_wav}")
        if play:
            print("▶️ Reproduciendo por los altavoces...")
            play_audio_file(out_wav)
        return out_wav
    finally:
        release_tts_gpu_memory()


def watch_sessions(
    base_storage_dir: str,
    interval: int = 15,
    profile: bool = True,
    delete_audio: bool = True,
    model_size: str = "medium",
) -> None:
    """
    Monitorea de forma continua storage/raw_sessions/ y procesa automáticamente
    las nuevas llamadas finalizadas de Discord, transcribiéndolas, actualizando los
    perfiles longitudinales y eliminando los audios pesados para no ocupar disco.
    """
    raw_sessions_dir = os.path.join(base_storage_dir, "raw_sessions")
    if not os.path.exists(raw_sessions_dir):
        os.makedirs(raw_sessions_dir, exist_ok=True)

    print("\n" + "=" * 65)
    print("👀 MODO VIGILANTE AUTÓNOMO (WATCHER) INICIADO")
    print(f"📁 Monitoreando directorio:  {raw_sessions_dir}")
    print(f"⏱️  Intervalo de sondeo:     {interval}s")
    print(f"🧠 Perfilado Gemini:        {'ACTIVO' if profile else 'Desactivado'}")
    print(f"🧹 Limpieza de disco:       {'ACTIVA (se liberará el audio tras perfilar)' if delete_audio else 'Desactivada'}")
    print(f"🎙️ Modelo STT:              faster-whisper ({model_size})")
    print("=" * 65)
    print("El sistema procesará automáticamente cualquier llamada apenas termine.")
    print("Presiona Ctrl+C en cualquier momento para detener el vigilante.\n")

    while True:
        try:
            candidates = sorted(glob.glob(os.path.join(raw_sessions_dir, "*")))
            for session_dir in candidates:
                if not os.path.isdir(session_dir):
                    continue
                meta_file = os.path.join(session_dir, "session_metadata.json")
                if not os.path.exists(meta_file):
                    continue

                transcript_file = os.path.join(session_dir, "transcript.json")
                audio_dir = os.path.join(session_dir, "audio")
                purged_file = os.path.join(audio_dir, ".purged")

                # Verificar si tiene audio pendiente y no fue purgada
                if os.path.exists(audio_dir) and not os.path.exists(purged_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        if not meta.get("ended_at"):
                            continue  # Llamada aún en curso en Discord
                    except Exception:
                        continue

                    session_id = os.path.basename(session_dir)
                    print(f"\n🔔 [NUEVA LLAMADA DETECTADA: {session_id}]")
                    if not os.path.exists(transcript_file):
                        process_session(
                            session_dir=session_dir,
                            model_size=model_size,
                            curate_samples=True,
                            base_storage_dir=base_storage_dir,
                        )
                    if profile:
                        profile_session(
                            session_dir=session_dir,
                            base_storage_dir=base_storage_dir,
                            cleanup_audio=delete_audio,
                        )
                    elif delete_audio:
                        cleanup_session_audio(session_dir)
                    print(f"✅ [LLAMADA {session_id} COMPLETADA - AUDIO PURGADO]\n")

            time.sleep(interval)
        except (KeyboardInterrupt, EOFError):
            print("\n🛑 Vigilante detenido por el usuario.\n")
            break
        except Exception as e:
            print(f"⚠️ Error en ciclo de vigilancia: {e}")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Orquestador STT, Curador de Voz y Gemelo Digital")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: process
    process_parser = subparsers.add_parser("process", help="Procesa una sesión grabada (STT + Curación)")
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
        "--profile",
        action="store_true",
        help="Ejecuta automáticamente el perfilado de personalidad luego de la transcripción",
    )
    process_parser.add_argument(
        "--delete-audio",
        action="store_true",
        help="Elimina los audios pesados luego de transcribir y curar las muestras",
    )
    process_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    # Subcomando: profile
    profile_parser = subparsers.add_parser("profile", help="Analiza y perfila psicológicamente una sesión ya procesada")
    profile_parser.add_argument(
        "--session",
        type=str,
        default="latest",
        help="ID de la sesión (ej. 2026-09-25_00-00-18) o 'latest'",
    )
    profile_parser.add_argument(
        "--model",
        type=str,
        default="gemini-flash-latest",
        help="Modelo de Gemini a utilizar (ej. gemini-flash-latest, gemini-2.5-flash)",
    )
    profile_parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Filtra el análisis para un usuario específico de Discord",
    )
    profile_parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza el modo mock local/offline sin consumir cuota de API de Gemini",
    )
    profile_parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Conserva los archivos de audio en disco en lugar de eliminarlos tras el análisis",
    )
    profile_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    # Subcomando: chat
    chat_parser = subparsers.add_parser("chat", help="Inicia un chat interactivo con el Gemelo Digital de un amigo")
    chat_parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="ID o nombre de usuario de Discord a emular (ej. 438796478035787780 o saframa)",
    )
    chat_parser.add_argument(
        "--model",
        type=str,
        default="gemini-flash-latest",
        help="Modelo de Gemini para el chat (por defecto: gemini-flash-latest)",
    )
    chat_parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza el modo mock local para pruebas sin conexión",
    )
    chat_parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Mensaje único para ejecución directa no interactiva",
    )
    chat_parser.add_argument(
        "--voice",
        action="store_true",
        help="Activa la síntesis de voz (TTS) para cada respuesta del Gemelo Digital",
    )
    chat_parser.add_argument(
        "--play",
        action="store_true",
        help="Reproduce automáticamente por altavoces el audio sintetizado",
    )
    chat_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    # Subcomando: tts
    tts_parser = subparsers.add_parser("tts", help="Sintetiza cualquier texto con la voz clonada de un amigo")
    tts_parser.add_argument(
        "--user-id",
        type=str,
        required=True,
        help="ID o nombre de usuario de Discord a emular (ej. 438796478035787780 o saframa)",
    )
    tts_parser.add_argument(
        "--text",
        type=str,
        required=True,
        help="Texto a sintetizar con la voz clonada",
    )
    tts_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Ruta personalizada para guardar el archivo WAV sintetizado",
    )
    tts_parser.add_argument(
        "--play",
        action="store_true",
        help="Reproduce el audio generado por los altavoces de inmediato",
    )
    tts_parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza el modo mock local para pruebas rápidas sin ocupar la GPU",
    )
    tts_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    # Subcomando: watch
    watch_parser = subparsers.add_parser("watch", help="Vigilante autónomo: detecta y procesa llamadas nuevas en segundo plano")
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Intervalo en segundos entre comprobaciones (por defecto: 15s)",
    )
    watch_parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Desactiva el perfilado automático con Gemini",
    )
    watch_parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Conserva los audios pesados en lugar de eliminarlos tras el perfilado",
    )
    watch_parser.add_argument(
        "--model-size",
        type=str,
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3", "turbo"],
        help="Modelo de faster-whisper",
    )
    watch_parser.add_argument(
        "--storage-dir",
        type=str,
        default="",
        help="Ruta base del directorio de almacenamiento",
    )

    args = parser.parse_args()

    base_storage = args.storage_dir
    if not base_storage:
        base_storage = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "storage"))

    if args.command == "process":
        if args.session == "all":
            raw_sessions_dir = os.path.join(base_storage, "raw_sessions")
            candidates = sorted(glob.glob(os.path.join(raw_sessions_dir, "*")))
            target_sessions = [
                d for d in candidates
                if os.path.isdir(d) and os.path.exists(os.path.join(d, "session_metadata.json"))
            ]
            if not target_sessions:
                print(f"❌ No se encontraron sesiones grabadas en {raw_sessions_dir}.")
                return
            print(f"🚀 Procesando {len(target_sessions)} sesiones acumuladas en lote...")
            for s_path in target_sessions:
                s_id = os.path.basename(s_path)
                t_file = os.path.join(s_path, "transcript.json")
                a_dir = os.path.join(s_path, "audio")
                p_file = os.path.join(a_dir, ".purged")
                if not os.path.exists(t_file) or (os.path.exists(a_dir) and not os.path.exists(p_file)):
                    print(f"\n▶️ [Procesando sesión: {s_id}]")
                    if not os.path.exists(t_file):
                        process_session(
                            session_dir=s_path,
                            model_size=args.model_size,
                            curate_samples=not args.no_clean_samples,
                            base_storage_dir=base_storage,
                        )
                    if args.profile:
                        profile_session(
                            session_dir=s_path,
                            base_storage_dir=base_storage,
                            cleanup_audio=args.delete_audio,
                        )
                    elif args.delete_audio:
                        cleanup_session_audio(s_path)
            print("\n🎉 Todas las sesiones pendientes han sido procesadas.")
        else:
            session_path = resolve_session_path(args.session, base_storage)
            process_session(
                session_dir=session_path,
                model_size=args.model_size,
                curate_samples=not args.no_clean_samples,
                base_storage_dir=base_storage,
            )
            if args.profile:
                profile_session(
                    session_dir=session_path,
                    base_storage_dir=base_storage,
                    cleanup_audio=args.delete_audio,
                )
            elif args.delete_audio:
                cleanup_session_audio(session_path)

    elif args.command == "profile":
        session_path = resolve_session_path(args.session, base_storage)
        profile_session(
            session_dir=session_path,
            base_storage_dir=base_storage,
            model_name=args.model,
            mock=args.mock,
            target_user_id=args.user_id,
            cleanup_audio=not args.keep_audio,
        )

    elif args.command == "chat":
        interactive_chat(
            base_storage_dir=base_storage,
            target_user_id=args.user_id,
            model_name=args.model,
            mock=args.mock,
            single_turn_prompt=args.prompt,
            enable_voice=args.voice,
            play_audio=args.play,
        )

    elif args.command == "tts":
        synthesize_user_voice(
            user_id=args.user_id,
            text=args.text,
            base_storage_dir=base_storage,
            output_path=args.output,
            mock=args.mock,
            play=args.play,
        )

    elif args.command == "watch":
        watch_sessions(
            base_storage_dir=base_storage,
            interval=args.interval,
            profile=not args.no_profile,
            delete_audio=not args.keep_audio,
            model_size=args.model_size,
        )


if __name__ == "__main__":
    main()
