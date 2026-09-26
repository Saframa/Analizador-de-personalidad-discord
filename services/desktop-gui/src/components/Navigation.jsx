import React from 'react';
import { 
  BarChart3, 
  Users, 
  Cpu, 
  Volume2, 
  Menu, 
  X, 
  Radio, 
  HardDrive 
} from 'lucide-react';

export default function Navigation({ 
  currentTab, 
  onSelectTab, 
  isMenuOpen, 
  onToggleMenu, 
  status 
}) {
  const tabs = [
    { id: 'stats', label: 'Estadísticas Globales', icon: BarChart3 },
    { id: 'users', label: 'Amigos y Perfiles', icon: Users },
    { id: 'hardware', label: 'Hardware y Vigilante', icon: Cpu },
    { id: 'tts', label: 'Estudio de Voz TTS', icon: Volume2 },
  ];

  const recorderActive = status?.daemons?.recorder?.active;
  const watcherActive = status?.daemons?.watcher?.active;
  const isBatchRunning = status?.daemons?.is_processing_batch;

  return (
    <>
      {/* Header Superior */}
      <header className="h-14 border-b border-dark-700 bg-dark-900 px-4 flex items-center justify-between z-30 select-none">
        <div className="flex items-center space-x-3">
          <button
            onClick={onToggleMenu}
            className="p-2 rounded-lg bg-dark-800 hover:bg-dark-700 text-slate-300 hover:text-white transition-colors"
            title="Abrir menú"
          >
            {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-100 tracking-wide text-sm md:text-base">
              Discord Twin Profiler
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-dark-800 text-slate-400 border border-dark-700">
              Desktop
            </span>
          </div>
        </div>

        {/* Indicadores rápidos de hardware y estado */}
        <div className="flex items-center space-x-3 text-xs">
          {/* Grabador Status */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-dark-850 border border-dark-700">
            <Radio size={13} className={recorderActive ? "text-emerald-500 animate-pulse" : "text-slate-500"} />
            <span className={recorderActive ? "text-emerald-400 font-medium" : "text-slate-400"}>
              {recorderActive ? "Grabando" : "Escucha Pausada"}
            </span>
          </div>

          {/* Vigilante Status */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-dark-850 border border-dark-700">
            <HardDrive size={13} className={watcherActive ? "text-cyan-500" : "text-slate-500"} />
            <span className={watcherActive ? "text-cyan-400 font-medium" : "text-slate-400"}>
              {watcherActive ? "Vigilante Activo" : "Procesado Pausado"}
            </span>
          </div>

          {/* Lote GPU indicator */}
          {isBatchRunning && (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-indigo-950/80 border border-indigo-700/60 text-indigo-300">
              <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
              <span>Procesando Lote GPU</span>
            </div>
          )}

          {/* GPU VRAM Badge */}
          {status?.hardware?.gpu?.available && (
            <div className="px-2.5 py-1 rounded bg-dark-800 border border-dark-700 text-slate-300">
              <span className="text-slate-500">VRAM:</span> {Math.round(status.hardware.gpu.vram_used_mb / 1024 * 10) / 10} / 12 GB
            </div>
          )}
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
                className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm transition-all ${
                  active
                    ? "bg-dark-700/90 text-white font-medium border border-dark-600 shadow-sm"
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
