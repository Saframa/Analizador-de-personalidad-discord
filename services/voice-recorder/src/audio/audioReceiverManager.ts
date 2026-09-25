import { EndBehaviorType, VoiceReceiver } from '@discordjs/voice';
import prism from 'prism-media';
import * as path from 'node:path';
import { WavFileWriter } from './wavWriter.js';
import { AudioFileInfo } from '../contracts/session.js';

export interface UserAudioTrack {
  userId: string;
  filePath: string;
  relativeFileName: string;
  writer: WavFileWriter;
  isSubscribed: boolean;
}

/**
 * Administra la demultiplexación de streams de audio por usuario en Discord.
 * Canaliza los paquetes Opus de cada participante hacia su respectivo archivo WAV mono a 48kHz.
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
      const relativeFileName = `audio/${userId}.wav`;
      const absoluteFilePath = path.join(this.sessionAudioDir, `${userId}.wav`);
      const writer = new WavFileWriter(absoluteFilePath, {
        sampleRate: 48000,
        channels: 1,
        bitsPerSample: 16,
      });

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

    // Suscribirse al stream Opus del usuario
    const opusStream = this.receiver.subscribe(userId, {
      end: {
        behavior: EndBehaviorType.AfterSilence,
        duration: 1200, // Cierra el stream individual tras 1.2s de silencio continuo
      },
    });

    // Decodificador Opus -> PCM 16-bit Mono a 48.000 Hz
    const opusDecoder = new prism.opus.Decoder({
      rate: 48000,
      channels: 1,
      frameSize: 960,
    });

    opusStream
      .pipe(opusDecoder)
      .pipe(track.writer, { end: false }); // Mantener el writer abierto entre pausas de habla

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

    opusDecoder.on('error', (err: Error) => {
      console.error(`[AudioReceiver] Error decodificando Opus para usuario ${userId}:`, err);
    });
  }

  /**
   * Finaliza todos los streams de audio abiertos y actualiza los encabezados WAV.
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
            format: 'wav',
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
