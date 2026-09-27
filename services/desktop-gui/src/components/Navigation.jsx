import React from 'react';
import { 
  BarChart3, 
  Users, 
  Share2,
  Cpu, 
  Volume2, 
  Menu, 
  X, 
  Radio, 
  HardDrive,
  Clock,
  Terminal 
} from 'lucide-react';

export default function Navigation({ 
  currentTab, 
  onSelectTab, 
  isMenuOpen, 
  onToggleMenu, 
  status,
  onOpenLogs
}) {
  const tabs = [
    { id: 'stats', label: 'Estadísticas Globales', icon: BarChart3 },
    { id: 'users', label: 'Amigos y Perfiles', icon: Users },
    { id: 'social', label: 'Dinámica Social', icon: Share2 },
    { id: 'channels', label: 'Canales de Voz', icon: Radio },
    { id: 'hardware', label: 'Hardware y Vigilante', icon: Cpu },
    { id: 'tts', label: 'Estudio de Voz TTS', icon: Volume2 },
  ];

  const recorderActive = status?.daemons?.recorder?.active;
  const watcherActive = status?.daemons?.watcher?.active;
  const isBatchRunning = status?.daemons?.is_processing_batch;
  const nextProc = status?.daemons?.next_processing;

  const [localSeconds, setLocalSeconds] = React.useState(nextProc?.seconds_remaining);

  React.useEffect(() => {
    if (nextProc?.seconds_remaining !== undefined && nextProc?.seconds_remaining !== null) {
      setLocalSeconds(nextProc.seconds_remaining);
    }
  }, [nextProc?.seconds_remaining]);

  React.useEffect(() => {
    if (!nextProc?.is_automatic || localSeconds === null || localSeconds === undefined) return;
    const interval = setInterval(() => {
      setLocalSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [nextProc?.is_automatic, localSeconds !== null]);

  const formatCountdown = (totalSecs) => {
    if (totalSecs === null || totalSecs === undefined) return '--:--';
    if (totalSecs <= 0) return 'Rotando...';
    const m = Math.floor(totalSecs / 60).toString().padStart(2, '0');
    const s = (totalSecs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <>
      {/* Header Superior */}
      <header className="h-14 border-b border-dark-700 bg-dark-900 px-4 flex items-center justify-between z-30 select-none">
        <div className="flex items-center space-x-3">
          <button
            onClick={onToggleMenu}
            className="btn-tactile p-2 rounded-xs bg-dark-800 hover:bg-dark-750 text-slate-300 hover:text-white border border-dark-700 shadow-sm"
            title="Abrir menú"
          >
            {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-100 tracking-wide text-sm md:text-base">
              Discord Twin Profiler
            </span>
            <span className="text-xs px-2 py-0.5 rounded-xs bg-dark-800 text-slate-400 border border-dark-700">
              Desktop
            </span>
          </div>
        </div>

        {/* Indicadores rápidos de hardware y estado */}
        <div className="flex items-center space-x-2 text-xs">
          {/* Próximo Procesamiento Automático Countdown */}
          {nextProc?.is_automatic && (
            <button
              onClick={() => onSelectTab('hardware')}
              className="btn-tactile hidden lg:flex items-center space-x-2 px-3 py-1 rounded-xs bg-gradient-to-r from-dark-850 to-indigo-950/40 border border-indigo-500/40 text-indigo-300 shadow-[0_0_12px_rgba(99,102,241,0.15)] hover:border-indigo-400/70"
              title="Ver detalles de procesamiento automático en Hardware"
            >
              <Clock size={13} className="text-indigo-400 animate-pulse" />
              <span className="text-slate-400 font-mono text-xs">
                Próximo lote en: <strong className="text-indigo-200 font-bold ml-1">{formatCountdown(localSeconds)}</strong>
              </span>
            </button>
          )}

          {/* Grabador Status */}
          <button
            onClick={() => onSelectTab('channels')}
            className="btn-tactile hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-xs bg-dark-850 hover:bg-dark-800 border border-dark-700 cursor-pointer"
            title="Ver canales de voz de Discord"
          >
            <Radio size={13} className={recorderActive ? "text-emerald-500 animate-pulse" : "text-slate-500"} />
            <span className={recorderActive ? "text-emerald-400 font-medium" : "text-slate-400"}>
              {recorderActive ? "Grabando" : "Escucha Pausada"}
            </span>
          </button>

          {/* Vigilante Status */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-xs bg-dark-850 border border-dark-700">
            <HardDrive size={13} className={watcherActive ? "text-cyan-500" : "text-slate-500"} />
            <span className={watcherActive ? "text-cyan-400 font-medium" : "text-slate-400"}>
              {watcherActive ? "Vigilante Activo" : "Procesado Pausado"}
            </span>
          </div>

          {/* Lote GPU indicator */}
          {isBatchRunning && (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-xs bg-indigo-950/80 border border-indigo-700/60 text-indigo-300">
              <span className="w-1.5 h-1.5 bg-indigo-400 animate-ping"></span>
              <span>Procesando Lote GPU</span>
            </div>
          )}

          {/* GPU VRAM Badge */}
          {status?.hardware?.gpu?.available && (
            <div className="px-2.5 py-1 rounded-xs bg-dark-800 border border-dark-700 text-slate-300">
              <span className="text-slate-500">VRAM:</span> {Math.round(status.hardware.gpu.vram_used_mb / 1024 * 10) / 10} / 12 GB
            </div>
          )}

          {/* Botón Consola de Logs */}
          <button
            onClick={onOpenLogs}
            className={`btn-tactile flex items-center space-x-1.5 px-2.5 py-1 rounded-xs border transition cursor-pointer ${
              isBatchRunning
                ? "bg-indigo-950 text-indigo-300 border-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.25)]"
                : "bg-dark-850 hover:bg-dark-800 text-slate-300 border-dark-700"
            }`}
            title="Abrir monitor de logs del pipeline en tiempo real"
          >
            <Terminal size={13} className={isBatchRunning ? "text-indigo-400 animate-pulse" : "text-slate-400"} />
            <span>Logs</span>
            {isBatchRunning && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping ml-0.5" />
            )}
          </button>
        </div>
      </header>

      {/* Menú Lateral Desplegable / Sidebar */}
      <aside
        className={`fixed top-14 left-0 bottom-0 w-64 bg-dark-900 border-r border-dark-700 z-40 transform transition-transform duration-200 ease-in-out flex flex-col justify-between ${
          isMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-3 space-y-1">
          <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Navegación
          </div>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  onSelectTab(tab.id);
                  onToggleMenu();
                }}
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xs text-sm transition-all ${
                  active
                    ? "bg-dark-750 text-white font-medium border border-dark-600 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-dark-800/60"
                }`}
              >
                <Icon size={18} className={active ? "text-indigo-400" : "text-slate-400"} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Footer del sidebar */}
        <div className="p-4 border-t border-dark-800 text-xs text-slate-500 space-y-1">
          <div className="flex justify-between">
            <span>Motor STT:</span>
            <span className="text-slate-400">faster-whisper (CUDA)</span>
          </div>
          <div className="flex justify-between">
            <span>Síntesis TTS:</span>
            <span className="text-slate-400">F5-TTS Spanish</span>
          </div>
          <div className="flex justify-between">
            <span>Perfilador:</span>
            <span className="text-slate-400">Gemini / LLaMA 3.3</span>
          </div>
        </div>
      </aside>

      {/* Backdrop para cerrar menú al tocar afuera en pantallas chicas */}
      {isMenuOpen && (
        <div
          onClick={onToggleMenu}
          className="fixed inset-0 bg-black/60 z-30 transition-opacity backdrop-blur-xs"
        />
      )}
    </>
  );
}
