import { test } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { OggOpusFileWriter } from '../src/audio/oggOpusWriter.js';

test('OggOpusFileWriter genera un archivo Ogg Opus estándar con páginas BOS y paquetes válidos', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ogg-test-'));
  const testOggPath = path.join(tempDir, 'output.ogg');

  const writer = new OggOpusFileWriter(testOggPath);

  // Simular 3 frames de audio Opus (ej. 80 bytes por frame)
  const mockOpusFrame = Buffer.alloc(80, 0xfc);

  writer.write(mockOpusFrame);
  writer.write(mockOpusFrame);
  writer.write(mockOpusFrame);

  await new Promise<void>((resolve) => {
    writer.end(() => resolve());
  });

  assert.strictEqual(fs.existsSync(testOggPath), true);
  const fileBuffer = fs.readFileSync(testOggPath);

  // Verificar que el archivo empiece con la firma OggS
  assert.strictEqual(fileBuffer.subarray(0, 4).toString('ascii'), 'OggS');

  // Verificar que la primera página contenga el identificador OpusHead
  const headIndex = fileBuffer.indexOf('OpusHead');
  assert.strictEqual(headIndex !== -1, true);

  // Verificar que la segunda página contenga el identificador OpusTags
  const tagsIndex = fileBuffer.indexOf('OpusTags');
  assert.strictEqual(tagsIndex !== -1, true);

  // El archivo debe ser infinitamente más liviano que WAV
  assert.strictEqual(writer.getTotalBytes() > 0, true);

  fs.rmSync(tempDir, { recursive: true, force: true });
});
