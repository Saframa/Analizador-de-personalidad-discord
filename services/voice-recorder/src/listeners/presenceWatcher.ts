import {
  Client,
  Events,
  VoiceState,
  ChannelType,
  VoiceBasedChannel,
} from 'discord.js';
import {
  joinVoiceChannel,
  VoiceConnection,
  VoiceConnectionStatus,
  entersState,
} from '@discordjs/voice';
import { config } from '../config.js';
import { SessionManager } from '../session/sessionManager.js';

export class PresenceWatcher {
  private client: Client;
  private sessionManager: SessionManager;
  private currentConnection: VoiceConnection | null = null;
  private currentChannelId: string | null = null;
  private leaveTimeout: NodeJS.Timeout | null = null;

  constructor(client: Client, sessionManager: SessionManager) {
    this.client = client;
    this.sessionManager = sessionManager;
    this.setupListeners();
  }

  private setupListeners(): void {
    this.client.on(Events.VoiceStateUpdate, (oldState: VoiceState, newState: VoiceState) => {
      this.handleVoiceStateUpdate(oldState, newState);
    });
  }

  /**
   * Procesa cualquier cambio en canales de voz dentro del servidor.
   */
  private async handleVoiceStateUpdate(oldState: VoiceState, newState: VoiceState): Promise<void> {
    const channel = newState.channel ?? oldState.channel;
    if (!channel || channel.type !== ChannelType.GuildVoice) {
      return;
    }

    // Si se especificó GUILD_ID en .env, filtrar solo ese servidor
    if (config.GUILD_ID && channel.guild.id !== config.GUILD_ID) {
      return;
    }

    const member = newState.member ?? oldState.member;
    const isBotSelf = member?.id === this.client.user?.id;

    // Si el bot fue desconectado externamente (ej. kickeado por un admin)
    if (isBotSelf && !newState.channelId && this.sessionManager.isRecording()) {
      console.warn('⚠️ [PresenceWatcher] El bot fue desconectado del canal de voz. Finalizando sesión de emergencia...');
      await this.cleanupAndEndSession();
      return;
    }

    // Contar usuarios humanos en el canal relevante
    const humanCount = channel.members.filter((m) => !m.user.bot).size;
    const isConnectedHere = this.currentChannelId === channel.id;

    // REGLA 1: Entrada automática (>= MIN_USERS_TO_RECORD en cualquier canal)
    if (humanCount >= config.MIN_USERS_TO_RECORD && !this.sessionManager.isRecording()) {
      this.cancelLeaveTimeout();
      await this.joinAndStartRecording(channel);
      return;
    }

    // REGLA 2: Actualización de participantes dentro de la sesión activa
    if (isConnectedHere && this.sessionManager.isRecording() && member && !member.user.bot) {
      if (newState.channelId === channel.id && oldState.channelId !== channel.id) {
        // Usuario entró al canal activo
        this.sessionManager.recordUserJoined(member.id, member.user.username, member.displayName);
      } else if (oldState.channelId === channel.id && newState.channelId !== channel.id) {
        // Usuario salió del canal activo
        this.sessionManager.recordUserLeft(member.id);
      }
    }

    // REGLA 3: Desconexión automática con Debounce (< MIN_USERS_TO_RECORD en canal activo)
    if (isConnectedHere && this.sessionManager.isRecording()) {
      if (humanCount < config.MIN_USERS_TO_RECORD) {
        this.scheduleGracefulLeave(channel.name);
      } else {
        // Si volvieron a entrar suficientes personas antes del timeout, cancelar la salida
        this.cancelLeaveTimeout();
      }
    }
  }

  /**
   * Conecta el bot al canal de voz e inicializa la sesión.
   */
  private async joinAndStartRecording(channel: VoiceBasedChannel): Promise<void> {
    try {
      console.log(`🚀 [PresenceWatcher] Detectados ${channel.members.filter(m => !m.user.bot).size} usuarios en '${channel.name}'. Conectando bot...`);

      const connection = joinVoiceChannel({
        channelId: channel.id,
        guildId: channel.guild.id,
        adapterCreator: channel.guild.voiceAdapterCreator,
        selfDeaf: false, // NO mutear recepción (necesario para capturar audio)
        selfMute: true,  // Silenciar micrófono del bot para no emitir ruido
      });

      // Esperar a que la conexión esté lista (máx 15 segundos)
      await entersState(connection, VoiceConnectionStatus.Ready, 15_000);
      console.log(`🔗 [PresenceWatcher] Conexión de voz establecida con éxito en '${channel.name}'.`);

      this.currentConnection = connection;
      this.currentChannelId = channel.id;

      // Iniciar la sesión de grabación y demultiplexación
      await this.sessionManager.startSession(channel, connection);

      // Manejar desconexiones inesperadas del socket de voz
      connection.on(VoiceConnectionStatus.Disconnected, async () => {
        try {
          await Promise.race([
            entersState(connection, VoiceConnectionStatus.Signalling, 5_000),
            entersState(connection, VoiceConnectionStatus.Connecting, 5_000),
          ]);
        } catch {
          console.warn('⚠️ [PresenceWatcher] Desconexión de voz permanente.');
          await this.cleanupAndEndSession();
        }
      });
    } catch (err) {
      console.error(`❌ [PresenceWatcher] Error al conectar al canal '${channel.name}':`, err);
      await this.cleanupAndEndSession();
    }
  }

  /**
   * Programa la desconexión con tiempo de gracia (debounce).
   */
  private scheduleGracefulLeave(channelName: string): void {
    if (this.leaveTimeout) {
      return;
    }

    console.log(`⏳ [PresenceWatcher] Menos de ${config.MIN_USERS_TO_RECORD} usuarios en '${channelName}'. Iniciando cuenta regresiva de ${config.DEBOUNCE_LEAVE_SECONDS}s para salir...`);

    this.leaveTimeout = setTimeout(async () => {
      console.log(`🚪 [PresenceWatcher] Tiempo de gracia finalizado. Saliendo de '${channelName}'...`);
      await this.cleanupAndEndSession();
    }, config.DEBOUNCE_LEAVE_SECONDS * 1000);
  }

  private cancelLeaveTimeout(): void {
    if (this.leaveTimeout) {
      console.log('🔄 [PresenceWatcher] Se reincorporaron usuarios al canal. Salida cancelada.');
      clearTimeout(this.leaveTimeout);
      this.leaveTimeout = null;
    }
  }

  /**
   * Finaliza la sesión actual y destruye la conexión de voz de Discord.
   */
  public async cleanupAndEndSession(): Promise<void> {
    this.cancelLeaveTimeout();

    if (this.sessionManager.isRecording()) {
      await this.sessionManager.endSession();
    }

    if (this.currentConnection) {
      try {
        this.currentConnection.destroy();
      } catch (e) {
        // Ignorar errores al destruir conexión ya cerrada
      }
      this.currentConnection = null;
      this.currentChannelId = null;
    }
  }
}
