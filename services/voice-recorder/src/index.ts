import { Client, GatewayIntentBits, Events } from 'discord.js';
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

client.once(Events.ClientReady, (readyClient) => {
  console.log(`✅ Bot conectado exitosamente como: ${readyClient.user.tag}`);
  console.log(`👀 Vigilando canales de voz (Entrada: >= ${config.MIN_USERS_TO_RECORD} personas, Debounce: ${config.DEBOUNCE_LEAVE_SECONDS}s)`);
  console.log(`📁 Directorio de almacenamiento: ${config.STORAGE_DIR}`);
});

// Manejo de cierre elegante (Ctrl+C / SIGINT / SIGTERM)
const handleShutdown = async (signal: string) => {
  console.log(`\n🛑 Recibida señal ${signal}. Finalizando grabaciones activas de forma segura...`);
  try {
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

client.login(config.DISCORD_TOKEN).catch((err) => {
  console.error('❌ Error fatal al conectar con la API de Discord:');
  console.error(err.message);
  process.exit(1);
});
