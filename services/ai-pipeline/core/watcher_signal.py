"""
Módulo de Sincronización y Señalización IPC Rápida (Watcher Signal).
Permite despertar de forma instantánea (latencia ~0 ms) al vigilante autónomo (Watcher)
cuando el grabador de Discord finaliza de guardar una sesión de audio, reemplazando
el sondeo lento por suspensión pasiva sobre socket UDP loopback con fallback de seguridad.
"""

from __future__ import annotations

import json
import logging
import select
import socket
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("watcher_signal")

DEFAULT_SIGNAL_HOST = "127.0.0.1"
DEFAULT_SIGNAL_PORT = 5056


class WatcherSignalListener:
    """
    Receptor de semáforos/señales UDP para el Watcher autónomo.
    Mantiene el hilo en reposo absoluto (0% CPU) mediante select() del kernel
    hasta que llega una señal de sesión lista o expira el tiempo de sondeo de respaldo.
    """

    def __init__(self, host: str = DEFAULT_SIGNAL_HOST, port: int = DEFAULT_SIGNAL_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._setup_socket()

    def _setup_socket(self) -> None:
        """Inicializa y enlaza el socket UDP local."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.setblocking(False)
            self.sock = sock
            logger.info(f"⚡ [WatcherSignal] Semáforo de eventos activo en UDP {self.host}:{self.port}")
        except Exception as e:
            logger.warning(
                f"⚠️ [WatcherSignal] No se pudo enlazar socket en {self.host}:{self.port}: {e}. "
                "Se utilizará temporizador pasivo de respaldo."
            )
            self.sock = None

    def wait_for_signal(self, timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        """
        Espera la señal de que se guardó un nuevo audio hasta `timeout` segundos.
        - Si llega la señal: retorna el payload recibido inmediatamente (0 ms).
        - Si vence el timeout: retorna None para que el Watcher haga su ciclo de mantenimiento.
        """
        if not self.sock:
            time.sleep(max(0.1, timeout))
            return None

        effective_timeout = max(0.05, timeout)
        try:
            readable, _, _ = select.select([self.sock], [], [], effective_timeout)
            if readable:
                data, _ = self.sock.recvfrom(4096)
                # Drenar posibles paquetes acumulados durante el procesamiento previo
                self._drain_extra_packets()
                try:
                    payload = json.loads(data.decode("utf-8"))
                    return payload
                except Exception:
                    return {"event": "SESSION_READY"}
            return None
        except Exception as e:
            logger.warning(f"Aviso en espera de señal de vigilante: {e}")
            time.sleep(effective_timeout)
            return None

    def _drain_extra_packets(self) -> None:
        """Descarta pulsos duplicados acumulados en el buffer del socket."""
        if not self.sock:
            return
        while True:
            try:
                r, _, _ = select.select([self.sock], [], [], 0.0)
                if not r:
                    break
                self.sock.recvfrom(4096)
            except Exception:
                break

    def close(self) -> None:
        """Cierra el socket y libera el puerto."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


def send_watcher_signal(
    session_id: str,
    session_dir: str = "",
    host: str = DEFAULT_SIGNAL_HOST,
    port: int = DEFAULT_SIGNAL_PORT,
) -> bool:
    """
    Envía un pulso de señal UDP local al Watcher de forma no bloqueante (fire-and-forget).
    Retorna True si el datagrama fue emitido sin error.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = json.dumps({
            "event": "SESSION_READY",
            "sessionId": session_id,
            "sessionDir": session_dir,
            "timestamp": time.time(),
        }).encode("utf-8")
        sock.sendto(payload, (host, port))
        sock.close()
        return True
    except Exception:
        return False
