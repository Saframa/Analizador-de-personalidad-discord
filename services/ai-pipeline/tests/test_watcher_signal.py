"""
Tests unitarios para el sistema de señalización instantánea del Watcher (WatcherSignal).
"""

import time
import pytest
from core.watcher_signal import WatcherSignalListener, send_watcher_signal

TEST_PORT = 5057  # Usar puerto alternativo para pruebas aisladas


def test_listener_timeout_returns_none():
    listener = WatcherSignalListener(port=TEST_PORT)
    start = time.time()
    result = listener.wait_for_signal(timeout=0.15)
    elapsed = time.time() - start

    listener.close()
    assert result is None
    assert 0.10 <= elapsed <= 0.35


def test_listener_receives_instant_signal():
    listener = WatcherSignalListener(port=TEST_PORT)

    # Enviar señal
    success = send_watcher_signal(session_id="2026-09-27_unit_test", port=TEST_PORT)
    assert success is True

    start = time.time()
    signal = listener.wait_for_signal(timeout=1.0)
    elapsed = time.time() - start

    listener.close()
    assert signal is not None
    assert signal.get("event") == "SESSION_READY"
    assert signal.get("sessionId") == "2026-09-27_unit_test"
    assert elapsed < 0.15  # Despertar casi instantáneo (< 150 ms)


def test_listener_drain_extra_packets():
    listener = WatcherSignalListener(port=TEST_PORT)

    # Enviar múltiples señales repetidas
    send_watcher_signal("sess_1", port=TEST_PORT)
    send_watcher_signal("sess_2", port=TEST_PORT)
    send_watcher_signal("sess_3", port=TEST_PORT)

    # La primera lectura debe capturar una y drenar las extras
    first = listener.wait_for_signal(timeout=0.5)
    assert first is not None

    # La siguiente llamada con timeout corto debe dar None porque el buffer fue drenado
    second = listener.wait_for_signal(timeout=0.1)
    assert second is None

    listener.close()
