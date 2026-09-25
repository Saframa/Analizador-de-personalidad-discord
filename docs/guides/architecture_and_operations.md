# Guía de Arquitectura, Operaciones y Referencia Técnica

Este documento proporciona una especificación técnica integral del sistema **Discord AI Profiler & Digital Twin**, diseñada para que cualquier desarrollador, investigador o tercero pueda comprender, operar, mantener y extender la plataforma con facilidad.

---

## 1. Filosofía Arquitectónica y Principios de Diseño

El sistema está construido bajo tres principios fundamentales:

1. **Diseño Basado en Contratos Inmutables (*Contract-First Architecture*):**
   * Los servicios no comparten memoria ni base de datos centralizada.
   * La comunicación entre el grabador de Discord (Node.js) y el pipeline de IA (Python) se realiza exclusivamente mediante archivos JSON atómicos que cumplen esquemas formales JSON Schema Draft-07 ubicados en [`docs/specs/`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/docs/specs/).
   * Toda escritura se realiza mediante el patrón *Atomic File Write* (`.tmp` seguido de reemplazo atómico a nivel de sistema de archivos) para garantizar inmunidad contra cierres abruptos o cortes de energía.

2. **Desacoplamiento Estricto de Cómputo:**
   * **Servicio 1 (Voice Recorder):** Proceso Node.js/TypeScript ultraliviano, responsable de escuchar la red, demultiplexar audio y gestionar presencia. Consume $< 1\%$ de CPU.
   * **Servicio 2 (AI Pipeline):** Proceso Python 3.13 con aceleración por hardware (CUDA en NVIDIA RTX 4070 de 12GB VRAM). Ejecuta VAD, STT (Whisper), extracción de muestras, perfilado LLM y síntesis TTS de forma desacoplada.
   * Ambos servicios pueden reiniciarse, detenerse o ejecutarse en máquinas independientes sin afectarse mutuamente.

3. **Eficiencia de Cómputo y Tokens (*Zero-Token Pre-computation*):**
   * Antes de invocar a Gemini API, el pipeline extrae algorítmicamente métricas duras (turnos, palabras por segundo, tasas de solapamiento, hilos de respuesta y distribución horaria).
   * El LLM solo se emplea para la comprensión cualitativa profunda (psicología, lore, chicanas, disparadores emocionales).

---

## 2. Flujo de Datos y Capa de Persistencia

El almacenamiento local se organiza en [`storage/`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/storage):

```text
storage/
├── raw_sessions/                    # Sesiones grabadas por el bot
│   └── <SESSION_ID>/                # Formato: YYYY-MM-DD_HH-mm-ss
│       ├── audio/                   # Pistas de audio por usuario (.ogg / .wav)
│       │   ├── <USER_ID>.ogg
│       │   └── .purged              # Recibo generado tras el perfilado
│       ├── session_metadata.json    # Contrato A: participantes, duración, archivos
│       └── transcript.json          # Contrato B: transcripción sincronizada
├── clean_samples/                   # Muestras limpias curadas para TTS
│   └── <USER_ID>/
│       └── sample_clean_60s.wav     # 24kHz Mono 16-bit PCM normalizado a -18 LUFS (~2.8 MB)
├── profiles/                        # Fichas acumulativas por usuario
│   └── <USER_ID>/
│       └── profile.json             # Contrato C: perfil Big Five, social, lore, voz
├── backups/                         # Snapshots diarios comprimidos
│   └── profiles_backup_YYYY-MM-DD.zip
└── logs/                            # Registro histórico de actividad
    ├── pipeline.log
    └── pipeline.log.1..5            # Rotación automática cada 10 MB
```

---

## 3. Subsistemas y Módulos Clave

### A. Grabador Autónomo (`services/voice-recorder`)
* **Detección de presencia (`PresenceWatcher`):**
  * Monitorea todos los canales de voz del servidor.
  * Si $\ge 2$ usuarios humanos entran a un canal, el bot se conecta automáticamente e inicia la grabación.
  * Si quedan $< 2$ usuarios, programa una salida elegante tras un debounce de 30 segundos (`DEBOUNCE_LEAVE_SECONDS`).
* **Demultiplexación de audio (`AudioReceiverManager`):**
  * Escucha los paquetes RTP Opus provistos por la API de voz de Discord vía SSRC.
  * Canaliza los paquetes Opus directamente a un contenedor Ogg Opus (`.ogg`) sin transcodificación a PCM en vivo, ahorrando más del $90\%$ de espacio en disco y reduciendo el uso de CPU a cero.
