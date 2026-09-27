# Plan de Implementación: Interfaz Gráfica de Escritorio (Electron + FastAPI)
## GSD Fase 2: Plan

**Rama:** `feature/gui-electron`  
**Objetivo:** Desarrollar la aplicación de escritorio completa con Electron, React, Tailwind CSS y backend FastAPI integrado.

---

## Tareas Desglosadas en Olas de Ejecución

### Ola 1: Backend API Local (`services/ai-pipeline/api`)
- [ ] **Tarea 1.1**: Crear servidor FastAPI modular en `services/ai-pipeline/api/server.py`.
- [ ] **Tarea 1.2**: Implementar endpoints de hardware y procesos (`/api/status`, `/api/daemon/*`) con `psutil`, `pynvml` / `nvidia-smi` y gestión de PIDs.
- [ ] **Tarea 1.3**: Implementar endpoints de estadísticas globales y directorio de usuarios (`/api/stats/global`, `/api/users`, `/api/users/{id}`).
- [ ] **Tarea 1.4**: Implementar carga/servicio de avatares personalizados (`/api/users/{id}/avatar`).
- [ ] **Tarea 1.5**: Implementar endpoints de chat (`/api/chat/{id}`) y síntesis de audio bajo demanda (`/api/tts/{id}`).
- [ ] **Verificación Ola 1**: Tests con `pytest` y curl a endpoints de FastAPI.

### Ola 2: Scaffold del Proyecto Electron + React + Tailwind
- [ ] **Tarea 2.1**: Inicializar `services/desktop-gui` con Vite, React, TypeScript y Tailwind CSS.
- [ ] **Tarea 2.2**: Configurar Electron (`main.cjs`, `preload.cjs`) con ventana sin marco personalizada o barra de título nativa oscura.
- [ ] **Tarea 2.3**: Integrar `lucide-react` para iconografía vectorial limpia (estricto: cero emojis).
- [ ] **Tarea 2.4**: Configurar paleta de colores oscuros (*Slate / Zinc* oscuro, acentos sutiles sin neones).
- [ ] **Verificación Ola 2**: Compilación y renderizado exitoso de la ventana de Electron en modo desarrollo.

### Ola 3: Componentes y Vistas de la Aplicación
- [ ] **Tarea 3.1**: Menú superior izquierdo y barra de navegación responsive.
- [ ] **Tarea 3.2**: Vista de Hardware & Control del Vigilante (Métricas en vivo de CPU, GPU, VRAM, RAM, temporizador y botones de pausa/reanudación).
- [ ] **Tarea 3.3**: Vista de Estadísticas Generales (Métricas globales, tiempo acumulado de llamadas, distribución de habla).
- [ ] **Tarea 3.4**: Vista de Directorio de Amigos y Ficha de Inspección Detallada (Avatar personalizado con subida de archivo, rasgos Big Five con barras de progreso, vocabulario con filtro de palabras comunes).
- [ ] **Tarea 3.5**: Panel Lateral Desplegable de Chat (Slide-over ChatGPT-style, texto puro, sin debug, con botón sutil de altavoz para escuchar la voz del gemelo).
- [ ] **Verificación Ola 3**: Pruebas de interacción en la UI con datos reales de `storage/profiles/` y `storage/raw_sessions/`.

### Ola 4: Integración y Empaquetado
- [ ] **Tarea 4.1**: Script de inicio unificado para lanzar FastAPI y Electron simultáneamente (`npm run dev` / `.bat`).
- [ ] **Tarea 4.2**: Pruebas de extremo a extremo (E2E) y verificación de diseño responsive.
