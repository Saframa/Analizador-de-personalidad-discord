# 📖 GUÍA COMPLETA DE COMANDOS DEL SISTEMA
### Discord AI Profiler & Digital Twin

> Todos los comandos del pipeline de IA se ejecutan dentro del directorio `services/ai-pipeline`.  
> Si estás en la raíz del proyecto, primero haz:  
> `cd services/ai-pipeline`

---

## 📑 ÍNDICE RÁPIDO
1. [🤖 Gemelos Digitales (Chat Réplica)](#1--gemelos-digitales-chat-réplica)
2. [🎙️ Clonación y Síntesis de Voz (TTS Local)](#2-️-clonación-y-síntesis-de-voz-tts-local)
3. [👥 Gestión de Usuarios y Diccionarios Léxicos](#3--gestión-de-usuarios-y-diccionarios-léxicos)
4. [🕵️ Vigilante Autónomo y Procesamiento de Audios](#4-️-vigilante-autónomo-y-procesamiento-de-audios)
5. [🧠 Contexto e Hilos Conversacionales](#5--contexto-e-hilos-conversacionales)
6. [⚡ Accesos Directos (.bat)](#6--accesos-directos-bat)
7. [🧪 Pruebas y Diagnóstico](#7--pruebas-y-diagnóstico)

---

## 1. 🤖 GEMELOS DIGITALES (CHAT RÉPLICA)

Permite hablar con el clon conversacional de cualquier amigo. El gemelo adopta su personalidad Big Five, su cadencia de habla, sus modismos y se basa en las llamadas reales grabadas por el bot.

### A. Chat interactivo por texto (Consola)
```powershell
# Chatear con Suna (usa Groq LLaMA si Gemini agota la cuota):
python main.py chat --user-id suna

# Chatear con Mateo / Jinx:
python main.py chat --user-id mateo

# Chatear con Marce:
python main.py chat --user-id saframa
```

### B. Forzar motor de Inteligencia Artificial (`--backend`)
```powershell
# Modo automático (Recomendado: Gemini primero, fallback transparente a LLaMA):
python main.py chat --user-id suna --backend auto

# Forzar LLaMA 3.3 en Groq (14.400 solicitudes gratuitas/día, ultra rápido):
python main.py chat --user-id suna --backend llama

# Forzar Gemini:
python main.py chat --user-id suna --backend gemini
```

### C. Chat con Voz Clonada y Reproducción en Altavoces
```powershell
# Responde por texto y además sintetiza la voz con F5-TTS y la reproduce por tus parlantes:
python main.py chat --user-id suna --voice --play

# Con Mateo:
python main.py chat --user-id mateo --voice --play
```

### D. Pregunta única no interactiva (`--prompt`)
```powershell
# Hacer una sola consulta directa sin entrar al loop del chat:
python main.py chat --user-id suna --prompt "Buenas che, cómo andás?"
python main.py chat --user-id suna --prompt "Che Suna, estás para jugar o qué?"
```

---

## 2. 🎙️ CLONACIÓN Y SÍNTESIS DE VOZ (TTS LOCAL)

Genera archivos de audio `.wav` con la voz clonada de cualquier amigo a partir de texto arbitrario usando **F5-TTS** acelerado en tu GPU RTX 4070 (~2.5 segundos por audio).

```powershell
# Sintetizar una frase y escucharla de inmediato por los altavoces:
python main.py tts --user-id suna --text "Buenas gente, sale partida hoy o están durmiendo?" --play

# Con la voz de Mateo:
python main.py tts --user-id mateo --text "No te la puedo creer, mirá lo que pasó en el juego." --play

# Con la voz de Marce:
python main.py tts --user-id saframa --text "Che, ya quedó listo el código, prueben entrar ahora." --play

# Guardar el audio generado en una ruta personalizada (sin reproducir):
python main.py tts --user-id suna --text "Audio de prueba guardado en disco." --output "../../storage/saludo_suna.wav"
```

---

## 3. 👥 GESTIÓN DE USUARIOS Y DICCIONARIOS LÉXICOS

Permite inspeccionar qué sabe el sistema de cada amigo, sus apodos, notas personales, métricas psicológicas y las palabras que más repite en Discord.

### A. Listar todos los usuarios registrados
```powershell
python main.py user list
```
*Muestra una tabla con ID, Username, Apodo visible, Rol grupal y estado de su muestra de voz de 60 segundos.*

### B. Ver el diccionario léxico y palabras más usadas (`user vocab`)
```powershell
# Ver las 30 palabras más usadas de TODOS los usuarios:
python main.py user vocab

# Ver el vocabulario de un usuario en específico:
python main.py user vocab --user-id suna
python main.py user vocab --user-id mateo

# Ver el Top 50 palabras filtrando conectores comunes (el, la, que, de):
python main.py user vocab --user-id suna --top 50 --filter-stopwords
```

### C. Ver ficha psicológica y técnica completa (`user show`)
```powershell
# Muestra Big Five, dinámicas sociales, citas textuales y datos de fondo:
python main.py user show --user-id suna
python main.py user show --user-id mateo
python main.py user show --user-id saframa
```

### D. Actualizar apodos, notas o datos a mano (`user update`)
```powershell
# Agregar notas de contexto (recuerda que el bot las usa como memoria pasiva sin forzarlas):
python main.py user update --user-id suna --add-notes "juega LoL en top, hincha de Peñarol"

# Agregar apodos con los que le llaman en Discord:
python main.py user update --user-id suna --add-nicknames "franquito,enano"

# Cambiar nombre visible:
python main.py user update --user-id mateo --display-name "Mateo"
```

### E. Crear un nuevo usuario manualmente (`user create`)
```powershell
python main.py user create --user-id 123456789 --username amigo_discord --display-name "Amigo" --nicknames "pepe" --notes "le gusta programar"
```

---

## 4. 🕵️ VIGILANTE AUTÓNOMO Y PROCESAMIENTO DE AUDIOS

### A. Iniciar el Vigilante Autónomo (Recomendado 24/7)
Detecta automáticamente llamadas finalizadas de Discord en segundo plano, extrae las pistas con Silero VAD, transcribe en GPU con faster-whisper, perfila psicológicamente y purga los audios pesados para no llenar el disco duro.
```powershell
python main.py watch
```
*(Incluye protección de PID Lock: no se duplicará en la GPU aunque intentes abrirlo dos veces).*

### B. Procesar sesiones grabadas manualmente
```powershell
# Procesar TODAS las sesiones pendientes acumuladas en lote:
python main.py process --session all --profile --delete-audio

# Procesar solo la última sesión:
python main.py process --session latest --profile

# Procesar una sesión específica por su fecha:
python main.py process --session 2026-09-25_18-41-13 --profile
```

### C. Perfilar una sesión ya transcripta
```powershell
python main.py profile --session latest
```

---

## 5. 🧠 CONTEXTO E HILOS CONVERSACIONALES

Visualiza cómo el sistema reconstruye la conversación de la llamada en grafos de respuesta de 0 tokens:
```powershell
# Ver el árbol jerárquico de hilos de la última llamada:
python main.py context --session latest --tree

# Ver hilos de una sesión específica:
python main.py context --session 2026-09-25_18-41-13 --tree
```

---

## 6. ⚡ ACCESOS DIRECTOS (.BAT)

En la carpeta raíz del proyecto (`c:\Users\safra\Documents\antigravity\clever-hypatia`), tienes ejecutables de doble clic listos:

| Archivo | Qué hace |
| :--- | :--- |
| `iniciar_sistema.bat` | Lanza simultáneamente el grabador de Discord y el vigilante de IA. |
| `iniciar_vigilante_ai.bat` | Lanza el vigilante autónomo (`main.py watch`). |
| `iniciar_grabador.bat` | Lanza el bot de Discord en Node.js que graba las llamadas. |
| `procesar_todas_las_llamadas.bat` | Procesa en lote todas las sesiones históricas pendientes. |

---

## 7. 🧪 PRUEBAS Y DIAGNÓSTICO

```powershell
# Correr toda la suite de pruebas unitarias automatizadas (12 tests):
python -m pytest tests/test_twin.py tests/test_llama_fallback.py

# Ver el estado en tiempo real de tu tarjeta gráfica (VRAM, Temperatura, Carga):
nvidia-smi
```

---

### 💡 Consejos de Uso:
1. **Identificadores flexibles:** Puedes usar el ID numérico (`960401021757169694`), su username de Discord (`garmadius`), su display name (`Suna`) o cualquiera de sus apodos (`suna`). El sistema los resuelve todos automáticamente.
2. **Audio purgado:** No te preocupes por el espacio en disco; los archivos `.ogg` pesados se borran automáticamente tras transcribirse, dejando solo el texto y una muestra dorada de 60 segundos por usuario para la clonación de voz.
