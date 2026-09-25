"""
Test Suite: Detección de Solapamiento (Overlap Detector)
Verifica la detección de solapamiento entre interlocutores y la
extracción de segmentos de voz limpios y no solapados para TTS.
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.vad.overlap_detector import (
    intervals_overlap,
    find_overlapping_speakers,
    extract_non_overlapping_intervals,
)


def test_intervals_overlap():
    # Caso 1: Solapamiento claro
    assert intervals_overlap(1.0, 5.0, 3.0, 6.0) is True
    # Caso 2: Totalmente contenido
    assert intervals_overlap(1.0, 10.0, 3.0, 5.0) is True
    # Caso 3: Adyacente sin solapamiento
    assert intervals_overlap(1.0, 2.0, 2.0, 3.0) is False
    # Caso 4: Separados
    assert intervals_overlap(1.0, 2.0, 5.0, 6.0) is False
    # Caso 5: Solapamiento menor que el umbral (0.1s)
    assert intervals_overlap(1.0, 2.0, 1.95, 3.0, min_overlap=0.1) is False
    assert intervals_overlap(1.0, 2.0, 1.85, 3.0, min_overlap=0.1) is True


def test_find_overlapping_speakers():
    all_speakers = {
        "user_marce": [(0.0, 5.0), (10.0, 15.0)],
        "user_arbustin": [(4.0, 8.0), (20.0, 25.0)],
        "user_kevin": [(14.5, 18.0)],
    }

    # Marce [0, 5] se solapa con Arbustin [4, 8] en [4, 5]
    overlap_1 = find_overlapping_speakers("user_marce", 0.0, 5.0, all_speakers)
    assert overlap_1 == ["user_arbustin"]

    # Marce [10, 15] se solapa con Kevin [14.5, 18] en [14.5, 15]
    overlap_2 = find_overlapping_speakers("user_marce", 10.0, 15.0, all_speakers)
    assert overlap_2 == ["user_kevin"]

    # Marce [8.5, 9.5] no se solapa con nadie
    overlap_3 = find_overlapping_speakers("user_marce", 8.5, 9.5, all_speakers)
    assert overlap_3 == []


def test_extract_non_overlapping_intervals():
    # User A habla [0, 10]
    # User B interrumpe en [3, 5]
    all_speakers = {
        "user_a": [(0.0, 10.0)],
        "user_b": [(3.0, 5.0)],
    }

    # Con margin_seconds=0.2 y min_duration=2.5:
    # User B expandido: [2.8, 5.2]
    # Resto de User A: [0.0, 2.8] (duración 2.8s >= 2.5s) y [5.2, 10.0] (duración 4.8s >= 2.5s)
    clean = extract_non_overlapping_intervals("user_a", all_speakers, min_duration=2.5, margin_seconds=0.2)
    assert len(clean) == 2
    assert clean[0] == (0.0, 2.8)
    assert clean[1] == (5.2, 10.0)


def test_extract_non_overlapping_min_duration_filter():
    # Segmento remanente menor a min_duration debe ser descartado
    all_speakers = {
        "user_a": [(0.0, 5.0)],
        "user_b": [(1.0, 4.0)],
    }
    # User B ocupa [0.8, 4.2].
    # Pedazos de User A: [0, 0.8] (0.8s < 3.0s) y [4.2, 5.0] (0.8s < 3.0s) -> ambos descartados
    clean = extract_non_overlapping_intervals("user_a", all_speakers, min_duration=3.0, margin_seconds=0.2)
    assert clean == []