* **Sesiones rotativas de 15 minutos (`SessionManager`):**
  * Cada 15 minutos (`ROTATION_INTERVAL_MINUTES=15`), el bot finaliza atómicamente el bloque actual de grabación y abre de inmediato uno nuevo en milisegundos sin desconectarse del canal.
  * En una llamada de 8 horas continuas, genera 32 bloques de 15 minutos procesables progresivamente, eliminando el riesgo de pérdida total de datos.

---

### B. Pipeline de IA y Reconocimiento de Voz (`services/ai-pipeline`)

#### 1. Detección de Actividad Vocal (VAD) y Solapamientos (`core/vad/`)
* Emplea **Silero VAD v5** sobre PyTorch para segmentar el habla con precisión de milisegundos.
* [`find_overlapping_speakers()`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/services/ai-pipeline/core/vad/overlap_detector.py) calcula exactamente qué participantes hablaron al mismo tiempo.
* [`extract_non_overlapping_intervals()`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/services/ai-pipeline/core/vad/overlap_detector.py) aísla fragmentos libres de ruido y de otras voces con un margen de seguridad de $150$ ms.

#### 2. Transcripción Acelerada (`core/stt/`)
* **faster-whisper** ejecutado con **CTranslate2** en modo FP16 sobre la GPU NVIDIA GeForce RTX 4070.
* Inyecta *hotwords* específicos de la jerga uruguaya (`bo`, `ta`, `salado`, `flama`, `chicana`) para maximizar la precisión de transcripción fonética local.
* Genera el archivo [`transcript.json`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/docs/specs/transcript.schema.json) sincronizado con timestamps y usuarios.

#### 3. Curación de Muestras de Voz (`core/curator/`)
* Selecciona los mejores intervalos sin solapamiento de cada amigo hasta alcanzar un acumulado de 60 segundos.
* Realiza resampleo a 24 kHz Mono y normalización acústica de sonoridad perceptual a **-18 LUFS** con limitador de picos a **-1.0 dBFS**.
* Almacena el resultado en `storage/clean_samples/<USER_ID>/sample_clean_60s.wav` como archivo de referencia permanente para clonación de voz.

---

### C. Motor de Contexto Conversacional y Grafos (`core/context/`)
* **`DiscourseThreader`:** Reconstruye la estructura conversacional de la llamada sin tokens:
  1. *Decaimiento temporal:* $e^{-\Delta t / 3.0}$.
  2. *Reconocimiento de apodos:* Detecta si una intervención menciona a un amigo registrado.
  3. *Emparejamiento de preguntas y respuestas:* Asocia turnos interrogativos con réplicas directas.
  4. *Similitud léxica:* Solapamiento Jaccard de vocabulario.
* Agrupa las intervenciones en hilos temáticos y clasifica dinámicas grupales (*Consulta Técnica*, *Broma / Chicana Afectuosa*, *Coordinación*, *Charla Casual*).

---

### D. Perfilado Psicológico y Conductual (`core/profiler/`)

#### 1. Inferencia Estructurada con Gemini (`gemini_analyzer.py`)
* Utiliza el SDK oficial `google-genai` con modelo `gemini-flash-latest` y salidas forzadas por esquema Pydantic (`response_schema=GeminiSessionEvaluation`).
* **Calibración dialectal rioplatense uruguaya:** El prompt del sistema (`RIOPLATENSE_SYSTEM_INSTRUCTIONS`) calibra al modelo para entender que las chicanas, insultos lúdicos y bromas afectuosas son indicadores de **alta complicidad y confianza grupal**, no de toxicidad.
* **Protocolo anti-alucinaciones:** Obliga al LLM a incluir citas textuales directas con su timestamp para cada rasgo evaluado.

#### 2. Modelado Longitudinal Multidimensional
* **Promedio continuo adaptativo:**
  $$\alpha = \max\left(0.05, \frac{1}{N + 1}\right)$$
  $$\text{Score}_{\text{new}} = (1 - \alpha) \cdot \text{Score}_{\text{prev}} + \alpha \cdot \text{Score}_{\text{session}}$$
