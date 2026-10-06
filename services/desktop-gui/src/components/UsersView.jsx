import React, { useEffect, useState } from 'react';
import { 
  Users, 
  Search, 
  MessageSquare, 
  Mic, 
  MicOff, 
  Clock, 
  BookOpen, 
  ArrowRight,
  RotateCw
} from 'lucide-react';
import { fetchUsers } from '../api';

export default function UsersView({ onSelectUser, onOpenChat, isBackendReady }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  const loadUsers = async (retryCount = 0) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchUsers();
      const list = Array.isArray(data) ? data : (data.users || []);
      setUsers(list);
    } catch (err) {
      if (retryCount < 2) {
        setTimeout(() => loadUsers(retryCount + 1), 1000);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [isBackendReady]);

  const filteredUsers = users.filter((u) => {
    const q = search.toLowerCase();
    return (
      u.display_name?.toLowerCase().includes(q) ||
      u.username?.toLowerCase().includes(q) ||
      u.primary_role?.toLowerCase().includes(q) ||
      (u.nicknames && u.nicknames.some((nick) => nick.toLowerCase().includes(q)))
    );
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto overflow-y-auto h-full">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            Amigos y Perfiles Psicológicos
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Explora perfiles evolucionados, sube fotos y chatea con sus gemelos digitales
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Barra de búsqueda */}
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Buscar por nombre o rol..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-3 py-1.5 rounded-xs bg-dark-850 border border-dark-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors w-64"
            />
          </div>

          <button
            onClick={loadUsers}
            className="btn-secondary p-2 rounded-xs"
            title="Actualizar lista"
          >
            <RotateCw size={15} className={loading ? "animate-spin text-indigo-400" : ""} />
          </button>
        </div>
      </div>

      {/* Estados de Carga / Error */}
      {loading && users.length === 0 && (
        <div className="h-64 flex items-center justify-center text-slate-400">
          <RotateCw className="animate-spin mr-2" size={20} />
          <span>Cargando perfiles...</span>
        </div>
      )}

      {error && (
        <div className="p-5 text-center text-rose-400 bg-dark-900 border border-dark-700 rounded-xs">
          <p className="font-medium">Error al cargar usuarios</p>
          <p className="text-xs text-slate-500 mt-1">{error}</p>
          <button
            onClick={loadUsers}
            className="btn-secondary mt-3 px-4 py-1.5 text-xs"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Grid de Tarjetas de Usuario */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredUsers.map((user) => (
          <div
            key={user.user_id}
            className="group relative bg-dark-900 border border-dark-700 hover:border-dark-600 rounded-xs p-5 shadow-sm transition-all flex flex-col justify-between"
          >
            {/* Cabecera de la tarjeta con Avatar y Botón Chat */}
            <div>
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3.5">
                  <div className="relative w-12 h-12 rounded-xs bg-dark-800 border border-dark-650 overflow-hidden flex items-center justify-center text-sm font-bold text-slate-300 flex-shrink-0">
                    {user.has_avatar ? (
                      <img
                        src={`http://127.0.0.1:8000${user.avatar_url}`}
                        alt={user.display_name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      user.display_name.slice(0, 2).toUpperCase()
                    )}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-100 group-hover:text-indigo-300 transition-colors">
                      {user.display_name}
                    </h3>
                    <p className="text-xs text-slate-500 font-mono">
                      @{user.username}
                    </p>
                  </div>
                </div>

                {/* Botón directo a Chat IA (arriba a la derecha) */}
                <button
                  onClick={() => onOpenChat && onOpenChat(user.user_id)}
                  className="btn-tactile p-2 rounded-xs bg-dark-800 hover:bg-indigo-600 text-slate-400 hover:text-white border border-dark-700 hover:border-indigo-500 shadow-sm"
                  title={`Chatear con el gemelo de ${user.display_name}`}
                >
                  <MessageSquare size={17} />
                </button>
              </div>

              {/* Rol / Arquetipo */}
              <div className="mt-3.5 flex items-center space-x-2">
                <span className="text-[11px] px-2 py-0.5 rounded-xs bg-dark-800 text-indigo-300 border border-dark-700 font-medium">
                  {user.primary_role || 'Participante'}
                </span>
                {user.has_voice_sample ? (
                  <span className="text-[11px] px-2 py-0.5 rounded-xs bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 flex items-center space-x-1">
                    <Mic size={11} />
                    <span>Voz Lista</span>
                  </span>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded-xs bg-dark-800 text-slate-500 border border-dark-700 flex items-center space-x-1">
                    <MicOff size={11} />
                    <span>Sin Muestra</span>
                  </span>
                )}
              </div>

              {/* Métricas breves */}
              <div className="mt-4 pt-3 border-t border-dark-800 grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center space-x-1.5 text-slate-400">
                  <Clock size={13} className="text-cyan-400" />
                  <span>{user.speaking_formatted || '0m'}</span>
                </div>
                <div className="flex items-center space-x-1.5 text-slate-400">
                  <BookOpen size={13} className="text-emerald-400" />
                  <span>{(user.words_count || 0).toLocaleString()} pal.</span>
                </div>
                {user.unique_words_count > 0 && (
                  <div className="col-span-2 flex items-center space-x-1.5 text-slate-500">
                    <span className="text-violet-400 font-mono text-[10px]">◈</span>
                    <span>{(user.unique_words_count || 0).toLocaleString()} únicas</span>
                  </div>
                )}
              </div>
            </div>

            {/* Botón Inspeccionar Detalles */}
            <div className="mt-5 pt-3 border-t border-dark-800/70">
              <button
                onClick={() => onSelectUser && onSelectUser(user.user_id)}
                className="btn-secondary w-full py-2 px-3 text-xs font-medium space-x-1.5"
              >
                <span>Inspeccionar Perfil y Rasgos</span>
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredUsers.length === 0 && !loading && (
        <div className="p-12 text-center text-slate-500 bg-dark-900 border border-dark-700 rounded-xs">
          <Users size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm font-medium">No se encontraron perfiles</p>
          <p className="text-xs text-slate-600 mt-1">
            {search ? 'Prueba con otro término de búsqueda' : 'No hay datos de usuarios recolectados aún'}
          </p>
        </div>
      )}
    </div>
  );
}
