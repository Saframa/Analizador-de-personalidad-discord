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
  private isConnecting = false;

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
   * Escanea los canales al iniciar el bot para unirse si ya hay personas hablando.
   */
  public async scanInitialChannels(): Promise<void> {
    for (const guild of this.client.guilds.cache.values()) {
      if (config.GUILD_ID && guild.id !== config.GUILD_ID) continue;

      for (const channel of guild.channels.cache.values()) {
        if (channel.type === ChannelType.GuildVoice) {
          const humanCount = channel.members.filter((m) => !m.user.bot).size;
          if (humanCount >= config.MIN_USERS_TO_RECORD && !this.sessionManager.isRecording() && !this.isConnecting) {
            console.log(`🔍 [PresenceWatcher] Canal activo detectado al iniciar: '${channel.name}' con ${humanCount} usuarios.`);
            await this.joinAndStartRecording(channel);
            return;
          }
        }
      }
    }
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

    // Si el bot fue desconectado externamente
    if (isBotSelf && !newState.channelId && this.sessionManager.isRecording()) {
      console.warn('⚠️ [PresenceWatcher] El bot fue desconectado del canal de voz. Finalizando sesión...');
      await this.cleanupAndEndSession();
      return;
    }

    // Verificar si el bot ya está conectado en este canal
    const botVoiceChannelId = channel.guild.members.me?.voice.channelId;
    const isConnectedHere = botVoiceChannelId === channel.id;

    // Contar usuarios humanos en el canal relevante
    const humanCount = channel.members.filter((m) => !m.user.bot).size;

    // REGLA 1: Entrada automática (>= MIN_USERS_TO_RECORD en cualquier canal)
    // Protegido con mutex `isConnecting` y comprobación de canal actual
    if (
      humanCount >= config.MIN_USERS_TO_RECORD &&
      !this.sessionManager.isRecording() &&
      !this.isConnecting &&
      !isConnectedHere
    ) {
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
        // Si hay suficientes personas, cancelar cualquier salida pendiente
        this.cancelLeaveTimeout();
      }
    }
  }

  /**
   * Conecta el bot al canal de voz e inicializa la sesión.
   */
  private async joinAndStartRecording(channel: VoiceBasedChannel): Promise<void> {
    if (this.isConnecting || this.sessionManager.isRecording()) {
      return;
    }

    this.isConnecting = true;

    try {
      const humanCount = channel.members.filter((m) => !m.user.bot).size;
      console.log(`🚀 [PresenceWatcher] Detectados ${humanCount} usuarios en '${channel.name}'. Conectando bot...`);

      const connection = joinVoiceChannel({
        channelId: channel.id,
        guildId: channel.guild.id,
        adapterCreator: channel.guild.voiceAdapterCreator,
        selfDeaf: false,
        selfMute: true,
        debug: true,
      });

      connection.on('stateChange', (oldState, newState) => {
        console.log(`📡 [VoiceConnection] ${channel.name}: ${oldState.status} -> ${newState.status}`, (newState as any).reason ?? '', (newState as any).closeCode ?? '');
      });

      connection.on('debug', (msg) => {
        console.log(`🔍 [Voice Debug] ${msg}`);
      });

      connection.on('error', (err) => {
        console.error(`❌ [Voice Error]`, err);
      });

      // Esperar a que la conexión esté en estado Ready
      await entersState(connection, VoiceConnectionStatus.Ready, 20_000);
      console.log(`🔗 [PresenceWatcher] Conexión de voz establecida con éxito en '${channel.name}'.`);

      this.currentConnection = connection;
      this.currentChannelId = channel.id;

      // Iniciar la sesión de grabación y demultiplexación
      await this.sessionManager.startSession(channel, connection);

      // Manejar desconexiones del socket de voz
      connection.on(VoiceConnectionStatus.Disconnected, async () => {
        try {
          await Promise.race([
            entersState(connection, VoiceConnectionStatus.Signalling, 5_000),
            entersState(connection, VoiceConnectionStatus.Connecting, 5_000),
          ]);
        } catch {
          console.warn('⚠️ [PresenceWatcher] Desconexión de voz detectada.');
          await this.cleanupAndEndSession();
        }
      });
    } catch (err) {
      console.error(`❌ [PresenceWatcher] Error al conectar al canal '${channel.name}':`, err);
      await this.cleanupAndEndSession();
    } finally {
      this.isConnecting = false;
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
        // Ignorar si ya estaba destruida
      }
      this.currentConnection = null;
      this.currentChannelId = null;
    }
  }
}
