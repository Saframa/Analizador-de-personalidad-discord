# Documento de Discusión y Especificación: Interfaz Gráfica de Escritorio (Electron)
## Discord Profiler & Digital Twin Dashboard

**Rama:** `feature/gui-electron`  
**Metodología:** GSD (Get Shit Done) - Fase 1: Discuss & Architecture

---

## 1. Mapeo de Funcionalidades (desde `COMANDOS.md` y Requerimientos)

### A. Panel de Control y Hardware (Estado del Sistema)
- **Monitoreo en tiempo real:**
  - Uso de CPU (%) y RAM del sistema (GB / %).
  - Uso de GPU NVIDIA RTX 4070 (%) y memoria VRAM (usada / 12 GB).
- **Control de Demonios y Procesos:**
  - Botón: *Pausar / Reanudar Escucha* (control del grabador de Discord `voice-recorder`).
  - Botón: *Pausar / Reanudar Procesado* (control del vigilante autónomo `main.py watch`).
  - Botón: *Activar Ambos*.
  - Botón de acción inmediata: *Procesar Todo Ahora* (`process-all`).
- **Temporizador / Próxima Ejecución:**
  - Contador hacia el próximo barrido programado de sesiones.
  - Indicador de sesiones acumuladas en espera (`storage/raw_sessions/`).

### B. Estadísticas Generales de Todas las Recolecciones
- **Métricas agregadas globales:**
  - Total de sesiones grabadas y analizadas.
  - Tiempo total de voz capturado (horas, minutos).
  - Total de palabras catalogadas en el diccionario léxico global.
- **Gráficos y Dinámicas:**
  - Distribución de volumen de habla por amigo (gráfico de barras / torta).
  - Actividad por hora del día (cronotipo del grupo).
  - Tabla de participantes con métricas de cadencia e interrupciones.

### C. Directorio y Ficha de Amigos (Apartado por Persona)
- **Tarjeta e Inspección detallada:**
  - Carga manual de foto/avatar por el usuario (almacenada persistentemente en `storage/profiles/avatars/<user_id>.png`).
  - Nombres, username de Discord, ID y lista de apodos reconocidos.
  - Rol arquetípico en el grupo y estilo de humor.
  - Memoria pasiva y notas de contexto (con opción de agregar/editar notas).
- **Rasgos Big Five Evolutivos:**
  - Barras de progreso de los 5 grandes rasgos (Apertura, Responsabilidad, Extraversión, Amabilidad, Neuroticismo) de 0.0 a 1.0 con porcentaje de confianza.
  - Citas textuales directas que sustentan cada evaluación.
- **Diccionario Léxico Personal:**
  - Palabras más repetidas del amigo con conteo exacto de ocurrencias.
  - Filtro para ignorar conectores comunes (stopwords) y ver sus palabras clave únicas.
  - Modismos rioplatenses preferidos (*bo, ta, flama, salado, posta*).

### D. Chat con el Gemelo Digital (Ventana Integrada)
- **Acceso:** Ícono en la esquina superior derecha de la ficha de cada persona.
- **Experiencia de usuario:**
  - Estilo minimalista tipo ChatGPT / Claude en tema oscuro.
  - Respuestas limpias solo con el texto del amigo (cero mensajes de debug o trazas técnicas).
  - Conmutador opcional para activar síntesis de voz (F5-TTS) y reproducción en altavoces.
  - Selector de motor: Automático (Gemini con fallback a Groq LLaMA 3.3) o LLaMA directo.

### E. Síntesis Rápida de Voz (TTS Studio)
- Campo de texto libre para escribir cualquier frase y escucharla con la voz clonada del amigo seleccionado.

---

## 2. Reglas de Diseño Visual Estrictas
- **Cero Emojis:** Prohibido el uso de emojis en toda la interfaz. Toda la iconografía se renderiza con iconos vectoriales limpios (Lucide Icons).
- **Paleta de Colores:** Modo oscuro profundo (*Dark Slate / Charcoal* `#0B0F19`, `#111827`, `#1F2937`), acentos sobrios (*Slate Blue / Soft Cyan / Muted Indigo*), sin colores neón agresivos ni saturados.
- **Responsive:** Diseño adaptable mediante CSS Grid y Flexbox fluido con Tailwind CSS.
- **Navegación:** Menú superior izquierdo accesible y colapsable.

---

## 3. Arquitectura Técnica Recomendada
- **Frontend / Shell:** Electron + React (Vite) + Tailwind CSS + Lucide Icons.
- **Capa de Comunicación:** API local ligera (FastAPI en Python dentro de `services/ai-pipeline`) que sirve datos en JSON, métricas de hardware vía `psutil` + `pynvml` y WebSocket/SSE para streaming fluido del chat sin bloquear el proceso principal de Electron.
