"""
Módulo de Detección de Solapamiento de Habla (Overlap Detection)
Identifica cuándo dos o más interlocutores hablan simultáneamente
a lo largo de las pistas de una sesión multi-track de Discord.
"""

from typing import Dict, List, Tuple


def intervals_overlap(
    start_a: float, end_a: float, start_b: float, end_b: float, min_overlap: float = 0.1
) -> bool:
    """
    Determina si dos intervalos de tiempo se solapan al menos min_overlap segundos.
    """
    overlap_duration = min(end_a, end_b) - max(start_a, start_b)
    return overlap_duration >= min_overlap


def find_overlapping_speakers(
    speaker_id: str,
    start: float,
    end: float,
    all_speakers_intervals: Dict[str, List[Tuple[float, float]]],
    min_overlap: float = 0.1,
) -> List[str]:
    """
    Retorna la lista de user_ids de otros participantes que hablaron
    durante el intervalo [start, end] del interlocutor actual.
    """
    overlapping: List[str] = []

    for other_id, intervals in all_speakers_intervals.items():
        if other_id == speaker_id:
            continue

        for other_start, other_end in intervals:
            if intervals_overlap(start, end, other_start, other_end, min_overlap=min_overlap):
                if other_id not in overlapping:
                    overlapping.append(other_id)
                break  # Con un solapamiento confirmado en este hablante es suficiente

    return sorted(overlapping)


def extract_non_overlapping_intervals(
    target_speaker_id: str,
    all_speakers_intervals: Dict[str, List[Tuple[float, float]]],
    min_duration: float = 2.5,
    margin_seconds: float = 0.2,
) -> List[Tuple[float, float]]:
    """
    Retorna intervalos de habla del target_speaker donde NINGÚN otro hablante
    estaba activo, aplicando un margen de seguridad (margin_seconds)
    y filtrando por duración mínima para garantizar muestras limpias para TTS.
    """
    target_intervals = all_speakers_intervals.get(target_speaker_id, [])
    if not target_intervals:
        return []

    # Recolectar todos los intervalos de otros hablantes
    other_intervals: List[Tuple[float, float]] = []
    for other_id, intervals in all_speakers_intervals.items():
        if other_id == target_speaker_id:
            continue
        for s, e in intervals:
            # Expandir ligeramente el intervalo ajeno con el margen de seguridad
            other_intervals.append((max(0.0, s - margin_seconds), e + margin_seconds))

    # Ordenar y fusionar intervalos de otros hablantes
    other_intervals.sort(key=lambda x: x[0])
    merged_others: List[Tuple[float, float]] = []
    for s, e in other_intervals:
        if not merged_others or merged_others[-1][1] < s:
            merged_others.append((s, e))
        else:
            merged_others[-1] = (merged_others[-1][0], max(merged_others[-1][1], e))

    clean_intervals: List[Tuple[float, float]] = []

    for t_start, t_end in target_intervals:
        current_pieces = [(t_start, t_end)]

        for o_start, o_end in merged_others:
            next_pieces = []
            for p_start, p_end in current_pieces:
                # Caso 1: sin solapamiento
                if p_end <= o_start or p_start >= o_end:
                    next_pieces.append((p_start, p_end))
                else:
                    # Caso 2: solapamiento parcial o total, restar la porción ajena
                    if p_start < o_start:
                        next_pieces.append((p_start, o_start))
                    if p_end > o_end:
                        next_pieces.append((o_end, p_end))
            current_pieces = next_pieces

        for piece_start, piece_end in current_pieces:
            duration = piece_end - piece_start
            if duration >= min_duration:
                clean_intervals.append((round(piece_start, 3), round(piece_end, 3)))

    return clean_intervals
