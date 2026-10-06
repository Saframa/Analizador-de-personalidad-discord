import dgram from 'node:dgram';

const WATCHER_SIGNAL_PORT = 5056;
const WATCHER_SIGNAL_HOST = '127.0.0.1';

/**
 * Emite un pulso de señal UDP local al Watcher de IA para despertarlo
 * en 0 milisegundos cuando una sesión de audio acaba de ser guardada.
 * Si el Watcher no está en ejecución, el datagrama se descarta sin bloquear ni generar errores.
 */
export function notifyWatcherSessionReady(sessionId: string, sessionDir: string): void {
  try {
    const payload = JSON.stringify({
      event: 'SESSION_READY',
      sessionId,
      sessionDir,
      timestamp: Date.now(),
    });

    const message = Buffer.from(payload, 'utf-8');
    const client = dgram.createSocket('udp4');

    client.send(message, 0, message.length, WATCHER_SIGNAL_PORT, WATCHER_SIGNAL_HOST, (err) => {
      try {
        client.close();
      } catch {}
      if (!err) {
        console.log(`⚡ [WatcherNotifier] Señal enviada al Watcher para despertar procesamiento de '${sessionId}' (0 ms).`);
      }
    });
  } catch (err) {
    // Falla silenciosa: si el puerto no está disponible o el socket falla,
    // el sondeo periódico de respaldo del Watcher procesará la sesión de todos modos.
  }
}
