import React, { useState, useEffect, useRef } from 'react';
import { 
  Radio, 
  RotateCw, 
  Users, 
  CheckCircle2, 
  AlertCircle, 
  Square, 
  Play, 
  Volume2, 
  Mic, 
  MicOff, 
  Headphones, 
  ShieldAlert, 
  Check, 
  Search, 
  Server,
  Zap,
  Info
} from 'lucide-react';
import { fetchDiscordChannels, joinDiscordChannel, leaveDiscordChannel } from '../api';

export default function VoiceChannelsView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all'); // 'all' | 'ready' | 'active' | 'empty'

  const [loadingAction, setLoadingAction] = useState(null); // channelId or 'leave'
  const [successAction, setSuccessAction] = useState(null);
  const [feedbackMessage, setFeedbackMessage] = useState(null);

  // Web Audio feedback táctil
  const playTactileClick = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(380, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(120, ctx.currentTime + 0.025);
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.025);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.03);
    } catch {
      // Ignorar si el audio context no está disponible
    }
  };

  const loadChannels = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const res = await fetchDiscordChannels();
      setData(res);
      setError(null);
    } catch (err) {
      console.error('Error fetching discord channels:', err);
      setError(err.message || 'No se pudo comunicar con el bot de Discord');
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  };

  useEffect(() => {
    loadChannels();
    const interval = setInterval(() => {
      loadChannels(false);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const handleJoin = async (channel) => {
    playTactileClick();
    setLoadingAction(channel.id);
    setFeedbackMessage(null);
    try {
      await joinDiscordChannel(channel.id);
      setSuccessAction(channel.id);
      setFeedbackMessage({
        type: 'success',
        text: `Bot conectado exitosamente al canal "${channel.name}". Grabando sesión.`
      });
      setTimeout(() => setSuccessAction(null), 1800);
      await loadChannels(false);
    } catch (err) {
      setFeedbackMessage({
        type: 'error',
        text: err.message || `No se pudo conectar a "${channel.name}"`
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const handleLeave = async () => {
    playTactileClick();
    setLoadingAction('leave');
    setFeedbackMessage(null);
    try {
      await leaveDiscordChannel();
      setSuccessAction('leave');
      setFeedbackMessage({
        type: 'success',
        text: 'Bot desconectado del canal de voz.'
      });
      setTimeout(() => setSuccessAction(null), 1800);
      await loadChannels(false);
    } catch (err) {
      setFeedbackMessage({
        type: 'error',
        text: err.message || 'Error al desconectar el bot'
      });
    } finally {
      setLoadingAction(null);
    }
  };

  const guilds = data?.guilds || [];
  const botActive = data?.bot_active ?? false;
  const connectedChannelId = data?.connectedChannelId || null;
  const isRecording = data?.isRecording ?? false;
  const minUsersRequired = data?.minUsersRequired ?? 2;
  const botUser = data?.botUser;

  // Filtrado de canales
  const filterChannel = (channel) => {
    const matchesSearch = 
      channel.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (channel.category && channel.category.toLowerCase().includes(searchQuery.toLowerCase())) ||
      channel.members.some(m => 
        (m.displayName || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.username || '').toLowerCase().includes(searchQuery.toLowerCase())
      );

    if (!matchesSearch) return false;

    if (filterType === 'ready') return channel.meetsConditions && !channel.isConnected;
    if (filterType === 'active') return channel.isConnected;
    if (filterType === 'empty') return channel.humanCount === 0;
    return true; // 'all'
  };

  // Calcular estadísticas rápidas
  const allChannels = guilds.flatMap(g => g.channels || []);
  const readyChannelsCount = allChannels.filter(c => c.meetsConditions).length;
  const activeUsersCount = allChannels.reduce((acc, c) => acc + (c.humanCount || 0), 0);
  const currentConnectedChannel = allChannels.find(c => c.id === connectedChannelId);

  return (
    <div className="h-full flex flex-col overflow-y-auto px-4 md:px-8 py-6 space-y-6">
      {/* Encabezado Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-dark-750 pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-indigo-950/60 border border-indigo-700/50 rounded-xs text-indigo-400">
              <Radio size={22} className={isRecording ? "animate-pulse text-emerald-400" : "text-indigo-400"} />
            </div>
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                Canales de Voz de Discord
                {botUser && (
                  <span className="text-xs font-mono font-normal px-2 py-0.5 rounded-xs bg-dark-800 text-slate-400 border border-dark-700">
                    {botUser.tag}
                  </span>
                )}
              </h1>
              <p className="text-xs md:text-sm text-slate-400">
                Selecciona manualmente a qué canal unir el bot o déjalo en automático según las condiciones de presencia.
              </p>
            </div>
          </div>
        </div>

        {/* Acciones del encabezado */}
        <div className="flex items-center gap-2.5 self-start md:self-auto">
          {connectedChannelId && (
            <button
              onClick={handleLeave}
              disabled={loadingAction === 'leave'}
              className="btn-rose px-3.5 py-2 rounded-xs text-xs flex items-center space-x-2"
              title="Desconectar bot del canal actual"
            >
              {loadingAction === 'leave' ? (
                <RotateCw size={14} className="animate-spin" />
              ) : successAction === 'leave' ? (
                <Check size={14} className="text-white" />
              ) : (
                <Square size={14} />
              )}
              <span>Desconectar Bot</span>
            </button>
          )}

          <button
            onClick={() => loadChannels(true)}
            disabled={refreshing}
            className="btn-secondary px-3.5 py-2 rounded-xs text-xs flex items-center space-x-2"
            title="Refrescar lista de canales en tiempo real"
          >
            <RotateCw size={14} className={refreshing ? "animate-spin text-indigo-400" : "text-slate-400"} />
            <span>Actualizar</span>
          </button>
        </div>
      </div>

      {/* Alerta de Bot Detenido si no está activo */}
      {!botActive && (
        <div className="p-4 rounded-xs bg-amber-950/40 border border-amber-800/60 text-amber-200 text-xs md:text-sm flex items-start space-x-3">
          <AlertCircle size={18} className="text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-amber-300">El Grabador de Discord no está en ejecución</span>
            <p className="text-amber-200/80">
              Para ver los canales de voz en vivo y permitir que el bot se una, inicia el grabador desde la pestaña <strong>Hardware y Vigilante</strong>.
            </p>
          </div>
        </div>
      )}

      {/* Feedback contextual de acciones */}
      {feedbackMessage && (
        <div className={`p-3.5 rounded-xs text-xs flex items-center justify-between transition-all ${
          feedbackMessage.type === 'success' 
            ? 'bg-emerald-950/60 border border-emerald-700/60 text-emerald-200' 
            : 'bg-rose-950/60 border border-rose-700/60 text-rose-200'
        }`}>
          <div className="flex items-center space-x-2">
            {feedbackMessage.type === 'success' ? (
              <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle size={16} className="text-rose-400 shrink-0" />
            )}
            <span>{feedbackMessage.text}</span>
          </div>
          <button 
            onClick={() => setFeedbackMessage(null)}
            className="text-xs opacity-70 hover:opacity-100 underline ml-3"
          >
            Cerrar
          </button>
        </div>
      )}

      {/* Tarjeta de Estado Global / En vivo */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Estado Conexión */}
        <div className="p-3.5 bg-dark-900 border border-dark-750 rounded-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Canal Actual</span>
            <Radio size={14} className={connectedChannelId ? "text-emerald-400 animate-pulse" : "text-slate-500"} />
          </div>
          <div className="font-semibold text-sm text-white truncate">
            {currentConnectedChannel ? (
              <span className="text-emerald-400 flex items-center gap-1.5 truncate">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping shrink-0" />
                {currentConnectedChannel.name}
              </span>
            ) : (
              <span className="text-slate-400 font-normal">No conectado a voz</span>
            )}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            {isRecording ? "Grabando audio de los participantes" : "Bot en espera en el servidor"}
          </div>
        </div>

        {/* Canales que cumplen condición */}
        <div className="p-3.5 bg-dark-900 border border-dark-750 rounded-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Listos para Grabar</span>
            <CheckCircle2 size={14} className="text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400">
            {readyChannelsCount} <span className="text-xs font-normal text-slate-400">canales</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Cumplen ≥ {minUsersRequired} {minUsersRequired === 1 ? 'persona' : 'personas'}
          </div>
        </div>

        {/* Personas en Llamada */}
        <div className="p-3.5 bg-dark-900 border border-dark-750 rounded-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Personas en Voz</span>
            <Users size={14} className="text-cyan-400" />
          </div>
          <div className="text-xl font-bold text-cyan-300">
            {activeUsersCount} <span className="text-xs font-normal text-slate-400">activos</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            En {allChannels.filter(c => c.humanCount > 0).length} canales activos
          </div>
        </div>

        {/* Criterio de Activación */}
        <div className="p-3.5 bg-dark-900 border border-dark-750 rounded-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>Criterio de Auto-grabado</span>
            <Info size={14} className="text-indigo-400" />
          </div>
          <div className="text-sm font-semibold text-indigo-300">
            ≥ {minUsersRequired} {minUsersRequired === 1 ? 'humano' : 'humanos'}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Configurado en MIN_USERS_TO_RECORD
          </div>
        </div>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-dark-900/60 p-3 rounded-xs border border-dark-750">
        {/* Buscador */}
        <div className="relative flex-1 max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Buscar canal o usuario..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-dark-850 border border-dark-700 rounded-xs pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        {/* Filtros rápidos */}
        <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
          <button
            onClick={() => setFilterType('all')}
            className={`px-3 py-1.5 rounded-xs transition-colors ${
              filterType === 'all'
                ? 'bg-indigo-600 text-white font-medium shadow-xs'
                : 'bg-dark-800 text-slate-400 hover:text-slate-200 hover:bg-dark-750 border border-dark-700'
            }`}
          >
            Todos ({allChannels.length})
          </button>
          <button
            onClick={() => setFilterType('ready')}
            className={`px-3 py-1.5 rounded-xs transition-colors flex items-center space-x-1.5 ${
              filterType === 'ready'
                ? 'bg-emerald-600 text-white font-medium shadow-xs'
                : 'bg-dark-800 text-emerald-400 hover:bg-dark-750 border border-dark-700'
            }`}
          >
            <CheckCircle2 size={12} />
            <span>Cumplen condición ({readyChannelsCount})</span>
          </button>
          <button
            onClick={() => setFilterType('active')}
            className={`px-3 py-1.5 rounded-xs transition-colors flex items-center space-x-1.5 ${
              filterType === 'active'
                ? 'bg-cyan-600 text-white font-medium shadow-xs'
                : 'bg-dark-800 text-slate-400 hover:text-slate-200 hover:bg-dark-750 border border-dark-700'
            }`}
          >
            <Radio size={12} />
            <span>Conectado</span>
          </button>
          <button
            onClick={() => setFilterType('empty')}
            className={`px-3 py-1.5 rounded-xs transition-colors ${
              filterType === 'empty'
                ? 'bg-slate-700 text-white font-medium shadow-xs'
                : 'bg-dark-800 text-slate-500 hover:text-slate-300 hover:bg-dark-750 border border-dark-700'
            }`}
          >
            Vacíos ({allChannels.filter(c => c.humanCount === 0).length})
          </button>
        </div>
      </div>

      {/* Lista de Servidores y Canales */}
      {loading ? (
        <div className="py-16 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-2">
          <RotateCw size={24} className="animate-spin text-indigo-400" />
          <span>Consultando canales de voz del servidor...</span>
        </div>
      ) : guilds.length === 0 ? (
        <div className="py-16 text-center text-slate-500 text-xs border border-dashed border-dark-750 rounded-xs p-8">
          <Server size={32} className="mx-auto text-slate-600 mb-2" />
          <p className="text-slate-400 font-medium">No se detectaron servidores conectados</p>
          <p className="text-slate-500 mt-1">Asegúrate de que el bot de Discord tenga el token configurado y permisos para ver canales de voz.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {guilds.map((guild) => {
            const filteredChannels = (guild.channels || []).filter(filterChannel);

            return (
              <div key={guild.id} className="bg-dark-900 border border-dark-750 rounded-xs overflow-hidden">
                {/* Cabecera del Servidor */}
                <div className="px-4 py-3 bg-dark-850/80 border-b border-dark-750 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    {guild.iconUrl ? (
                      <img 
                        src={guild.iconUrl} 
                        alt={guild.name} 
                        className="w-8 h-8 rounded-xs object-cover border border-dark-700 shadow-xs"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-xs bg-dark-750 border border-dark-650 flex items-center justify-center font-bold text-xs text-indigo-300">
                        {guild.name.substring(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <h2 className="text-sm font-bold text-white tracking-wide">{guild.name}</h2>
                      <span className="text-[11px] text-slate-400">
                        {guild.channels?.length || 0} canales de voz disponibles
                      </span>
                    </div>
                  </div>

                  <span className="text-xs px-2.5 py-1 rounded-xs bg-dark-800 text-slate-300 border border-dark-700">
                    ID: <code className="font-mono text-[10px] text-slate-400">{guild.id}</code>
                  </span>
                </div>

                {/* Grid de Canales */}
                <div className="p-4">
                  {filteredChannels.length === 0 ? (
                    <div className="py-8 text-center text-xs text-slate-500">
                      No hay canales que coincidan con el filtro actual.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
                      {filteredChannels.map((channel) => {
                        const isConnected = channel.isConnected || channel.id === connectedChannelId;
                        const meets = channel.meetsConditions;
                        const isLoading = loadingAction === channel.id;
                        const isSuccess = successAction === channel.id;

                        return (
                          <div
                            key={channel.id}
                            className={`p-3.5 rounded-xs border flex flex-col justify-between transition-all ${
                              isConnected
                                ? 'bg-gradient-to-b from-dark-850 to-emerald-950/20 border-emerald-600/70 shadow-[0_0_15px_rgba(16,185,129,0.1)]'
                                : meets
                                ? 'bg-dark-850/90 border-emerald-800/40 hover:border-emerald-600/60'
                                : 'bg-dark-850/50 border-dark-750 hover:border-dark-700'
                            }`}
                          >
                            {/* Header del Canal */}
                            <div>
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="flex items-center space-x-2 min-w-0">
                                  <Volume2 
                                    size={16} 
                                    className={
                                      isConnected 
                                        ? "text-emerald-400 animate-pulse shrink-0" 
                                        : meets 
                                        ? "text-emerald-400 shrink-0" 
                                        : "text-slate-400 shrink-0"
                                    } 
                                  />
                                  <span className="font-semibold text-sm text-slate-100 truncate" title={channel.name}>
                                    {channel.name}
                                  </span>
                                </div>

                                {/* Badge de Estado */}
                                {isConnected ? (
                                  <span className="shrink-0 px-2 py-0.5 rounded-xs text-[10px] font-semibold bg-emerald-950 border border-emerald-700/80 text-emerald-300 flex items-center gap-1 shadow-xs">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                                    Conectado
                                  </span>
                                ) : meets ? (
                                  <span className="shrink-0 px-2 py-0.5 rounded-xs text-[10px] font-semibold bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 flex items-center gap-1">
                                    <CheckCircle2 size={11} />
                                    Cumple
                                  </span>
                                ) : channel.humanCount > 0 ? (
                                  <span className="shrink-0 px-2 py-0.5 rounded-xs text-[10px] font-medium bg-cyan-950/40 border border-cyan-800/50 text-cyan-300">
                                    {channel.humanCount} {channel.humanCount === 1 ? 'persona' : 'personas'}
                                  </span>
                                ) : (
                                  <span className="shrink-0 px-2 py-0.5 rounded-xs text-[10px] font-normal bg-dark-800 border border-dark-700 text-slate-500">
                                    Vacío
                                  </span>
                                )}
                              </div>

                              {/* Categoría y capacidad */}
                              <div className="flex items-center justify-between text-[11px] text-slate-500 mb-3">
                                <span>{channel.category || 'Canales de voz'}</span>
                                <span>
                                  {channel.humanCount} {channel.humanCount === 1 ? 'usuario' : 'usuarios'}
                                  {channel.userLimit > 0 ? ` / ${channel.userLimit}` : ''}
                                </span>
                              </div>

                              {/* Participantes presentes */}
                              <div className="mb-4">
                                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
                                  En llamada ({channel.members.length})
                                </div>

                                {channel.members.length === 0 ? (
                                  <div className="text-xs text-slate-600 italic py-1">
                                    Ningún miembro en este canal
                                  </div>
                                ) : (
                                  <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
                                    {channel.members.map((member) => (
                                      <div
                                        key={member.id}
                                        className={`flex items-center space-x-1.5 px-2 py-1 rounded-xs text-xs border ${
                                          member.isBot
                                            ? 'bg-indigo-950/40 border-indigo-800/50 text-indigo-300'
                                            : 'bg-dark-800 border-dark-700 text-slate-200'
                                        }`}
                                        title={`${member.displayName} (@${member.username})`}
                                      >
                                        {member.avatarUrl ? (
                                          <img
                                            src={member.avatarUrl}
                                            alt={member.displayName}
                                            className="w-4 h-4 rounded-full object-cover shrink-0"
                                          />
                                        ) : (
                                          <div className="w-4 h-4 rounded-full bg-dark-700 flex items-center justify-center text-[9px] font-bold text-slate-400">
                                            {member.displayName.substring(0, 1)}
                                          </div>
                                        )}
                                        <span className="truncate max-w-[90px] font-medium text-[11px]">
                                          {member.displayName}
                                        </span>
                                        {member.selfMute && (
                                          <MicOff size={11} className="text-rose-400/80 shrink-0" title="Silenciado" />
                                        )}
                                        {member.selfDeaf && (
                                          <Headphones size={11} className="text-rose-400/80 shrink-0" title="Ensordecido" />
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Botón de Acción Táctil */}
                            <div className="pt-2 border-t border-dark-750">
                              {isConnected ? (
                                <button
                                  onClick={handleLeave}
                                  disabled={loadingAction === 'leave'}
                                  className="w-full btn-rose py-1.5 px-3 rounded-xs text-xs flex items-center justify-center space-x-1.5"
                                >
                                  {loadingAction === 'leave' ? (
                                    <RotateCw size={13} className="animate-spin" />
                                  ) : (
                                    <Square size={13} />
                                  )}
                                  <span>Desconectar del Canal</span>
                                </button>
                              ) : !channel.canJoin ? (
                                <button
                                  disabled
                                  className="w-full btn-secondary py-1.5 px-3 rounded-xs text-xs flex items-center justify-center space-x-1.5 opacity-40 cursor-not-allowed"
                                >
                                  <ShieldAlert size={13} className="text-amber-400" />
                                  <span>Sin Permiso para Unir</span>
                                </button>
                              ) : meets ? (
                                <button
                                  onClick={() => handleJoin(channel)}
                                  disabled={isLoading || !botActive}
                                  className="w-full btn-emerald py-1.5 px-3 rounded-xs text-xs flex items-center justify-center space-x-1.5"
                                  title="Unir el bot a este canal y comenzar a grabar"
                                >
                                  {isLoading ? (
                                    <RotateCw size={13} className="animate-spin" />
                                  ) : isSuccess ? (
                                    <Check size={13} className="text-white" />
                                  ) : (
                                    <Play size={13} />
                                  )}
                                  <span>
                                    {isSuccess ? '¡Conectado!' : 'Unir Bot y Grabar'}
                                  </span>
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleJoin(channel)}
                                  disabled={isLoading || !botActive}
                                  className="w-full btn-secondary py-1.5 px-3 rounded-xs text-xs flex items-center justify-center space-x-1.5 hover:text-slate-100"
                                  title={
                                    channel.humanCount === 0 
                                      ? "El canal está vacío. Puedes forzar la unión si deseas." 
                                      : `Hay ${channel.humanCount} persona (el mínimo es ${minUsersRequired}). Puedes forzar la unión.`
                                  }
                                >
                                  {isLoading ? (
                                    <RotateCw size={13} className="animate-spin" />
                                  ) : isSuccess ? (
                                    <Check size={13} className="text-white" />
                                  ) : (
                                    <Zap size={13} className="text-slate-400" />
                                  )}
                                  <span>
                                    {isSuccess ? '¡Conectado!' : 'Unir Manualmente'}
                                  </span>
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
