import React, { useState } from 'react';
import { 
  Cpu, 
  HardDrive, 
  Radio, 
  Activity, 
  Play, 
  Square, 
  Flame, 
  RotateCw, 
  Zap,
  CheckCircle2,
  Clock
} from 'lucide-react';
import { toggleRecorder, toggleWatcher, triggerProcessAll } from '../api';

export default function HardwareView({ status, onRefresh }) {
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);

  const hw = status?.hardware || {};
  const daemons = status?.daemons || {};

  const cpuPercent = hw.cpu_percent || 0;
  const ramUsed = hw.ram_used_gb || 0;
  const ramTotal = hw.ram_total_gb || 0;
  const ramPercent = hw.ram_percent || 0;

  const gpu = hw.gpu || {};
  const gpuName = gpu.name || 'NVIDIA GeForce RTX 4070';
  const gpuUtil = gpu.utilization_gpu_percent || 0;
  const vramUsed = gpu.vram_used_mb || 0;
  const vramTotal = gpu.vram_total_mb || 12288;
  const vramPercent = Math.round((vramUsed / (vramTotal || 1)) * 100);
  const gpuTemp = gpu.temperature_c || 0;

  const recorderActive = daemons.recorder?.active;
  const watcherActive = daemons.watcher?.active;
  const isBatchRunning = daemons.is_processing_batch;

  const handleToggleRecorder = async () => {
    try {
      setActionLoading(true);
      const res = await toggleRecorder();
      setActionMessage(res.message);
      if (onRefresh) onRefresh();
    } catch (err) {
      setActionMessage(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleWatcher = async () => {
    try {
      setActionLoading(true);
      const res = await toggleWatcher();
      setActionMessage(res.message);
      if (onRefresh) onRefresh();
    } catch (err) {
      setActionMessage(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleBoth = async (activate) => {
    try {
      setActionLoading(true);
      if (activate) {
        if (!recorderActive) await toggleRecorder();
        if (!watcherActive) await toggleWatcher();
        setActionMessage('Ambos servicios activados');
      } else {
        if (recorderActive) await toggleRecorder();
        if (watcherActive) await toggleWatcher();
        setActionMessage('Ambos servicios pausados');
      }
      if (onRefresh) onRefresh();
    } catch (err) {
      setActionMessage(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleProcessAll = async () => {
    try {
      setActionLoading(true);
      const res = await triggerProcessAll();
      setActionMessage(res.message);
      if (onRefresh) onRefresh();
    } catch (err) {
      setActionMessage(`Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full">
      {/* Encabezado */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Hardware y Control de Daemons
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Monitoreo en tiempo real de GPU RTX 4070, CPU y procesos de recolección en segundo plano
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg bg-dark-850 hover:bg-dark-700 text-slate-400 hover:text-slate-200 border border-dark-700 transition-colors"
          title="Actualizar métricas"
        >
          <RotateCw size={16} className={actionLoading ? "animate-spin" : ""} />
        </button>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-lg bg-dark-850 border border-dark-650 text-slate-300 text-xs flex items-center justify-between">
          <span>{actionMessage}</span>
          <button
            onClick={() => setActionMessage(null)}
            className="text-slate-500 hover:text-slate-300 text-xs ml-4"
          >
            Cerrar
          </button>
        </div>
      )}

      {/* Grid de Métricas de Hardware */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* GPU Util */}
        <div className="p-4 rounded-xl bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <Zap size={14} className="text-indigo-400" />
              <span>Carga GPU</span>
            </span>
            <span className="font-mono text-slate-300">{gpuUtil}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">{gpuUtil}%</div>
          <div className="w-full bg-dark-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                gpuUtil > 80 ? "bg-amber-500" : "bg-indigo-500"
              }`}
              style={{ width: `${Math.min(gpuUtil, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500 truncate">{gpuName}</div>
        </div>

        {/* VRAM RTX 4070 */}
        <div className="p-4 rounded-xl bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <HardDrive size={14} className="text-cyan-400" />
              <span>Memoria VRAM</span>
            </span>
            <span className="font-mono text-slate-300">{vramPercent}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">
            {Math.round(vramUsed / 1024 * 10) / 10} / {Math.round(vramTotal / 1024 * 10) / 10} GB
          </div>
          <div className="w-full bg-dark-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                vramPercent > 85 ? "bg-rose-500" : "bg-cyan-500"
              }`}
              style={{ width: `${Math.min(vramPercent, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-[11px] text-slate-500">
            <span>Usada: {vramUsed} MB</span>
            <span className="flex items-center space-x-1">
              <Flame size={12} className="text-amber-500" />
              <span>{gpuTemp}°C</span>
            </span>
          </div>
        </div>

        {/* CPU */}
        <div className="p-4 rounded-xl bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <Cpu size={14} className="text-emerald-400" />
              <span>Procesador CPU</span>
            </span>
            <span className="font-mono text-slate-300">{cpuPercent}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">{cpuPercent}%</div>
          <div className="w-full bg-dark-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(cpuPercent, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500">Uso total del sistema</div>
        </div>

        {/* RAM */}
        <div className="p-4 rounded-xl bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <Activity size={14} className="text-purple-400" />
              <span>Memoria RAM</span>
            </span>
            <span className="font-mono text-slate-300">{ramPercent}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">
            {ramUsed} / {ramTotal} GB
          </div>
          <div className="w-full bg-dark-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(ramPercent, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500">RAM disponible para modelos</div>
        </div>
      </div>

      {/* Panel de Control de Daemons */}
      <div className="bg-dark-900 border border-dark-700 rounded-xl p-5 shadow-sm space-y-5">
        <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
          <div>
            <h2 className="font-semibold text-slate-200 text-sm">
              Control de Servicios en Segundo Plano
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Controla de forma independiente la grabación de voz y el consumo de GPU/CPU
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleToggleBoth(true)}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-emerald-400 border border-dark-700 text-xs font-medium transition-colors"
            >
              Activar Ambos
            </button>
            <button
              onClick={() => handleToggleBoth(false)}
              disabled={actionLoading}
              className="px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-400 hover:text-rose-400 border border-dark-700 text-xs font-medium transition-colors"
            >
              Pausar Ambos
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Tarjeta Grabador Discord */}
          <div className="p-4 rounded-xl bg-dark-850 border border-dark-700/70 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className={`p-2 rounded-lg ${recorderActive ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50' : 'bg-dark-800 text-slate-500 border border-dark-700'}`}>
                    <Radio size={18} className={recorderActive ? "animate-pulse" : ""} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">
                      Grabador de Discord
                    </h3>
                    <p className="text-xs text-slate-400">
                      Captura canales de voz a archivos PCM/WAV
                    </p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium border ${
                  recorderActive 
                    ? 'bg-emerald-950/70 text-emerald-300 border-emerald-700/60' 
                    : 'bg-dark-800 text-slate-400 border-dark-700'
                }`}>
                  {recorderActive ? 'En Ejecución' : 'Detenido'}
                </span>
              </div>

              <div className="mt-4 space-y-1 text-xs text-slate-400 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">PID de Proceso:</span>
                  <span>{daemons.recorder?.pid || 'Ninguno'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Módulo:</span>
                  <span>services/discord-bot</span>
                </div>
              </div>
            </div>

            <button
              onClick={handleToggleRecorder}
              disabled={actionLoading}
              className={`w-full py-2 px-3 rounded-lg text-xs font-medium transition-colors flex items-center justify-center space-x-2 border ${
                recorderActive
                  ? 'bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border-rose-800/60'
                  : 'bg-dark-800 hover:bg-dark-750 text-emerald-400 border-emerald-800/50'
              }`}
            >
              {recorderActive ? (
                <>
                  <Square size={14} />
                  <span>Pausar Escucha</span>
                </>
              ) : (
                <>
                  <Play size={14} />
                  <span>Iniciar Escucha Discord</span>
                </>
              )}
            </button>
          </div>

          {/* Tarjeta Vigilante IA */}
          <div className="p-4 rounded-xl bg-dark-850 border border-dark-700/70 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className={`p-2 rounded-lg ${watcherActive ? 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/50' : 'bg-dark-800 text-slate-500 border border-dark-700'}`}>
                    <HardDrive size={18} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">
                      Vigilante IA Continuo
                    </h3>
                    <p className="text-xs text-slate-400">
                      faster-whisper + Gemini / LLaMA en cola
                    </p>
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium border ${
                  watcherActive 
                    ? 'bg-cyan-950/70 text-cyan-300 border-cyan-700/60' 
                    : 'bg-dark-800 text-slate-400 border-dark-700'
                }`}>
                  {watcherActive ? 'Vigilando' : 'Pausado'}
                </span>
              </div>

              <div className="mt-4 space-y-1 text-xs text-slate-400 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">PID de Proceso:</span>
                  <span>{daemons.watcher?.pid || 'Ninguno'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Sesiones Pendientes:</span>
                  <span className={daemons.pending_sessions_count > 0 ? "text-amber-400 font-bold" : "text-slate-400"}>
                    {daemons.pending_sessions_count || 0}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={handleToggleWatcher}
              disabled={actionLoading}
              className={`w-full py-2 px-3 rounded-lg text-xs font-medium transition-colors flex items-center justify-center space-x-2 border ${
                watcherActive
                  ? 'bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border-rose-800/60'
                  : 'bg-dark-800 hover:bg-dark-750 text-cyan-400 border-cyan-800/50'
              }`}
            >
              {watcherActive ? (
                <>
                  <Square size={14} />
                  <span>Frenar Procesado IA</span>
                </>
              ) : (
                <>
                  <Play size={14} />
                  <span>Iniciar Vigilante IA</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Sección de Disparo Manual de Procesamiento por Lote */}
        <div className="p-4 rounded-xl bg-dark-850/80 border border-dark-700/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <Clock size={16} className="text-indigo-400" />
              <span className="text-sm font-semibold text-slate-200">
                Procesar Todas las Sesiones Pendientes Ahora
              </span>
            </div>
            <p className="text-xs text-slate-400 max-w-xl">
              Ejecuta la pipeline completa sobre todas las grabaciones acumuladas: transcripción con faster-whisper (CUDA), extracción de muestras de voz limpias y actualización de perfiles psicológicos con Gemini o LLaMA de respaldo.
            </p>
          </div>

          <button
            onClick={handleProcessAll}
            disabled={actionLoading || isBatchRunning}
            className={`px-4 py-2.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors flex items-center justify-center space-x-2 border ${
              isBatchRunning
                ? 'bg-indigo-950/70 border-indigo-700 text-indigo-300 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white border-indigo-500 shadow-sm'
            }`}
          >
            {isBatchRunning ? (
              <>
                <RotateCw size={14} className="animate-spin" />
                <span>Procesando en Segundo Plano...</span>
              </>
            ) : (
              <>
                <Zap size={14} />
                <span>Procesar Todo Ahora</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
