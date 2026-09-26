import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  Client,
  Events,
  VoiceState,
  ChannelType,
  VoiceBasedChannel,
  PermissionFlagsBits,
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
  private isShuttingDown = false;
  private isManualOperation = false;
  private isManualConnected = false;
  private autoJoinPausedUntil = 0;
  private lastJoinAttempt = 0;

  constructor(client: Client, sessionManager: SessionManager) {
    this.client = client;
    this.sessionManager = sessionManager;
    this.setupListeners();
  }

  public setShuttingDown(): void {
    this.isShuttingDown = true;
    this.cancelLeaveTimeout();
  }

  private setupListeners(): void {
    this.client.on(Events.VoiceStateUpdate, (oldState: VoiceState, newState: VoiceState) => {
      this.handleVoiceStateUpdate(oldState, newState);
      this.saveChannelsCache();
    });
    this.client.on(Events.ChannelUpdate, () => {
      this.saveChannelsCache();
    });
    this.client.on(Events.ChannelCreate, () => {
      this.saveChannelsCache();
    });
    this.client.on(Events.ChannelDelete, () => {
      this.saveChannelsCache();
    });
  }

  /**
   * Limpia conexiones de voz fantasma que hayan quedado registradas en Discord
   * tras un cierre abrupto o reinicio del bot.
   */
  public async cleanupStaleVoiceStates(): Promise<void> {
    for (const guild of this.client.guilds.cache.values()) {
      if (config.GUILD_ID && guild.id !== config.GUILD_ID) continue;
      const me = guild.members.me;
      if (me?.voice.channelId) {
        console.log(`🧹 [PresenceWatcher] Estado de voz previo detectado en '${me.voice.channel?.name ?? me.voice.channelId}'. Forzando desconexión limpia...`);
        try {
          await me.voice.disconnect();
          await new Promise((resolve) => setTimeout(resolve, 800));
        } catch (err) {
          console.warn(`Aviso al limpiar voz previa:`, err);
        }
      }
    }
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
    if (this.isShuttingDown || this.isManualOperation) {
      return;
    }

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

    // Si el bot fue desconectado externamente (ej. kick manual en Discord)
    if (isBotSelf && !newState.channelId && this.sessionManager.isRecording()) {
      console.warn('⚠️ [PresenceWatcher] El bot fue desconectado externamente del canal de voz. Finalizando sesión...');
      await this.cleanupAndEndSession();
      return;
    }

    // Verificar si el bot ya está conectado con conexión activa en este canal
    const botVoiceChannelId = channel.guild.members.me?.voice.channelId;
    const isConnectedHere = botVoiceChannelId === channel.id && this.currentConnection !== null;

    // Si Discord cree que estamos en el canal pero no tenemos conexión de audio activa (estado fantasma)
    if (botVoiceChannelId === channel.id && !this.currentConnection && !this.isConnecting) {
      console.warn(`⚠️ [PresenceWatcher] Estado fantasma detectado en '${channel.name}'. Limpiando para reconexión limpia...`);
      try {
        await channel.guild.members.me?.voice.disconnect();
        await new Promise((resolve) => setTimeout(resolve, 500));
      } catch {}
    }

    // Contar usuarios humanos en el canal relevante
    const humanCount = channel.members.filter((m) => !m.user.bot).size;

    // Si estábamos en modo manual y ya se unieron usuarios suficientes, transferir a modo automático
    if (isConnectedHere && this.isManualConnected && humanCount >= config.MIN_USERS_TO_RECORD) {
      this.isManualConnected = false;
    }

    // REGLA 1: Entrada automática (>= MIN_USERS_TO_RECORD en cualquier canal)
    const autoJoinBlocked = Date.now() < this.autoJoinPausedUntil;
    if (
      humanCount >= config.MIN_USERS_TO_RECORD &&
      !this.sessionManager.isRecording() &&
      !this.isConnecting &&
      !isConnectedHere &&
      !autoJoinBlocked
    ) {
      this.cancelLeaveTimeout();
      await this.joinAndStartRecording(channel, false);
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
        const graceSeconds = this.isManualConnected ? 120 : config.DEBOUNCE_LEAVE_SECONDS;
        this.scheduleGracefulLeave(channel.name, graceSeconds);
      } else {
        // Si hay suficientes personas, cancelar cualquier salida pendiente
        this.cancelLeaveTimeout();
      }
    }
  }

  /**
   * Conecta el bot al canal de voz e inicializa la sesión.
   */
  private async joinAndStartRecording(channel: VoiceBasedChannel, isManual: boolean = false): Promise<boolean> {
    if (this.isShuttingDown) {
      return false;
    }

    if (this.isConnecting) {
      console.warn(`⏳ [PresenceWatcher] Ya hay una conexión en proceso para un canal.`);
      return false;
    }

    if (this.sessionManager.isRecording() && this.currentChannelId === channel.id) {
      console.log(`ℹ️ [PresenceWatcher] Ya está grabando activamente en '${channel.name}'.`);
      return true;
    }

    const now = Date.now();
    if (!isManual && (now - this.lastJoinAttempt < 3000)) {
      console.log(`⏳ [PresenceWatcher] Intervalo de seguridad activo. Esperando antes de reconectar a '${channel.name}'...`);
      return false;
    }
    this.lastJoinAttempt = now;
    this.isConnecting = true;

    let connection: VoiceConnection | null = null;
    try {
      const humanCount = channel.members.filter((m) => !m.user.bot).size;
      console.log(`🚀 [PresenceWatcher] Conectando bot a '${channel.name}' (${humanCount} usuarios humanos)...`);

      connection = joinVoiceChannel({
        channelId: channel.id,
        guildId: channel.guild.id,
        adapterCreator: channel.guild.voiceAdapterCreator,
        selfDeaf: false,
        selfMute: true,
        debug: true,
      });

      connection.on('stateChange', async (oldState, newState) => {
        console.log(`📡 [VoiceConnection] ${channel.name}: ${oldState.status} -> ${newState.status}`, (newState as any).reason ?? '', (newState as any).closeCode ?? '');
        
        // Si estamos ejecutando una transición manual, ignorar desconexiones previas
        if (this.isManualOperation) {
          return;
        }

        if (newState.status === VoiceConnectionStatus.Disconnected) {
          const closeCode = (newState as any).closeCode;
          if (closeCode === 4014 || closeCode === 4006) {
            console.log(`ℹ️ [VoiceConnection] Desconexión definitiva detectada (código ${closeCode}). Finalizando sesión...`);
            await this.cleanupAndEndSession();
          } else {
            try {
              await Promise.race([
                entersState(connection!, VoiceConnectionStatus.Signalling, 5_000),
                entersState(connection!, VoiceConnectionStatus.Connecting, 5_000),
              ]);
            } catch {
              console.warn('⚠️ [VoiceConnection] No se pudo recuperar el socket de voz. Finalizando sesión...');
              await this.cleanupAndEndSession();
            }
          }
        }
      });

      connection.on('debug', (msg) => {
        console.log(`🔍 [Voice Debug] ${msg}`);
      });

      connection.on('error', (err) => {
        console.error(`❌ [Voice Error]`, err);
      });

      // Esperar a que la conexión esté en estado Ready
      await entersState(connection!, VoiceConnectionStatus.Ready, 20_000);
      console.log(`🔗 [PresenceWatcher] Conexión de voz establecida con éxito en '${channel.name}'.`);

      this.currentConnection = connection;
      this.currentChannelId = channel.id;
      this.isManualConnected = isManual;

      // Iniciar la sesión de grabación y demultiplexación
      await this.sessionManager.startSession(channel, connection!);
      return true;
    } catch (err) {
      console.error(`❌ [PresenceWatcher] Error al conectar al canal '${channel.name}':`, err);
      try {
        connection?.removeAllListeners();
        connection?.destroy();
      } catch {}
      await this.cleanupAndEndSession();
      return false;
    } finally {
      this.isConnecting = false;
    }
  }

  /**
   * Programa la desconexión con tiempo de gracia (debounce).
   */
  private scheduleGracefulLeave(channelName: string, seconds: number = config.DEBOUNCE_LEAVE_SECONDS): void {
    if (this.leaveTimeout) {
      return;
    }

    console.log(`⏳ [PresenceWatcher] Menos de ${config.MIN_USERS_TO_RECORD} usuarios en '${channelName}'. Esperando ${seconds}s antes de desconectar...`);

    this.leaveTimeout = setTimeout(async () => {
      console.log(`🚪 [PresenceWatcher] Tiempo de gracia finalizado. Saliendo de '${channelName}'...`);
      await this.cleanupAndEndSession();
      this.saveChannelsCache();
    }, seconds * 1000);
  }

  private cancelLeaveTimeout(): void {
    if (this.leaveTimeout) {
      console.log('🔄 [PresenceWatcher] Se canceló el tiempo de salida.');
      clearTimeout(this.leaveTimeout);
      this.leaveTimeout = null;
    }
  }

  /**
   * Finaliza la sesión actual y destruye la conexión de voz de Discord.
   */
  public async cleanupAndEndSession(): Promise<void> {
    this.cancelLeaveTimeout();
    this.isManualConnected = false;

    if (this.sessionManager.isRecording()) {
      await this.sessionManager.endSession();
    }

    if (this.currentConnection) {
      try {
        this.currentConnection.removeAllListeners();
        this.currentConnection.destroy();
      } catch (e) {
        // Ignorar si ya estaba destruida
      }
      this.currentConnection = null;
      this.currentChannelId = null;
    }

    // Asegurar desconexión explícita de todos los canales de voz en Discord Gateway
    for (const guild of this.client.guilds.cache.values()) {
      if (guild.members.me?.voice.channelId) {
        try {
          await guild.members.me.voice.disconnect();
        } catch (e) {
          // Ignorar si ya estaba desconectado
        }
      }
    }
  }

  /**
   * Obtiene la información estructurada de todos los canales de voz en los servidores donde está el bot.
   */
  public getChannelsInfo(): {
    botUser: { id: string; tag: string } | null;
    connectedChannelId: string | null;
    isRecording: boolean;
    minUsersRequired: number;
    guilds: Array<{
      id: string;
      name: string;
      iconUrl: string | null;
      channels: Array<{
        id: string;
        name: string;
        category: string | null;
        userLimit: number;
        humanCount: number;
        botCount: number;
        isConnected: boolean;
        canJoin: boolean;
        meetsConditions: boolean;
        members: Array<{
          id: string;
          username: string;
          displayName: string;
          isBot: boolean;
          avatarUrl: string | null;
          selfMute: boolean;
          selfDeaf: boolean;
        }>;
      }>;
    }>;
  } {
    const guildsData = [];

    for (const guild of this.client.guilds.cache.values()) {
      if (config.GUILD_ID && guild.id !== config.GUILD_ID) continue;

      const channelsData = [];
      const me = guild.members.me;

      const voiceChannels = guild.channels.cache
        .filter((c) => c.type === ChannelType.GuildVoice)
        .sort((a, b) => a.position - b.position);

      for (const channel of voiceChannels.values()) {
        const vChannel = channel as VoiceBasedChannel;

        let canJoin = true;
        if (me) {
          const perms = vChannel.permissionsFor(me);
          if (perms && (!perms.has(PermissionFlagsBits.ViewChannel) || !perms.has(PermissionFlagsBits.Connect))) {
            canJoin = false;
          }
        }
        if (vChannel.userLimit > 0 && vChannel.members.size >= vChannel.userLimit && vChannel.id !== this.currentChannelId) {
          canJoin = false;
        }

        const membersList = [];
        let humanCount = 0;
        let botCount = 0;

        for (const m of vChannel.members.values()) {
          if (m.user.bot) {
            botCount++;
          } else {
            humanCount++;
          }
          membersList.push({
            id: m.id,
            username: m.user.username,
            displayName: m.displayName,
            isBot: m.user.bot,
            avatarUrl: m.user.displayAvatarURL({ size: 64 }),
            selfMute: m.voice.selfMute ?? false,
            selfDeaf: m.voice.selfDeaf ?? false,
          });
        }

        const isConnected = vChannel.id === this.currentChannelId && this.sessionManager.isRecording();
        const meetsConditions = humanCount >= config.MIN_USERS_TO_RECORD;

        channelsData.push({
          id: vChannel.id,
          name: vChannel.name,
          category: vChannel.parent?.name ?? null,
          userLimit: vChannel.userLimit,
          humanCount,
          botCount,
          isConnected,
          canJoin,
          meetsConditions,
          members: membersList,
        });
      }

      guildsData.push({
        id: guild.id,
        name: guild.name,
        iconUrl: guild.iconURL({ size: 128 }),
        channels: channelsData,
      });
    }

    return {
      botUser: this.client.user ? { id: this.client.user.id, tag: this.client.user.tag } : null,
      connectedChannelId: this.currentChannelId,
      isRecording: this.sessionManager.isRecording(),
      minUsersRequired: config.MIN_USERS_TO_RECORD,
      guilds: guildsData,
    };
  }

  /**
   * Guarda una copia local en disco de los canales y su estado para lectura instantánea.
   */
  public saveChannelsCache(): void {
    try {
      const data = this.getChannelsInfo();
      const filePath = path.join(config.STORAGE_DIR, '.discord_channels.json');
      fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    } catch {
      // Ignorar fallas silenciosas de caché
    }
  }

  /**
   * Conecta manualmente el bot al canal indicado.
   */
  public async manualJoin(channelId: string): Promise<{ success: boolean; message: string }> {
    if (this.isShuttingDown) {
      return { success: false, message: 'El bot se encuentra en proceso de apagado.' };
    }

    let targetChannel: VoiceBasedChannel | null = null;
    for (const guild of this.client.guilds.cache.values()) {
      const ch = guild.channels.cache.get(channelId);
      if (ch && ch.type === ChannelType.GuildVoice) {
        targetChannel = ch as VoiceBasedChannel;
        break;
      }
    }

    if (!targetChannel) {
      return { success: false, message: `Canal de voz '${channelId}' no encontrado en los servidores del bot.` };
    }

    // Verificar permisos
    const me = targetChannel.guild.members.me;
    if (me) {
      const perms = targetChannel.permissionsFor(me);
      if (perms && !perms.has(PermissionFlagsBits.Connect)) {
        return { success: false, message: `El bot no tiene permisos para conectarse a '${targetChannel.name}'.` };
      }
    }

    if (this.currentChannelId === channelId && this.sessionManager.isRecording()) {
      return { success: true, message: `El bot ya se encuentra grabando en '${targetChannel.name}'.` };
    }

    console.log(`🎯 [PresenceWatcher] Transición manual hacia '${targetChannel.name}' iniciada...`);
    this.isManualOperation = true;
    this.cancelLeaveTimeout();

    // Pausar auto-join por 25s para que no interfiera ningún evento de presencia
    this.autoJoinPausedUntil = Date.now() + 25000;

    try {
      // 1. Si ya estamos en otro canal, desconectar y cerrar sesión limpiamente
      if (this.sessionManager.isRecording()) {
        console.log(`⏹️ [PresenceWatcher] Cerrando sesión previa antes de mover bot...`);
        await this.sessionManager.endSession();
      }

      if (this.currentConnection) {
        console.log(`🔌 [PresenceWatcher] Destruyendo conexión anterior...`);
        try {
          this.currentConnection.removeAllListeners();
          this.currentConnection.destroy();
        } catch {}
        this.currentConnection = null;
        this.currentChannelId = null;
      }

      // Desconexión limpia del socket de Discord si quedó asociado
      for (const guild of this.client.guilds.cache.values()) {
        if (guild.members.me?.voice.channelId) {
          try {
            await guild.members.me.voice.disconnect();
          } catch {}
        }
      }

      // Pausa breve para que Discord Gateway procese la salida del canal previo
      await new Promise((r) => setTimeout(r, 700));

      // 2. Conectar al nuevo canal forzando bypass de throttle
      const connected = await this.joinAndStartRecording(targetChannel, true);
      if (!connected) {
        return {
          success: false,
          message: `No se pudo conectar a '${targetChannel.name}'. Verifica permisos o estado del canal.`,
        };
      }

      this.saveChannelsCache();
      return {
        success: true,
        message: `Bot conectado exitosamente al canal '${targetChannel.name}'. Grabación iniciada.`,
      };
    } catch (err: any) {
      console.error(`❌ [PresenceWatcher] Error en manualJoin:`, err);
      return {
        success: false,
        message: `Fallo al unir al canal: ${err?.message || err}`,
      };
    } finally {
      this.isManualOperation = false;
    }
  }

  /**
   * Desconecta manualmente el bot del canal de voz.
   */
  public async manualLeave(): Promise<{ success: boolean; message: string }> {
    if (!this.sessionManager.isRecording() && !this.currentConnection) {
      return { success: true, message: 'El bot no está en ninguna llamada.' };
    }

    console.log(`👋 [PresenceWatcher] Desconexión manual solicitada.`);
    this.isManualOperation = true;
    // Pausar auto-join por 45s para que no se reconecte inmediatamente al mismo canal
    this.autoJoinPausedUntil = Date.now() + 45000;
    this.cancelLeaveTimeout();

    try {
      await this.cleanupAndEndSession();
      this.saveChannelsCache();
      return {
        success: true,
        message: 'Bot desconectado correctamente del canal de voz. Escucha automática pausada temporalmente.',
      };
    } finally {
      this.isManualOperation = false;
    }
  }
}
