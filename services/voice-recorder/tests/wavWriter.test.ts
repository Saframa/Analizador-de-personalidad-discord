import { test } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { createWavHeader, WavFileWriter } from '../src/audio/wavWriter.js';

test('createWavHeader genera un encabezado RIFF estándar de 44 bytes', () => {
  const header = createWavHeader(1000, 48000, 1, 16);

  assert.strictEqual(header.length, 44);
  assert.strictEqual(header.toString('ascii', 0, 4), 'RIFF');
  assert.strictEqual(header.readUInt32LE(4), 36 + 1000);
  assert.strictEqual(header.toString('ascii', 8, 12), 'WAVE');
  assert.strictEqual(header.toString('ascii', 12, 16), 'fmt ');
  assert.strictEqual(header.readUInt16LE(20), 1); // PCM format
  assert.strictEqual(header.readUInt16LE(22), 1); // 1 canal Mono
  assert.strictEqual(header.readUInt32LE(24), 48000); // 48kHz
  assert.strictEqual(header.readUInt32LE(28), 96000); // ByteRate = 48000 * 1 * 2 = 96000
  assert.strictEqual(header.readUInt16LE(32), 2); // BlockAlign = 2
  assert.strictEqual(header.readUInt16LE(34), 16); // 16 bits
  assert.strictEqual(header.toString('ascii', 36, 40), 'data');
  assert.strictEqual(header.readUInt32LE(40), 1000); // Tamaño de datos
});

test('WavFileWriter escribe datos y finaliza la cabecera atómicamente', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wav-test-'));
  const testWavPath = path.join(tempDir, 'output.wav');

  const writer = new WavFileWriter(testWavPath, {
    sampleRate: 48000,
    channels: 1,
    bitsPerSample: 16,
  });

  // Generar 960 bytes de audio simulado (1 frame de 10ms a 48kHz 16-bit)
  const mockPcmFrame = Buffer.alloc(960, 0x55);

  writer.write(mockPcmFrame);
  writer.write(mockPcmFrame);

  await new Promise<void>((resolve) => {
    writer.end(() => resolve());
  });

  assert.strictEqual(fs.existsSync(testWavPath), true);
  const fileBuffer = fs.readFileSync(testWavPath);

  // 44 bytes de cabecera + (960 * 2) bytes de audio = 1964 bytes
  assert.strictEqual(fileBuffer.length, 44 + 1920);
  assert.strictEqual(fileBuffer.readUInt32LE(4), 36 + 1920);
  assert.strictEqual(fileBuffer.readUInt32LE(40), 1920);

  // Limpiar archivo temporal
  fs.rmSync(tempDir, { recursive: true, force: true });
});
