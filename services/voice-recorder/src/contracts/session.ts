import { z } from 'zod';
import * as fs from 'node:fs';
import * as path from 'node:path';

/**
 * Esquema de información de participante en una sesión de Discord.
 */
export const ParticipantSchema = z.object({
  user_id: z.string().min(1, 'El user_id no puede estar vacío'),
  username: z.string().min(1, 'El username no puede estar vacío'),
  display_name: z.string().min(1, 'El display_name no puede estar vacío'),
  joined_at: z.string().datetime({ message: 'joined_at debe ser un timestamp ISO 8601 válido' }),
  left_at: z.string().datetime({ message: 'left_at debe ser un timestamp ISO 8601 válido' }).nullable(),
});

export type Participant = z.infer<typeof ParticipantSchema>;

/**
 * Esquema de metadatos de un archivo de audio grabado por usuario.
 */
export const AudioFileInfoSchema = z.object({
  filename: z.string().min(1, 'El nombre de archivo es requerido'),
  sample_rate: z.literal(48000),
  channels: z.union([z.literal(1), z.literal(2)]),
  format: z.enum(['pcm_s16le', 'wav', 'ogg_opus']),
  size_bytes: z.number().int().nonnegative('El tamaño del archivo debe ser mayor o igual a 0'),
});

export type AudioFileInfo = z.infer<typeof AudioFileInfoSchema>;

/**
 * Esquema raíz del contrato session_metadata.json (Draft-07).
 */
export const SessionMetadataSchema = z.object({
  version: z.literal('1.0.0'),
  session_id: z.string().regex(
    /^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$/,
    'session_id debe seguir el patrón YYYY-MM-DD_HH-mm-ss'
  ),
  guild_id: z.string().min(1, 'guild_id no puede estar vacío'),
  channel_id: z.string().min(1, 'channel_id no puede estar vacío'),
  channel_name: z.string().min(1, 'channel_name no puede estar vacío'),
  started_at: z.string().datetime({ message: 'started_at debe ser un timestamp ISO 8601 válido' }),
  ended_at: z.string().datetime({ message: 'ended_at debe ser un timestamp ISO 8601 válido' }),
  duration_seconds: z.number().nonnegative('duration_seconds debe ser >= 0'),
  participants: z.array(ParticipantSchema).min(1, 'Debe haber al menos un participante registrado'),
  audio_files: z.record(z.string(), AudioFileInfoSchema),
});

export type SessionMetadata = z.infer<typeof SessionMetadataSchema>;

/**
 * Escribe el archivo session_metadata.json de forma atómica y validada.
 * Utiliza un archivo temporal (.tmp) y renameSync para prevenir archivos corruptos si ocurre un corte.
 */
export function writeSessionMetadataAtomic(targetFilePath: string, data: unknown): SessionMetadata {
  const validated = SessionMetadataSchema.parse(data);
  const tempFilePath = `${targetFilePath}.tmp`;

  const dir = path.dirname(targetFilePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  fs.writeFileSync(tempFilePath, JSON.stringify(validated, null, 2), 'utf-8');
  fs.renameSync(tempFilePath, targetFilePath);

  return validated;
}

/**
 * Lee y valida un archivo session_metadata.json desde disco.
 */
export function readSessionMetadataValidated(filePath: string): SessionMetadata {
  if (!fs.existsSync(filePath)) {
    throw new Error(`El archivo de metadatos no existe: ${filePath}`);
  }
  const content = fs.readFileSync(filePath, 'utf-8');
  return SessionMetadataSchema.parse(JSON.parse(content));
}