* **Dimensiones evaluadas en el perfil:**
  * **Big Five (OCEAN):** Apertura, Responsabilidad, Extraversión, Amabilidad, Neuroticismo.
  * **Estilo comunicativo:** Cadencia (palabras/segundo), palabras por turno, proporción de interrupciones, humor predominante.
  * **Dinámica social (`SocialDynamics`):** Amigos más cercanos, blancos de chicanas y conteo acumulado de interacciones mutuas.
  * **Lore grupal (`GroupLore`):** Chistes internos, frases meme, menciones de entidades externas y anécdotas compartidas.
  * **Disparadores emocionales (`EmotionalTriggers`):** *Tilts* (frustraciones/quejas) vs *Hiperfocos* (pasiones).
  * **Iniciativa en actividades (`ActivityInitiative`):** Nivel de iniciativa (`iniciador`, `seguidor`), juegos y planes propuestos.
  * **Cronotipo (`TemporalPatterns`):** Distribución horaria (noctámbulo, vespertino, madrugador) y variaciones de humor de madrugada.

---

### E. Motor del Gemelo Digital y Síntesis de Voz (`core/twin/` y `core/tts/`)

* **Compilador Dinámico Jinja2 (`compiler.py`):**
  * Transforma el perfil completo en un System Prompt conversacional de altísima fidelidad.
  * Inyecta pares few-shot reales de diálogos mantenidos por el amigo en las llamadas.
  * Modula la temperatura del modelo según la personalidad:
    $$\text{temp} = 0.50 + 0.30 \cdot E + 0.20 \cdot O - 0.20 \cdot C$$
* **Clonación de voz zero-shot (`core/tts/`):**
  * Emplea modelos de *Flow Matching* / Diffusion Transformer (**F5-TTS**) en modo FP16 en la RTX 4070.
  * Inferencia de audio en $\sim 1.5$ segundos por turno conversacional.
  * Normalizador lingüístico uruguayo: elimina emojis y expande abreviaturas de chat antes de sintetizar.
  * Reproductor de baja latencia con `winsound` nativo en Windows.

---

## 4. Guía Operativa de Comandos CLI

El script [`services/ai-pipeline/main.py`](file:///c:/Users/safra/Documents/antigravity/clever-hypatia/services/ai-pipeline/main.py) centraliza la orquestación mediante subcomandos:

| Subcomando | Propósito | Ejemplo de Uso |
| :--- | :--- | :--- |
| `watch` | Demonio 24/7 autónomo: detecta, procesa, purga audios y hace backups | `python main.py watch --interval 15` |
| `process` | Procesa una sesión grabada (STT + Silero VAD + Curación 60s) | `python main.py process --session latest` |
| `profile` | Analiza psicológicamente y sintetiza perfiles con Gemini | `python main.py profile --session latest` |
| `context` | Visualiza árboles discursivos e hilos conversacionales | `python main.py context --session latest` |
| `user list` | Lista todos los usuarios registrados en el sistema | `python main.py user list` |
| `user create` | Registra un nuevo amigo con apodos y notas iniciales | `python main.py user create --user-id 123 --username fiera --nicknames "fifi,perro"` |
| `user show` | Muestra la ficha técnica completa y multidimensional de un amigo | `python main.py user show --user-id saframa` |
| `user update` | Actualiza apodos, notas o datos personales de un usuario | `python main.py user update --user-id saframa --add-notes "juega LoL"` |
| `chat` | Chatea interactivamente con el Gemelo Digital | `python main.py chat --user-id saframa` |
| `chat --voice` | Chatea y escucha las respuestas habladas con su voz clonada | `python main.py chat --user-id saframa --voice --play` |
| `tts` | Sintetiza cualquier texto arbitrario con la voz de un amigo | `python main.py tts --user-id saframa --text "Bo mirá esto" --play` |

---

## 5. Garantías de Resiliencia Industrial y Tolerancia a Fallos

1. **Gestión de Energía Windows (Win32 Anti-Sleep):**
   * El modo `watch` invoca a `ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)`.
   * Impide que Windows ponga en reposo la CPU/GPU tras periodos de inactividad mientras procesa de noche.
2. **Cola de Cuarentena contra Fallos (*Dead-Letter Queue*):**
   * Si una sesión presenta archivos corruptos o ilegibles, escribe un recibo `.failed` con el traceback del error y continúa procesando el resto de las llamadas sin detenerse.
3. **Purga Automática de Disco:**
   * Inmediatamente después del perfilado, el audio pesado de la llamada es eliminado, liberando gigabytes de almacenamiento y conservando intactos el `transcript.json` y la muestra de voz de 60s.
4. **Respaldos Diarios Automáticos:**
   * Cada 24 horas genera un `.zip` en `storage/backups/` y elimina copias de seguridad de más de 30 días.
5. **Reintentos Exponenciales con Fallback:**
   * La API de Gemini cuenta con 3 reintentos automáticos (2s, 6s, 15s) ante rate limits (429) o fallas de red, conmutando a un sintetizador heurístico determinista si la conexión se corta por completo.
