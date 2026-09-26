import * as fs from 'node:fs';
import * as path from 'node:path';
import { Client, GatewayIntentBits, Events, ActivityType } from 'discord.js';
import { config } from './config.js';
import { SessionManager } from './session/sessionManager.js';
import { PresenceWatcher } from './listeners/presenceWatcher.js';

console.log('====================================================');
console.log('🤖 Discord Voice Recorder Service (Fase 1)');
console.log('====================================================');

if (!config.DISCORD_TOKEN) {
  console.error('❌ ERROR: DISCORD_TOKEN no configurado en el archivo .env');
  console.error('   Por favor, copia .env.example a .env y define tu token.');
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates,
    GatewayIntentBits.GuildMembers,
  ],
});

const sessionManager = new SessionManager();
const presenceWatcher = new PresenceWatcher(client, sessionManager);

client.once(Events.ClientReady, async (readyClient) => {
  console.log(`✅ Bot conectado exitosamente como: ${readyClient.user.tag}`);
  console.log(`👀 Vigilando canales de voz (Entrada: >= ${config.MIN_USERS_TO_RECORD} personas, Debounce: ${config.DEBOUNCE_LEAVE_SECONDS}s)`);
  console.log(`⏱️  Rotación de bloques continuos: cada ${config.ROTATION_INTERVAL_MINUTES} minutos (Rolling Sessions)`);
  console.log(`📁 Directorio de almacenamiento: ${config.STORAGE_DIR}`);

  // Asegurar estado 'online' verde en Discord para evitar indicador amarillo de inactividad
  client.user?.setPresence({
    status: 'online',
    activities: [{ name: 'grabando llamadas', type: ActivityType.Custom }],
  });

  // Limpiar cualquier estado residual que haya quedado en Discord antes de escanear
  await presenceWatcher.cleanupStaleVoiceStates();

  // Escanear si ya hay canales con gente hablando al momento de iniciar
  await presenceWatcher.scanInitialChannels();
});

// Vigilante de archivo de parada suave (.recorder_stop) para Windows y control por API
const stopFilePath = path.join(config.STORAGE_DIR, '.recorder_stop');
if (fs.existsSync(stopFilePath)) {
  try {
    fs.unlinkSync(stopFilePath);
  } catch {}
}

const stopWatcherInterval = setInterval(async () => {
  if (fs.existsSync(stopFilePath)) {
    clearInterval(stopWatcherInterval);
    try {
      fs.unlinkSync(stopFilePath);
    } catch {}
    console.log('🛑 [VoiceRecorder] Señal de parada (.recorder_stop) recibida. Apagando limpiamente...');
    await handleShutdown('API_STOP');
  }
}, 300);

// Manejo de cierre elegante (Ctrl+C / SIGINT / SIGTERM / API_STOP)
const handleShutdown = async (signal: string) => {
  console.log(`\n🛑 Recibida señal ${signal}. Finalizando grabaciones activas de forma segura...`);
  try {
    presenceWatcher.setShuttingDown();
    client.removeAllListeners(Events.VoiceStateUpdate);
    await presenceWatcher.cleanupAndEndSession();
    client.destroy();
    console.log('👋 Servicio detenido correctamente.');
    process.exit(0);
  } catch (err) {
    console.error('❌ Error durante el apagado:', err);
    process.exit(1);
  }
};

process.on('SIGINT', () => handleShutdown('SIGINT'));
process.on('SIGTERM', () => handleShutdown('SIGTERM'));

// Prevención de caídas silenciosas por errores de socket o promesas no capturadas
process.on('uncaughtException', (err) => {
  console.error('🚨 [VoiceRecorder] Excepción no capturada capturada por guardián:', err);
});

process.on('unhandledRejection', (reason) => {
  console.error('⚠️ [VoiceRecorder] Promesa rechazada no manejada:', reason);
});

client.login(config.DISCORD_TOKEN).catch((err) => {
  console.error('❌ Error fatal al conectar con la API de Discord:');
  console.error(err.message);
  process.exit(1);
});
