import dotenv from 'dotenv';
import path from 'node:path';
import { z } from 'zod';

// Cargar variables de entorno desde .env local o desde la raíz
dotenv.config();

const ConfigSchema = z.object({
  DISCORD_TOKEN: z.string().min(1, 'DISCORD_TOKEN es obligatorio para conectar el bot'),
  GUILD_ID: z.string().optional(),
  MIN_USERS_TO_RECORD: z.coerce.number().int().min(1).default(2),
  DEBOUNCE_LEAVE_SECONDS: z.coerce.number().int().min(1).default(15),
  ROTATION_INTERVAL_MINUTES: z.coerce.number().int().min(1).default(15),
  STORAGE_DIR: z.string().default('../../storage'),
});

const parsed = ConfigSchema.safeParse(process.env);

if (!parsed.success) {
  console.warn('⚠️ [Config] Faltan variables de entorno obligatorias o tienen formato inválido:');
  for (const issue of parsed.error.issues) {
    console.warn(`   - ${issue.path.join('.')}: ${issue.message}`);
  }
}

export interface AppConfig {
  DISCORD_TOKEN: string;
  GUILD_ID?: string;
  MIN_USERS_TO_RECORD: number;
  DEBOUNCE_LEAVE_SECONDS: number;
  ROTATION_INTERVAL_MINUTES: number;
  STORAGE_DIR: string;
}

// Configuración por defecto o parseada para permitir compilación y testing
export const config: AppConfig = {
  DISCORD_TOKEN: parsed.success ? parsed.data.DISCORD_TOKEN : (process.env.DISCORD_TOKEN || ''),
  GUILD_ID: parsed.success ? parsed.data.GUILD_ID : process.env.GUILD_ID,
  MIN_USERS_TO_RECORD: parsed.success ? parsed.data.MIN_USERS_TO_RECORD : 2,
  DEBOUNCE_LEAVE_SECONDS: parsed.success ? parsed.data.DEBOUNCE_LEAVE_SECONDS : 15,
  ROTATION_INTERVAL_MINUTES: parsed.success ? parsed.data.ROTATION_INTERVAL_MINUTES : 15,
  STORAGE_DIR: path.resolve(process.cwd(), parsed.success ? parsed.data.STORAGE_DIR : (process.env.STORAGE_DIR || '../../storage')),
};
