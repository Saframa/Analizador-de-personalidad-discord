import { VoiceBasedChannel } from 'discord.js';
import { VoiceConnection } from '@discordjs/voice';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { AudioReceiverManager } from '../audio/audioReceiverManager.js';
import {
  writeSessionMetadataAtomic,
  Participant,
  SessionMetadata,
  AudioFileInfo,
} from '../contracts/session.js';
import { config } from '../config.js';

export class SessionManager {
  private currentSessionId: string | null = null;
  private currentSessionDir: string | null = null;
  private startedAt: Date | null = null;
  private channel: VoiceBasedChannel | null = null;
  private audioManager: AudioReceiverManager | null = null;
  private participantsMap: Map<string, Participant> = new Map();

  /**
   * Genera el ID de sesión en formato estricto YYYY-MM-DD_HH-mm-ss
   */
  public static generateSessionId(date: Date = new Date()): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    const yyyy = date.getFullYear();
    const mm = pad(date.getMonth() + 1);
    const dd = pad(date.getDate());
    const hh = pad(date.getHours());
    const min = pad(date.getMinutes());
    const ss = pad(date.getSeconds());
    return `${yyyy}-${mm}-${dd}_${hh}-${min}-${ss}`;
  }

  public isRecording(): boolean {
    return this.currentSessionId !== null;
  }

  public getSessionId(): string | null {
    return this.currentSessionId;
  }

  /**
   * Inicia una nueva sesión de grabación para un canal de voz dado.
   */
  public async startSession(channel: VoiceBasedChannel, connection: VoiceConnection): Promise<string> {
    if (this.isRecording()) {
      console.warn(`[SessionManager] Ya existe una sesión activa: ${this.currentSessionId}`);
      return this.currentSessionId!;
    }

    const now = new Date();
    const sessionId = SessionManager.generateSessionId(now);
    const rawSessionsDir = path.join(config.STORAGE_DIR, 'raw_sessions');
    const sessionDir = path.join(rawSessionsDir, sessionId);
    const audioDir = path.join(sessionDir, 'audio');

    fs.mkdirSync(audioDir, { recursive: true });

    this.currentSessionId = sessionId;
    this.currentSessionDir = sessionDir;
    this.startedAt = now;
    this.channel = channel;
    this.participantsMap.clear();

    // Registrar participantes humanos presentes en el canal
    for (const [, member] of channel.members) {
      if (member.user.bot) continue;
      this.participantsMap.set(member.id, {
        user_id: member.id,
        username: member.user.username,
        display_name: member.displayName,
        joined_at: now.toISOString(),
        left_at: null,
      });
    }

    // Inicializar el receptor de audio
    this.audioManager = new AudioReceiverManager(connection.receiver, audioDir);

    // Pre-suscribir a todos los miembros presentes para no perder sílabas iniciales
    for (const [userId] of this.participantsMap) {
      this.audioManager.subscribeUser(userId);
    }

    console.log(`🎙️ [SessionManager] Sesión iniciada: ${sessionId} en canal '${channel.name}' con ${this.participantsMap.size} participantes.`);
    return sessionId;
  }

  /**
   * Registra el ingreso de un participante durante la sesión.
   */
  public recordUserJoined(userId: string, username: string, displayName: string): void {
    if (!this.isRecording()) return;

    const existing = this.participantsMap.get(userId);
    if (!existing) {
      this.participantsMap.set(userId, {
        user_id: userId,
        username,
        display_name: displayName,
        joined_at: new Date().toISOString(),
        left_at: null,
      });
    }
  }

  /**
   * Registra la salida de un participante durante la sesión.
   */
  public recordUserLeft(userId: string): void {
    if (!this.isRecording()) return;

    const participant = this.participantsMap.get(userId);
    if (participant && !participant.left_at) {
      participant.left_at = new Date().toISOString();
    }
  }

  /**
   * Finaliza la sesión actual, cierra los archivos de audio y persiste session_metadata.json.
   */
  public async endSession(): Promise<SessionMetadata | null> {
    if (!this.isRecording() || !this.startedAt || !this.currentSessionDir || !this.channel || !this.audioManager) {
      console.warn('[SessionManager] Intento de finalizar una sesión no existente.');
      return null;
    }

    const endedAt = new Date();
    const durationSeconds = Math.max(0, (endedAt.getTime() - this.startedAt.getTime()) / 1000);
    const sessionId = this.currentSessionId!;
    const sessionDir = this.currentSessionDir;

    console.log(`⏹️ [SessionManager] Cerrando sesión ${sessionId}... Duración: ${durationSeconds.toFixed(1)}s`);

    // Cerrar streams de audio y obtener metadatos de archivos
    const audioFilesMap = await this.audioManager.closeAll();
    const audioFilesObject: Record<string, AudioFileInfo> = {};
    for (const [userId, info] of audioFilesMap.entries()) {
      audioFilesObject[userId] = info;
    }

    // Marcar salida para quienes no salieron antes
    for (const participant of this.participantsMap.values()) {
      if (!participant.left_at) {
        participant.left_at = endedAt.toISOString();
      }
    }

    const participantsArray = Array.from(this.participantsMap.values());

    // Construir metadata conforme al contrato A
    const metadataPayload = {
      version: '1.0.0' as const,
      session_id: sessionId,
      guild_id: this.channel.guild.id,
      channel_id: this.channel.id,
      channel_name: this.channel.name,
      started_at: this.startedAt.toISOString(),
      ended_at: endedAt.toISOString(),
      duration_seconds: Math.round(durationSeconds * 100) / 100,
      participants: participantsArray.length > 0 ? participantsArray : [
        {
          user_id: 'unknown',
          username: 'unknown',
          display_name: 'Unknown',
          joined_at: this.startedAt.toISOString(),
          left_at: endedAt.toISOString(),
        }
      ],
      audio_files: audioFilesObject,
    };

    const metadataFilePath = path.join(sessionDir, 'session_metadata.json');
    const validatedMetadata = writeSessionMetadataAtomic(metadataFilePath, metadataPayload);

    console.log(`✅ [SessionManager] Metadata guardada atómicamente en: ${metadataFilePath}`);

    // Limpiar estado
    this.currentSessionId = null;
    this.currentSessionDir = null;
    this.startedAt = null;
    this.channel = null;
    this.audioManager = null;
    this.participantsMap.clear();

    return validatedMetadata;
  }
}
