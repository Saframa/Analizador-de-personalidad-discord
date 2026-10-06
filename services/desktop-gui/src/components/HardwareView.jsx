import React, { useState, useEffect, useRef } from 'react';
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
  Clock, 
  Check, 
  CheckCircle2, 
  AlertCircle,
  Terminal,
  Sparkles,
  Mic,
  Brain,
  Database,
  ChevronRight,
  Layers,
  Volume2
} from 'lucide-react';
import { toggleRecorder, toggleWatcher, triggerProcessAll, fetchPipelineLogs } from '../api';

export default function HardwareView({ status, onRefresh, onOpenLogs }) {
  const [loadingAction, setLoadingAction] = useState(null); // 'both-start' | 'both-pause' | 'recorder' | 'watcher' | 'process-all' | 'refresh'
  const [successAction, setSuccessAction] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);

  // Estado del monitor de procesamiento en vivo
  const [localIsProcessing, setLocalIsProcessing] = useState(false);
  const [pipelineData, setPipelineData] = useState(null);
  const [justFinished, setJustFinished] = useState(false);
  const [justFailed, setJustFailed] = useState(null);
  const [processingDuration, setProcessingDuration] = useState(0);
  const logsTerminalRef = useRef(null);

  const hw = status?.hardware || {};
  const daemons = status?.daemons || {};

  const cpuPercent = hw.cpu_percent || 0;
  const ramUsed = hw.ram_used_gb || 0;
  const ramTotal = hw.ram_total_gb || 0;
  const ramPercent = hw.ram_percent || 0;

  const gpu = hw.gpu || {};
  const gpuName = gpu.name || 'NVIDIA GeForce RTX 4070';
  const gpuUtil = gpu.utilization_gpu_percent ?? gpu.utilization_percent ?? 0;
  const vramUsed = gpu.vram_used_mb || 0;
  const vramTotal = gpu.vram_total_mb || 12288;
  const vramPercent = Math.round((vramUsed / (vramTotal || 1)) * 100);
  const gpuTemp = gpu.temperature_c || 0;

  const recorderActive = daemons.recorder?.active;
  const watcherActive = daemons.watcher?.active;
  const nextProc = daemons.next_processing;

  // Determinar si hay procesamiento activo (por lote manual, por watcher o por estado local)
  const isEffectivelyProcessing = Boolean(
    daemons.is_processing_batch || 
    localIsProcessing || 
    pipelineData?.is_running
  );
  const isBatchRunning = isEffectivelyProcessing;

  // Contador regresivo suave que corre localmente cada segundo
  const [localSeconds, setLocalSeconds] = useState(nextProc?.seconds_remaining ?? null);

  useEffect(() => {
    if (nextProc?.seconds_remaining !== undefined && nextProc?.seconds_remaining !== null) {
      setLocalSeconds(nextProc.seconds_remaining);
    }
  }, [nextProc?.seconds_remaining]);

  useEffect(() => {
    if (!nextProc?.is_automatic || localSeconds === null || localSeconds === undefined) return;
    const interval = setInterval(() => {
      setLocalSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [nextProc?.is_automatic, localSeconds !== null]);

  // Sondeo de logs en vivo a alta frecuencia mientras se esté procesando
  useEffect(() => {
    let timer = null;
    const pollLogs = async () => {
      try {
        const res = await fetchPipelineLogs(40);
        setPipelineData(res);
        if (!res.is_running && (localIsProcessing || daemons.is_processing_batch)) {
          setLocalIsProcessing(false);
          if (res.last_run?.success) {
            playSuccessFanfare();
            setJustFinished(true);
            setJustFailed(null);
            if (onRefresh) onRefresh();
          } else if (res.last_run?.success === false) {
            setJustFailed(res.last_run?.error || 'El proceso finalizó con advertencias o error');
          }
        }
      } catch {}
    };

    if (isEffectivelyProcessing) {
      pollLogs();
      timer = setInterval(pollLogs, 900);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isEffectivelyProcessing, localIsProcessing, daemons.is_processing_batch]);

  // Cronómetro de duración de la tarea actual
  useEffect(() => {
    let interval = null;
    if (isEffectivelyProcessing) {
      interval = setInterval(() => {
        setProcessingDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setProcessingDuration(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isEffectivelyProcessing]);

  // Auto-scroll del mini terminal de logs cuando ingresan nuevas líneas
  useEffect(() => {
    if (logsTerminalRef.current) {
      logsTerminalRef.current.scrollTop = logsTerminalRef.current.scrollHeight;
    }
  }, [pipelineData?.logs]);

  const formatDuration = (totalSecs) => {
    const m = Math.floor(totalSecs / 60).toString().padStart(2, '0');
    const s = (totalSecs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const formatCountdown = (totalSecs) => {
    if (totalSecs === null || totalSecs === undefined) return '--:--';
    if (totalSecs <= 0) return '00:00 (Rotando lote...)';
    const m = Math.floor(totalSecs / 60).toString().padStart(2, '0');
    const s = (totalSecs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const progressPercent = localSeconds !== null && localSeconds !== undefined
    ? Math.min(100, Math.max(0, Math.round(((900 - localSeconds) / 900) * 100)))
    : 0;

  // Respuesta táctil auditiva sutil sintetizada mediante Web Audio API
  const playTactileClick = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(360, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.025);
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.025);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.03);
    } catch {}
  };

  // Sonido de inicio de ignición de pipeline en GPU
  const playStartChime = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(392, now); // G4
      osc.frequency.exponentialRampToValueAtTime(784, now + 0.14); // G5
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.17);
    } catch {}
  };

  // Fanfarria triunfal de finalización exitosa (acorde mayor ascendente C-E-G-C)
  const playSuccessFanfare = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const chords = [523.25, 659.25, 783.99, 1046.5];
      chords.forEach((freq, idx) => {
        const t = ctx.currentTime + idx * 0.07;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, t);
        gain.gain.setValueAtTime(0.06, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.26);
      });
    } catch {}
  };

  // Manejador centralizado con feedback visual y háptico garantizado
  const handleAction = async (actionId, fn, fallbackSuccessText) => {
    playTactileClick();
    setLoadingAction(actionId);
    setActionMessage(null);
    try {
      const res = await fn();
      setSuccessAction(actionId);
      setActionMessage({
        type: 'success',
        text: res?.message || fallbackSuccessText || 'Operación completada con éxito'
      });
      setTimeout(() => {
        setSuccessAction((curr) => (curr === actionId ? null : curr));
      }, 2000);
      if (onRefresh) onRefresh();
    } catch (err) {
      setActionMessage({
        type: 'error',
        text: err?.message || 'Error al ejecutar la acción'
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleToggleRecorder = () => {
    handleAction(
      'recorder', 
      toggleRecorder, 
      recorderActive ? 'Grabador pausado' : 'Grabador conectado a Discord'
    );
  };

  const handleToggleWatcher = () => {
    handleAction(
      'watcher', 
      toggleWatcher, 
      watcherActive ? 'Vigilante IA pausado' : 'Vigilante IA iniciado'
    );
  };

  const handleToggleBoth = (activate) => {
    handleAction(
      activate ? 'both-start' : 'both-pause',
      async () => {
        if (activate) {
          if (!recorderActive) await toggleRecorder();
          if (!watcherActive) await toggleWatcher();
          return { message: 'Grabador y Vigilante IA activados correctamente' };
        } else {
          if (recorderActive) await toggleRecorder();
          if (watcherActive) await toggleWatcher();
          return { message: 'Grabador y Vigilante IA pausados' };
        }
      }
    );
  };

  const getStepStatus = (stepIndex) => {
    // 1: VAD, 2: Transcripción CUDA, 3: IA Perfilado, 4: SQLite
    if (!isEffectivelyProcessing && justFinished) return 'completed';
    if (!isEffectivelyProcessing) return 'idle';

    const stage = pipelineData?.stage || 'init';
    const stageMap = {
      init: 1,
      vad: 1,
      overlap: 1,
      stt: 2,
      curation: 3,
      profiling: 3,
      sync: 4,
      completed: 5,
    };

    const currentStageNum = stageMap[stage] || 1;
    if (currentStageNum > stepIndex) return 'completed';
    if (currentStageNum === stepIndex) return 'active';
    return 'pending';
  };

  const handleProcessAll = async () => {
    playStartChime();
    setJustFinished(false);
    setJustFailed(null);
    setLocalIsProcessing(true);
    setProcessingDuration(0);

    // Consulta inicial inmediata para activar panel
    fetchPipelineLogs(30).then((logs) => setPipelineData(logs)).catch(() => {});

    await handleAction('process-all', triggerProcessAll, 'Procesamiento en lote iniciado en GPU');

    fetchPipelineLogs(30).then((logs) => setPipelineData(logs)).catch(() => {});
  };

  const handleRefresh = () => {
    playTactileClick();
    setLoadingAction('refresh');
    if (onRefresh) {
      Promise.resolve(onRefresh()).finally(() => {
        setSuccessAction('refresh');
        setTimeout(() => {
          setSuccessAction((curr) => (curr === 'refresh' ? null : curr));
          setLoadingAction(null);
        }, 500);
      });
    } else {
      setLoadingAction(null);
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
          onClick={handleRefresh}
          disabled={loadingAction === 'refresh'}
          className="btn-secondary p-2 rounded-xs"
          title="Actualizar métricas"
        >
          {successAction === 'refresh' ? (
            <Check size={16} className="text-emerald-400" />
          ) : (
            <RotateCw size={16} className={loadingAction === 'refresh' ? "animate-spin text-indigo-400" : ""} />
          )}
        </button>
      </div>

      {/* Alerta de confirmación o error de acción */}
      {actionMessage && (
        <div className={`p-3 rounded-xs border text-xs flex items-center justify-between animate-in fade-in slide-in-from-top-1 ${
          actionMessage.type === 'error'
            ? 'bg-rose-950/60 border-rose-800 text-rose-200'
            : 'bg-emerald-950/50 border-emerald-800 text-emerald-200'
        }`}>
          <div className="flex items-center space-x-2">
            {actionMessage.type === 'error' ? (
              <AlertCircle size={15} className="text-rose-400 shrink-0" />
            ) : (
              <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-slate-400 hover:text-white text-xs ml-4 font-bold p-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Widget Destacado de Procesamiento Automático de Lotes (15m) */}
      <div className="bg-dark-900 border border-dark-700 rounded-xs p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-dark-700/60 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xs bg-indigo-950/70 text-indigo-400 border border-indigo-800/50 shadow-xs">
              <Clock size={18} className={nextProc?.is_automatic ? "animate-pulse" : ""} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="font-semibold text-slate-100 text-sm tracking-tight">
                  Procesamiento Automático de Lotes
                </h2>
                <span className="text-[10px] px-1.5 py-0.5 rounded-xs bg-dark-800 text-slate-400 border border-dark-700 font-mono">
                  15 min
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Rotación continua sin cortar la llamada de Discord. GPU faster-whisper procesa al rotar cada bloque.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {nextProc?.is_automatic ? (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xs bg-emerald-950/70 border border-emerald-700/60 text-emerald-300 text-xs font-medium">
                <span className="w-2 h-2 rounded-none bg-emerald-400 animate-ping"></span>
                <span>Ciclo Automático Activo</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xs bg-amber-950/60 border border-amber-800/60 text-amber-300 text-xs font-medium">
                <AlertCircle size={12} />
                <span>Ciclo Pausado</span>
              </span>
            )}
          </div>
        </div>

        {/* Cuerpo del widget: Countdown y Barra de Progreso */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          {/* Columna Countdown Principal */}
          <div className="md:col-span-2 p-4 rounded-xs bg-dark-850 border border-dark-700/80 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400 flex items-center space-x-1.5">
                <RotateCw size={13} className={nextProc?.is_automatic ? "animate-spin text-indigo-400" : "text-slate-500"} />
                <span>Próxima Rotación y Procesado GPU:</span>
              </span>
              <span className="text-xs font-mono text-slate-400">
                {progressPercent}% transcurrido
              </span>
            </div>

            <div className="flex items-baseline space-x-3">
              <div className="text-3xl font-extrabold font-mono tracking-tight text-indigo-200">
                {formatCountdown(localSeconds)}
              </div>
              <span className="text-xs text-slate-400">
                {nextProc?.is_automatic ? "para ejecutar transcripción y perfiles" : "(Inicie Grabador y Vigilante para activar)"}
              </span>
            </div>

            {/* Barra de progreso visual con marcas de tiempo */}
            <div className="space-y-1">
              <div className="w-full bg-dark-800 rounded-none h-2 overflow-hidden border border-dark-700/50">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 via-cyan-500 to-emerald-400 transition-all duration-500"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>00:00 (Inicio sesión)</span>
                <span>07:30 (Mitad)</span>
                <span>15:00 (Rotación de audio y GPU)</span>
              </div>
            </div>

            {/* Sesión actual */}
            {nextProc?.active_session_id && (
              <div className="pt-1 flex items-center justify-between text-xs text-slate-400 border-t border-dark-750">
                <span>Sesión activa en disco:</span>
                <span className="font-mono text-indigo-300 font-semibold bg-dark-900 px-2 py-0.5 rounded-xs border border-dark-700">
                  {nextProc.active_session_id}
                </span>
              </div>
            )}
          </div>

          {/* Columna de Estado / Resumen */}
          <div className="p-4 rounded-xs bg-dark-850 border border-dark-700/80 flex flex-col justify-between space-y-3">
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-300">
                ¿Cómo funciona el ciclo?
              </span>
              <ul className="text-[11px] text-slate-400 space-y-1.5 leading-relaxed">
                <li className="flex items-start space-x-1.5">
                  <span className="text-indigo-400 font-bold">•</span>
                  <span><strong>15m continuos:</strong> Los audios PCM de cada usuario se graban en canales aislados.</span>
                </li>
                <li className="flex items-start space-x-1.5">
                  <span className="text-cyan-400 font-bold">•</span>
                  <span><strong>Cero cortes:</strong> La rotación abre un nuevo archivo sin desconectar a nadie de Discord.</span>
                </li>
                <li className="flex items-start space-x-1.5">
                  <span className="text-emerald-400 font-bold">•</span>
                  <span><strong>GPU RTX 4070:</strong> faster-whisper transcribe el lote cerrado a {">"}15x tiempo real.</span>
                </li>
              </ul>
            </div>

            {isBatchRunning ? (
              <div className="p-2 rounded-xs bg-indigo-950/80 border border-indigo-700/70 text-indigo-300 text-xs flex items-center space-x-2">
                <RotateCw size={13} className="animate-spin text-indigo-400 shrink-0" />
                <span className="font-medium truncate">GPU transcribiendo lote anterior...</span>
              </div>
            ) : daemons.pending_sessions_count > 0 ? (
              <div className="p-2 rounded-xs bg-amber-950/50 border border-amber-800/60 text-amber-300 text-xs flex items-center justify-between">
                <span>{daemons.pending_sessions_count} sesiones pendientes</span>
                <button
                  onClick={handleProcessAll}
                  disabled={loadingAction !== null}
                  className="btn-primary text-[10px] px-2 py-0.5"
                >
                  Procesar
                </button>
              </div>
            ) : (
              <div className="p-2 rounded-xs bg-dark-800/70 border border-dark-700 text-slate-400 text-xs flex items-center space-x-1.5">
                <Check size={12} className="text-emerald-400" />
                <span>Todas las sesiones anteriores están procesadas</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Grid de Métricas de Hardware */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* GPU Util */}
        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <Zap size={14} className="text-indigo-400" />
              <span>Carga GPU</span>
            </span>
            <span className="font-mono text-slate-300">{gpuUtil}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">{gpuUtil}%</div>
          <div className="w-full bg-dark-800 rounded-none h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-none transition-all duration-300 ${
                gpuUtil > 80 ? "bg-amber-500" : "bg-indigo-500"
              }`}
              style={{ width: `${Math.min(gpuUtil, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500 truncate">{gpuName}</div>
        </div>

        {/* VRAM RTX 4070 */}
        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 space-y-2">
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
          <div className="w-full bg-dark-800 rounded-none h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-none transition-all duration-300 ${
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
        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="flex items-center space-x-1.5 font-medium">
              <Cpu size={14} className="text-emerald-400" />
              <span>Procesador CPU</span>
            </span>
            <span className="font-mono text-slate-300">{cpuPercent}%</span>
          </div>
          <div className="text-xl font-bold text-slate-100">{cpuPercent}%</div>
          <div className="w-full bg-dark-800 rounded-none h-1.5 overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-none transition-all duration-300"
              style={{ width: `${Math.min(cpuPercent, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500">Uso total del sistema</div>
        </div>

        {/* RAM */}
        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 space-y-2">
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
          <div className="w-full bg-dark-800 rounded-none h-1.5 overflow-hidden">
            <div
              className="h-full bg-purple-500 rounded-none transition-all duration-300"
              style={{ width: `${Math.min(ramPercent, 100)}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-500">RAM disponible para modelos</div>
        </div>
      </div>

      {/* Panel de Control de Daemons */}
      <div className="bg-dark-900 border border-dark-700 rounded-xs p-5 shadow-sm space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-700/60 pb-3">
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
              disabled={loadingAction !== null}
              className="btn-emerald px-3.5 py-1.5 rounded-xs text-xs font-semibold space-x-1.5"
            >
              {loadingAction === 'both-start' ? (
                <>
                  <RotateCw size={13} className="animate-spin text-emerald-300" />
                  <span>Activando Ambos...</span>
                </>
              ) : successAction === 'both-start' ? (
                <>
                  <Check size={13} className="text-emerald-300" />
                  <span>¡Ambos Activados!</span>
                </>
              ) : (
                <>
                  <Play size={13} />
                  <span>Activar Ambos</span>
                </>
              )}
            </button>
            <button
              onClick={() => handleToggleBoth(false)}
              disabled={loadingAction !== null}
              className="btn-rose px-3.5 py-1.5 rounded-xs text-xs font-semibold space-x-1.5"
            >
              {loadingAction === 'both-pause' ? (
                <>
                  <RotateCw size={13} className="animate-spin text-rose-300" />
                  <span>Pausando Ambos...</span>
                </>
              ) : successAction === 'both-pause' ? (
                <>
                  <Check size={13} className="text-rose-300" />
                  <span>¡Ambos Pausados!</span>
                </>
              ) : (
                <>
                  <Square size={13} />
                  <span>Pausar Ambos</span>
                </>
              )}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Tarjeta Grabador Discord */}
          <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className={`p-2 rounded-xs ${recorderActive ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50' : 'bg-dark-800 text-slate-500 border border-dark-700'}`}>
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
                <span className={`text-xs px-2.5 py-0.5 rounded-xs font-medium border ${
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
              disabled={loadingAction !== null}
              className={`w-full py-2.5 px-3 rounded-xs text-xs font-semibold space-x-2 ${
                recorderActive ? 'btn-rose' : 'btn-emerald'
              }`}
            >
              {loadingAction === 'recorder' ? (
                <>
                  <RotateCw size={14} className="animate-spin" />
                  <span>{recorderActive ? 'Pausando Grabador...' : 'Iniciando Grabador...'}</span>
                </>
              ) : successAction === 'recorder' ? (
                <>
                  <Check size={14} className="text-emerald-300" />
                  <span>{recorderActive ? '¡Grabador Detenido!' : '¡Grabador Conectado!'}</span>
                </>
              ) : recorderActive ? (
                <>
                  <Square size={14} />
                  <span>Pausar Escucha Discord</span>
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
          <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className={`p-2 rounded-xs ${watcherActive ? 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/50' : 'bg-dark-800 text-slate-500 border border-dark-700'}`}>
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
                <span className={`text-xs px-2.5 py-0.5 rounded-xs font-medium border ${
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
              disabled={loadingAction !== null}
              className={`w-full py-2.5 px-3 rounded-xs text-xs font-semibold space-x-2 ${
                watcherActive ? 'btn-rose' : 'btn-cyan'
              }`}
            >
              {loadingAction === 'watcher' ? (
                <>
                  <RotateCw size={14} className="animate-spin" />
                  <span>{watcherActive ? 'Deteniendo Vigilante...' : 'Iniciando Vigilante...'}</span>
                </>
              ) : successAction === 'watcher' ? (
                <>
                  <Check size={14} className="text-emerald-300" />
                  <span>{watcherActive ? '¡Vigilante Detenido!' : '¡Vigilante Activo!'}</span>
                </>
              ) : watcherActive ? (
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

        {/* Panel de Monitoreo de Procesamiento en Tiempo Real */}
        {isEffectivelyProcessing && (
          <div className="p-5 rounded-xs bg-indigo-950/20 border border-indigo-500/40 shadow-xl shadow-indigo-950/40 space-y-4 animate-in fade-in slide-in-from-top-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-indigo-900/40 pb-3">
              <div className="flex items-center space-x-2.5">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
                  <Zap size={14} className="text-indigo-400 animate-pulse" />
                  Procesando en GPU RTX 4070 (faster-whisper CUDA)
                </span>
                {pipelineData?.session_id && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-xs bg-indigo-900/40 text-indigo-300 border border-indigo-700/40 truncate max-w-xs">
                    {pipelineData.session_id}
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3 text-xs">
                <div className="flex items-center space-x-1.5 text-slate-300 font-mono bg-dark-900/70 px-2.5 py-1 rounded-xs border border-dark-700">
                  <Clock size={13} className="text-indigo-400" />
                  <span>{formatDuration(processingDuration)}</span>
                </div>
                {onOpenLogs && (
                  <button
                    onClick={onOpenLogs}
                    className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 transition-colors"
                  >
                    <Terminal size={13} />
                    <span>Ver Consola Completa</span>
                  </button>
                )}
              </div>
            </div>

            {/* Barra de progreso */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-300 font-medium flex items-center gap-1.5">
                  <RotateCw size={13} className="animate-spin text-indigo-400" />
                  {pipelineData?.current_task || 'Ejecutando pipeline de procesamiento...'}
                </span>
                <span className="font-mono font-bold text-indigo-400">
                  {pipelineData?.progress_percent || (localIsProcessing ? 15 : 0)}%
                </span>
              </div>
              <div className="w-full bg-dark-900 rounded-full h-2 overflow-hidden border border-indigo-900/50">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 transition-all duration-500 rounded-full"
                  style={{ width: `${Math.max(5, pipelineData?.progress_percent || (localIsProcessing ? 15 : 0))}%` }}
                />
              </div>
            </div>

            {/* Stepper de 4 fases */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 pt-1">
              {/* Fase 1: VAD */}
              {(() => {
                const s = getStepStatus(1);
                return (
                  <div className={`p-2.5 rounded-xs border transition-all ${
                    s === 'active' 
                      ? 'bg-indigo-900/40 border-indigo-400 text-indigo-200 shadow-sm shadow-indigo-500/20' 
                      : s === 'completed' 
                      ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-300' 
                      : 'bg-dark-900/40 border-dark-700/60 text-slate-500'
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <Mic size={15} className={s === 'active' ? 'text-indigo-400 animate-pulse' : s === 'completed' ? 'text-emerald-400' : 'text-slate-600'} />
                      {s === 'completed' ? (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      ) : s === 'active' ? (
                        <RotateCw size={14} className="animate-spin text-indigo-400" />
                      ) : (
                        <span className="text-[10px] font-mono text-slate-600">1</span>
                      )}
                    </div>
                    <div className="text-xs font-semibold">1. Silero VAD</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate">Detección y aislamiento</div>
                  </div>
                );
              })()}

              {/* Fase 2: faster-whisper CUDA */}
              {(() => {
                const s = getStepStatus(2);
                return (
                  <div className={`p-2.5 rounded-xs border transition-all ${
                    s === 'active' 
                      ? 'bg-indigo-900/40 border-indigo-400 text-indigo-200 shadow-sm shadow-indigo-500/20' 
                      : s === 'completed' 
                      ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-300' 
                      : 'bg-dark-900/40 border-dark-700/60 text-slate-500'
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <Cpu size={15} className={s === 'active' ? 'text-indigo-400 animate-pulse' : s === 'completed' ? 'text-emerald-400' : 'text-slate-600'} />
                      {s === 'completed' ? (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      ) : s === 'active' ? (
                        <RotateCw size={14} className="animate-spin text-indigo-400" />
                      ) : (
                        <span className="text-[10px] font-mono text-slate-600">2</span>
                      )}
                    </div>
                    <div className="text-xs font-semibold">2. faster-whisper</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate">Transcripción CUDA FP16</div>
                  </div>
                );
              })()}

              {/* Fase 3: Gemini / LLaMA */}
              {(() => {
                const s = getStepStatus(3);
                return (
                  <div className={`p-2.5 rounded-xs border transition-all ${
                    s === 'active' 
                      ? 'bg-indigo-900/40 border-indigo-400 text-indigo-200 shadow-sm shadow-indigo-500/20' 
                      : s === 'completed' 
                      ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-300' 
                      : 'bg-dark-900/40 border-dark-700/60 text-slate-500'
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <Brain size={15} className={s === 'active' ? 'text-indigo-400 animate-pulse' : s === 'completed' ? 'text-emerald-400' : 'text-slate-600'} />
                      {s === 'completed' ? (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      ) : s === 'active' ? (
                        <RotateCw size={14} className="animate-spin text-indigo-400" />
                      ) : (
                        <span className="text-[10px] font-mono text-slate-600">3</span>
                      )}
                    </div>
                    <div className="text-xs font-semibold">3. Gemini 2.5 Flash</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate">Curación y perfilado Big Five</div>
                  </div>
                );
              })()}

              {/* Fase 4: SQLite Sync */}
              {(() => {
                const s = getStepStatus(4);
                return (
                  <div className={`p-2.5 rounded-xs border transition-all ${
                    s === 'active' 
                      ? 'bg-indigo-900/40 border-indigo-400 text-indigo-200 shadow-sm shadow-indigo-500/20' 
                      : s === 'completed' 
                      ? 'bg-emerald-950/30 border-emerald-700/50 text-emerald-300' 
                      : 'bg-dark-900/40 border-dark-700/60 text-slate-500'
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <Database size={15} className={s === 'active' ? 'text-indigo-400 animate-pulse' : s === 'completed' ? 'text-emerald-400' : 'text-slate-600'} />
                      {s === 'completed' ? (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      ) : s === 'active' ? (
                        <RotateCw size={14} className="animate-spin text-indigo-400" />
                      ) : (
                        <span className="text-[10px] font-mono text-slate-600">4</span>
                      )}
                    </div>
                    <div className="text-xs font-semibold">4. Sincronización</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate">Base de datos y clones</div>
                  </div>
                );
              })()}
            </div>

            {/* Mini terminal de salida en vivo */}
            <div className="bg-dark-900/90 rounded-xs border border-dark-750 p-2.5 space-y-1">
              <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono border-b border-dark-800 pb-1 mb-1">
                <span className="flex items-center gap-1.5">
                  <Terminal size={12} className="text-indigo-400" />
                  Salida estándar en tiempo real
                </span>
                <span className="text-[10px] text-slate-500">Auto-scroll activo</span>
              </div>
              <div 
                ref={logsTerminalRef}
                className="max-h-28 overflow-y-auto font-mono text-[11px] text-slate-300 space-y-0.5 scrollbar-thin select-text"
              >
                {pipelineData?.logs && pipelineData.logs.length > 0 ? (
                  pipelineData.logs.slice(-15).map((logLine, idx) => (
                    <div key={idx} className="leading-tight text-slate-400 hover:text-slate-200">
                      <span className="text-slate-600 mr-1.5">&gt;</span>
                      {logLine}
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 italic">Esperando primeras líneas de salida del proceso...</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tarjeta de éxito tras completar el proceso */}
        {!isEffectivelyProcessing && justFinished && (
          <div className="p-4 rounded-xs bg-emerald-950/30 border border-emerald-600/50 flex items-center justify-between animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-xs bg-emerald-900/50 text-emerald-400 border border-emerald-700/50">
                <CheckCircle2 size={20} />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-emerald-200">
                  ¡Procesamiento Completado Exitosamente!
                </h4>
                <p className="text-xs text-emerald-400/80">
                  Las transcripciones con faster-whisper, la extracción de muestras de voz y la actualización de perfiles con Gemini finalizaron correctamente.
                </p>
              </div>
            </div>
            <button
              onClick={() => setJustFinished(false)}
              className="btn-secondary text-xs px-3 py-1.5 text-slate-300 hover:text-white"
            >
              Entendido
            </button>
          </div>
        )}

        {/* Tarjeta de alerta si falló */}
        {!isEffectivelyProcessing && justFailed && (
          <div className="p-4 rounded-xs bg-rose-950/30 border border-rose-600/50 flex items-center justify-between animate-in fade-in slide-in-from-top-2">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-xs bg-rose-950/60 text-rose-400 border border-rose-800/50">
                <AlertCircle size={20} />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-rose-200">
                  Advertencia o Error en el Procesamiento
                </h4>
                <p className="text-xs text-rose-400/80 max-w-2xl font-mono">
                  {justFailed}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {onOpenLogs && (
                <button
                  onClick={onOpenLogs}
                  className="btn-rose text-xs px-3 py-1.5"
                >
                  Ver Logs
                </button>
              )}
              <button
                onClick={() => setJustFailed(null)}
                className="btn-secondary text-xs px-3 py-1.5 text-slate-300 hover:text-white"
              >
                Cerrar
              </button>
            </div>
          </div>
        )}

        {/* Sección de Disparo Manual de Procesamiento por Lote */}
        <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
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
            disabled={loadingAction !== null || isBatchRunning}
            className={`px-5 py-2.5 rounded-xs text-xs font-semibold whitespace-nowrap space-x-2 ${
              isBatchRunning
                ? 'btn-secondary opacity-80 cursor-wait text-indigo-300 border-indigo-700/60'
                : 'btn-primary'
            }`}
          >
            {loadingAction === 'process-all' ? (
              <>
                <RotateCw size={14} className="animate-spin" />
                <span>Lanzando Pipeline...</span>
              </>
            ) : successAction === 'process-all' ? (
              <>
                <Check size={14} className="text-white" />
                <span>¡Lote Lanzado con Éxito!</span>
              </>
            ) : isBatchRunning ? (
              <>
                <RotateCw size={14} className="animate-spin text-indigo-300" />
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
