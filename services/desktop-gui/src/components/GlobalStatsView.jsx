import React, { useEffect, useState } from 'react';
import { fetchGlobalStats } from '../api';
import { 
  Clock, 
  Layers, 
  BookOpen, 
  Users, 
  TrendingUp, 
  Award, 
  RotateCw 
} from 'lucide-react';

export default function GlobalStatsView({ onSelectUser, isBackendReady }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = async (retryCount = 0) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchGlobalStats();
      setStats(data);
    } catch (err) {
      if (retryCount < 2) {
        setTimeout(() => loadData(retryCount + 1), 1000);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [isBackendReady]);

  if (loading && !stats) {
    return (
      <div className="h-full flex items-center justify-center text-slate-400">
        <RotateCw className="animate-spin mr-2" size={20} />
        <span>Cargando estadísticas globales...</span>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="p-6 text-center text-rose-400 bg-dark-900 border border-dark-700 rounded-xs m-6">
        <p className="font-medium">Error al cargar estadísticas</p>
        <p className="text-xs text-slate-500 mt-1">{error}</p>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-1.5 rounded-xs bg-dark-800 hover:bg-dark-700 text-slate-200 text-xs transition-colors"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const maxSpeakingSec = stats?.leaderboard?.[0]?.total_speaking_seconds || 1;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full">
      {/* Título y botón refrescar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Estadísticas Generales de Recolección
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Consolidado histórico de todas las sesiones de Discord analizadas y sintetizadas
          </p>
        </div>
        <button
          onClick={loadData}
          className="p-2 rounded-xs bg-dark-850 hover:bg-dark-700 text-slate-400 hover:text-slate-200 border border-dark-700 transition-colors"
          title="Actualizar estadísticas"
        >
          <RotateCw size={16} className={loading ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Tarjetas de Métricas Clave */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 shadow-sm flex items-center space-x-3.5">
          <div className="p-2.5 rounded-xs bg-dark-800 text-indigo-400 border border-dark-700">
            <Layers size={22} />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-100">{stats?.total_sessions_recorded || 0}</div>
            <div className="text-xs text-slate-400">Sesiones Grabadas</div>
          </div>
        </div>

        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 shadow-sm flex items-center space-x-3.5">
          <div className="p-2.5 rounded-xs bg-dark-800 text-cyan-400 border border-dark-700">
            <Clock size={22} />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-100">{stats?.total_speaking_hours || 0} h</div>
            <div className="text-xs text-slate-400">Voz Activa Acumulada</div>
          </div>
        </div>

        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 shadow-sm flex items-center space-x-3.5">
          <div className="p-2.5 rounded-xs bg-dark-800 text-emerald-400 border border-dark-700">
            <BookOpen size={22} />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-100">
              {(stats?.total_words_cataloged || 0).toLocaleString()}
            </div>
            <div className="text-xs text-slate-400">Palabras en Diccionario</div>
          </div>
        </div>

        <div className="p-4 rounded-xs bg-dark-900 border border-dark-700 shadow-sm flex items-center space-x-3.5">
          <div className="p-2.5 rounded-xs bg-dark-800 text-amber-400 border border-dark-700">
            <Users size={22} />
          </div>
          <div>
            <div className="text-2xl font-bold text-slate-100">{stats?.participants_count || 0}</div>
            <div className="text-xs text-slate-400">Amigos Catalogados</div>
          </div>
        </div>
      </div>

      {/* Tabla y Ranking de Habla */}
      <div className="bg-dark-900 border border-dark-700 rounded-xs p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
          <div className="flex items-center space-x-2">
            <TrendingUp size={18} className="text-indigo-400" />
            <h2 className="font-semibold text-slate-200 text-sm">
              Ranking de Participación y Tiempo de Habla
            </h2>
          </div>
          <span className="text-xs text-slate-500">
            Ordenado por volumen total de locución
          </span>
        </div>

        <div className="space-y-2.5">
          {stats?.leaderboard?.map((item, index) => {
            const percentOfTop = Math.round((item.total_speaking_seconds / maxSpeakingSec) * 100);
            return (
              <div
                key={item.user_id}
                onClick={() => onSelectUser && onSelectUser(item.user_id)}
                className="group p-3 rounded-xs bg-dark-850 hover:bg-dark-800/80 border border-dark-700/70 hover:border-dark-600 transition-all cursor-pointer"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-3">
                    <span className="text-xs font-mono font-medium text-slate-500 w-5">
                      #{index + 1}
                    </span>
                    <div className="w-8 h-8 rounded-xs bg-dark-800 border border-dark-600 overflow-hidden flex items-center justify-center text-xs font-semibold text-slate-300 flex-shrink-0">
                      {item.has_avatar ? (
                        <img
                          src={`http://127.0.0.1:8000${item.avatar_url}`}
                          alt={item.display_name}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        item.display_name.slice(0, 2).toUpperCase()
                      )}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-200 group-hover:text-white flex items-center space-x-2">
                        <span>{item.display_name}</span>
                        {index === 0 && <Award size={14} className="text-amber-400" />}
                      </div>
                      <div className="text-xs text-slate-500">
                        @{item.username} · {item.primary_role}
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-sm font-semibold text-slate-300">
                      {item.total_speaking_formatted}
                    </div>
                    <div className="text-xs text-slate-500">
                      {item.total_words_spoken.toLocaleString()} palabras
                    </div>
                    {item.total_unique_words > 0 && (
                      <div className="text-[10px] text-violet-400/70">
                        {item.total_unique_words.toLocaleString()} únicas
                      </div>
                    )}
                  </div>
                </div>

                {/* Barra de progreso sutil */}
                <div className="w-full bg-dark-800 rounded-none h-1.5 overflow-hidden">
                  <div
                    className="bg-indigo-500/80 h-full rounded-none transition-all duration-500"
                    style={{ width: `${percentOfTop}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
