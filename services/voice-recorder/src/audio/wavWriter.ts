import * as fs from 'node:fs';
import * as path from 'node:path';
import { Writable } from 'node:stream';

export interface WavWriterOptions {
  sampleRate?: number;
  channels?: number;
  bitsPerSample?: number;
}

/**
 * Genera el encabezado RIFF estándar de 44 bytes para audio PCM sin compresión.
 */
export function createWavHeader(
  dataLength: number,
  sampleRate = 48000,
  numChannels = 1,
  bitsPerSample = 16
): Buffer {
  const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const buffer = Buffer.alloc(44);

  // RIFF Chunk Descriptor
  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataLength, 4); // ChunkSize
  buffer.write('WAVE', 8);

  // fmt Subchunk
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16); // Subchunk1Size (16 para PCM)
  buffer.writeUInt16LE(1, 20); // AudioFormat (1 para PCM Lineal)
  buffer.writeUInt16LE(numChannels, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(byteRate, 28);
  buffer.writeUInt16LE(blockAlign, 32);
  buffer.writeUInt16LE(bitsPerSample, 34);

  // data Subchunk
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataLength, 40);

  return buffer;
}

/**
 * Stream de escritura que genera un archivo WAV válido en disco.
 * Escribe un encabezado provisional y, al cerrarse, actualiza los tamaños reales en bytes.
 */
export class WavFileWriter extends Writable {
  private filePath: string;
  private sampleRate: number;
  private channels: number;
  private bitsPerSample: number;
  private fd: number | null = null;
  private pcmBytesWritten = 0;

  constructor(filePath: string, options: WavWriterOptions = {}) {
    super();
    this.filePath = filePath;
    this.sampleRate = options.sampleRate ?? 48000;
    this.channels = options.channels ?? 1;
    this.bitsPerSample = options.bitsPerSample ?? 16;

    const dir = path.dirname(filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Abrir archivo para lectura y escritura
    this.fd = fs.openSync(filePath, 'w+');

    // Escribir cabecera provisional con tamaño 0
    const initialHeader = createWavHeader(0, this.sampleRate, this.channels, this.bitsPerSample);
    fs.writeSync(this.fd, initialHeader, 0, 44, 0);
  }

  override _write(chunk: Buffer, _encoding: BufferEncoding, callback: (error?: Error | null) => void): void {
    if (this.fd === null) {
      return callback(new Error('Descriptor de archivo cerrado'));
    }

    try {
      const bytesWritten = fs.writeSync(this.fd, chunk, 0, chunk.length, 44 + this.pcmBytesWritten);
      this.pcmBytesWritten += bytesWritten;
      callback(null);
    } catch (err) {
      callback(err as Error);
    }
  }

  override _final(callback: (error?: Error | null) => void): void {
    if (this.fd === null) {
      return callback();
    }

    try {
      // Actualizar cabecera con el tamaño final real de datos PCM
      const finalHeader = createWavHeader(this.pcmBytesWritten, this.sampleRate, this.channels, this.bitsPerSample);
      fs.writeSync(this.fd, finalHeader, 0, 44, 0);
      fs.closeSync(this.fd);
      this.fd = null;
      callback(null);
    } catch (err) {
      callback(err as Error);
    }
  }

  public getTotalBytes(): number {
    return 44 + this.pcmBytesWritten;
  }

  public getPcmBytes(): number {
    return this.pcmBytesWritten;
  }

  public getFilePath(): string {
    return this.filePath;
  }
}
