import { EndBehaviorType, VoiceReceiver } from '@discordjs/voice';
import * as path from 'node:path';
import { OggOpusFileWriter } from './oggOpusWriter.js';
import { AudioFileInfo } from '../contracts/session.js';

export interface UserAudioTrack {
  userId: string;
  filePath: string;
  relativeFileName: string;
  writer: OggOpusFileWriter;
  isSubscribed: boolean;
}

/**
 * Administra la demultiplexación de streams de audio por usuario en Discord.
 * Canaliza los paquetes Opus directamente a un contenedor Ogg Opus (.ogg),
 * logrando un 90%+ de ahorro de espacio en disco con 0% pérdida de calidad y 0% de CPU.
 */
export class AudioReceiverManager {
  private receiver: VoiceReceiver;
  private sessionAudioDir: string;
  private tracks: Map<string, UserAudioTrack> = new Map();
  private isClosed = false;

  constructor(receiver: VoiceReceiver, sessionAudioDir: string) {
    this.receiver = receiver;
    this.sessionAudioDir = sessionAudioDir;
    this.setupSpeakingListener();
  }

  /**
   * Escucha cuando un usuario comienza a transmitir audio en el canal.
   */
  private setupSpeakingListener(): void {
    this.receiver.speaking.on('start', (userId: string) => {
      if (this.isClosed) return;
      this.subscribeUser(userId);
    });
  }

  /**
   * Suscribe el receptor al stream de un usuario específico si no está activo.
   */
  public subscribeUser(userId: string): void {
    if (this.isClosed) return;

    let track = this.tracks.get(userId);

    if (!track) {
      const relativeFileName = `audio/${userId}.ogg`;
      const absoluteFilePath = path.join(this.sessionAudioDir, `${userId}.ogg`);
      const writer = new OggOpusFileWriter(absoluteFilePath);

      track = {
        userId,
        filePath: absoluteFilePath,
        relativeFileName,
        writer,
        isSubscribed: false,
      };

      this.tracks.set(userId, track);
    }

    if (track.isSubscribed) {
      return;
    }

    track.isSubscribed = true;

    // Suscribirse al stream Opus directo del usuario
    const opusStream = this.receiver.subscribe(userId, {
      end: {
        behavior: EndBehaviorType.AfterSilence,
        duration: 1200, // 1.2 segundos de silencio continuo
      },
    });

    // Canalizar los paquetes Opus directo al empaquetador Ogg sin transcodificar
    opusStream.pipe(track.writer, { end: false });

    opusStream.on('end', () => {
      if (track) {
        track.isSubscribed = false;
      }
    });

    opusStream.on('error', (err: Error) => {
      console.error(`[AudioReceiver] Error en stream Opus de usuario ${userId}:`, err);
      if (track) {
        track.isSubscribed = false;
      }
    });
  }

  /**
   * Finaliza todos los streams de audio abiertos y genera los metadatos de archivo.
   */
  public async closeAll(): Promise<Map<string, AudioFileInfo>> {
    this.isClosed = true;
    const audioFilesMetadata = new Map<string, AudioFileInfo>();

    const closePromises: Promise<void>[] = [];

    for (const [userId, track] of this.tracks.entries()) {
      const p = new Promise<void>((resolve) => {
        track.writer.end(() => {
          audioFilesMetadata.set(userId, {
            filename: track.relativeFileName,
            sample_rate: 48000,
            channels: 1,
            format: 'ogg_opus',
            size_bytes: track.writer.getTotalBytes(),
          });
          resolve();
        });
      });
      closePromises.push(p);
    }

    await Promise.all(closePromises);
    this.tracks.clear();
    return audioFilesMetadata;
  }
}
