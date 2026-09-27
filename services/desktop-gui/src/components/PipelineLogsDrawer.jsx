import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, X, RotateCw, Trash2, Copy, Check, 
  ArrowDownCircle, Activity, Sparkles, Play, ShieldAlert
} from 'lucide-react';
import { fetchPipelineLogs, clearPipelineLogs, triggerProcessAll } from '../api';

export default function PipelineLogsDrawer({ isOpen, onClose, isProcessingGlobal }) {
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentTask, setCurrentTask] = useState(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const terminalEndRef = useRef(null);

  const loadLogs = async () => {
    try {
      const data = await fetchPipelineLogs(200);
      setLogs(data.logs || []);
      setIsRunning(data.is_running || false);
      setCurrentTask(data.current_task || null);
    } catch (err) {
      console.error("Error al cargar logs del pipeline:", err);
    }
  };

  useEffect(() => {
    if (!isOpen && !isRunning && !isProcessingGlobal) return;
    loadLogs();
    const interval = setInterval(loadLogs, 1500);
    return () => clearInterval(interval);
  }, [isOpen, isRunning, isProcessingGlobal]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleClear = async () => {
    try {
      await clearPipelineLogs();
      setLogs([]);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleStartProcess = async () => {
    setLoading(true);
    try {
      await triggerProcessAll();
      await loadLogs();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const formatLine = (line, index) => {
    let colorClass = "text-slate-300";
    if (line.includes("[ERROR]") || line.includes("🚨") || line.includes("CUARENTENA") || line.includes("failed")) {
      colorClass = "text-rose-400 font-semibold";
    } else if (line.includes("✅") || line.includes("COMPLETADA") || line.includes("exitosamente")) {
      colorClass = "text-emerald-400";
    } else if (line.includes("⚠️") || line.includes("[WARN]")) {
      colorClass = "text-amber-400";
    } else if (line.includes("🎙️") || line.includes("faster-whisper") || line.includes("STT")) {
      colorClass = "text-indigo-300";
    } else if (line.includes("Silero VAD") || line.includes("VAD")) {
      colorClass = "text-cyan-300";
    } else if (line.includes("PROCESANDO SESION")) {
      colorClass = "text-purple-300 font-bold bg-purple-950/30 px-1 py-0.5 rounded";
    } else if (line.includes("Gemini") || line.includes("Perfil")) {
      colorClass = "text-yellow-300";
    }

    return (
      <div key={index} className={`font-mono text-xs py-0.5 leading-relaxed break-all select-text ${colorClass}`}>
        {line}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm transition-all duration-300">
      <div className="w-full max-w-6xl h-[70vh] bg-slate-950 border-t border-x border-slate-800 rounded-t-2xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
        {/* Barra superior de la consola */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-900 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
              <Terminal size={18} />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-semibold text-white tracking-wide">Monitor de Pipeline en Vivo</h3>
                <span className={`inline-flex items-center space-x-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${
                  isRunning 
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' 
                    : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'}`} />
                  <span>{isRunning ? 'Procesando en GPU' : 'Inactivo'}</span>
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {currentTask || "Esperando nuevas llamadas o procesamiento manual..."}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {!isRunning && (
              <button
                onClick={handleStartProcess}
                disabled={loading}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium shadow-sm transition disabled:opacity-50"
              >
                <Play size={13} />
                <span>{loading ? 'Iniciando...' : 'Procesar Sesiones'}</span>
              </button>
            )}

            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs transition border ${
                autoScroll 
                  ? 'bg-indigo-950/60 text-indigo-300 border-indigo-700/50' 
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
              title="Alternar auto-desplazamiento hacia el último log"
            >
              <ArrowDownCircle size={13} />
              <span>Auto-scroll</span>
            </button>

            <button
              onClick={handleCopy}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
              title="Copiar registros"
            >
              {copied ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
            </button>

            <button
              onClick={handleClear}
              className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
              title="Limpiar pantalla"
            >
              <Trash2 size={16} />
            </button>

            <button
              onClick={loadLogs}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
              title="Refrescar"
            >
              <RotateCw size={16} />
            </button>

            <div className="h-4 w-px bg-slate-700 mx-1" />

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
              title="Cerrar consola"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Banner de tarea activa si está corriendo */}
        {isRunning && (
          <div className="bg-gradient-to-r from-indigo-950/80 via-purple-950/60 to-slate-900 border-b border-indigo-800/40 px-5 py-2 flex items-center justify-between text-xs text-indigo-200">
            <div className="flex items-center space-x-2.5">
              <Activity size={14} className="text-indigo-400 animate-spin" />
              <span className="font-medium text-white">{currentTask || "Procesando en segundo plano..."}</span>
            </div>
            <span className="text-[11px] text-indigo-300/80 bg-indigo-900/40 px-2 py-0.5 rounded border border-indigo-700/30">
              NVIDIA RTX 4070 (FP16)
            </span>
          </div>
        )}

        {/* Cuerpo de la terminal de logs */}
        <div className="flex-1 bg-black/90 p-4 overflow-y-auto space-y-0.5 select-text scrollbar-thin scrollbar-thumb-slate-800">
          {logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs space-y-2">
              <Terminal size={28} className="text-slate-700" />
              <p>No hay registros recientes en el búfer de ejecución.</p>
              <p className="text-[11px] text-slate-600">Los eventos de transcripción y perfilado aparecerán aquí en vivo.</p>
            </div>
          ) : (
            logs.map((line, idx) => formatLine(line, idx))
          )}
          <div ref={terminalEndRef} />
        </div>

        {/* Barra de pie */}
        <div className="px-5 py-2 bg-slate-900/90 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <span>{logs.length} líneas registradas</span>
          <span className="font-mono">storage/logs/pipeline.log</span>
        </div>
      </div>
    </div>
  );
}
