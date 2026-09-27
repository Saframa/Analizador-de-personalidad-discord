import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Share2, Users, Flame, Clock, Search, Filter, 
  RotateCw, ZoomIn, ZoomOut, Maximize2, Sparkles, MessageCircle, ExternalLink
} from 'lucide-react';
import { fetchSocialGraph } from '../api';

export default function SocialGraphView({ onSelectUser }) {
  const [data, setData] = useState({ nodes: [], edges: [], stats: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [minSessions, setMinSessions] = useState(2);
  const [zoom, setZoom] = useState(1);
  const svgRef = useRef(null);

  const loadGraph = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSocialGraph();
      setData(res);
      // Seleccionar por defecto el usuario con más locución si no hay uno seleccionado
      if (res.nodes && res.nodes.length > 0 && !selectedNodeId) {
        setSelectedNodeId(res.nodes[0].id);
      }
    } catch (err) {
      console.error(err);
      setError('Error al cargar la red social del servidor.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, []);

  // Filtrar aristas por mínimo de sesiones
  const filteredEdges = useMemo(() => {
    return (data.edges || []).filter(e => e.sessions_together >= minSessions);
  }, [data.edges, minSessions]);

  // Layout circular orgánico para los nodos
  const layoutNodes = useMemo(() => {
    const nodes = data.nodes || [];
    if (nodes.length === 0) return [];

    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.38;

    return nodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / nodes.length - Math.PI / 2;
      // Posición base circular
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      // Radio del nodo según tiempo de habla
      const r = 24 + (node.size_weight || 0.5) * 22;

      return {
        ...node,
        x,
        y,
        r,
      };
    });
  }, [data.nodes]);

  const nodeMap = useMemo(() => {
    const map = {};
    layoutNodes.forEach(n => {
      map[n.id] = n;
    });
    return map;
  }, [layoutNodes]);

  // Nodos y aristas conectados al nodo activo (hover o seleccionado)
  const activeFocusId = hoveredNodeId || selectedNodeId;

  const connectedNodeIds = useMemo(() => {
    if (!activeFocusId) return new Set();
    const set = new Set([activeFocusId]);
    filteredEdges.forEach(e => {
      if (e.source === activeFocusId) set.add(e.target);
      if (e.target === activeFocusId) set.add(e.source);
    });
    return set;
  }, [activeFocusId, filteredEdges]);

  const activeUser = useMemo(() => {
    return layoutNodes.find(n => n.id === activeFocusId) || layoutNodes[0] || null;
  }, [layoutNodes, activeFocusId]);

  const activeUserConnections = useMemo(() => {
    if (!activeUser) return [];
    return filteredEdges
      .filter(e => e.source === activeUser.id || e.target === activeUser.id)
      .map(e => {
        const otherId = e.source === activeUser.id ? e.target : e.source;
        const otherNode = nodeMap[otherId];
        return {
          ...e,
          peer: otherNode,
        };
      })
      .sort((a, b) => b.sessions_together - a.sessions_together);
  }, [activeUser, filteredEdges, nodeMap]);

  return (
    <div className="flex-1 h-full flex flex-col bg-dark-950 overflow-hidden text-slate-200">
      {/* Header Superior */}
      <div className="px-6 py-4 border-b border-dark-800 bg-dark-900/60 backdrop-blur flex items-center justify-between flex-shrink-0">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
              <Share2 size={20} />
            </div>
            <h1 className="text-lg font-bold text-white tracking-wide">Dinámica Social y Red de Interacciones</h1>
            <span className="bg-indigo-950/60 text-indigo-300 text-xs px-2.5 py-0.5 rounded-full border border-indigo-800/40 font-medium">
              {data.nodes.length} Miembros Activos
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Mapeo de afinidad y tiempo compartido entre los participantes a partir de 82 sesiones de llamadas de Discord.
          </p>
        </div>

        {/* Controles y Filtros */}
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Buscar miembro..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-dark-800/90 border border-dark-700/80 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-44 transition"
            />
          </div>

          <div className="flex items-center space-x-2 bg-dark-800/70 border border-dark-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-300">
            <Filter size={13} className="text-indigo-400" />
            <span>Mín. Sesiones:</span>
            <input
              type="range"
              min="1"
              max="20"
              value={minSessions}
              onChange={(e) => setMinSessions(Number(e.target.value))}
              className="w-20 accent-indigo-500 cursor-pointer"
            />
            <span className="font-semibold text-white w-4 text-center">{minSessions}</span>
          </div>

          <div className="flex items-center space-x-1 bg-dark-800/70 border border-dark-700/80 rounded-lg p-0.5">
            <button
              onClick={() => setZoom(prev => Math.min(1.5, prev + 0.1))}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-dark-700 rounded transition"
              title="Acercar"
            >
              <ZoomIn size={14} />
            </button>
            <button
              onClick={() => setZoom(prev => Math.max(0.7, prev - 0.1))}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-dark-700 rounded transition"
              title="Alejar"
            >
              <ZoomOut size={14} />
            </button>
            <button
              onClick={() => setZoom(1)}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-dark-700 rounded transition"
              title="Restablecer Zoom"
            >
              <Maximize2 size={14} />
            </button>
          </div>

          <button
            onClick={loadGraph}
            className="p-2 text-slate-400 hover:text-white hover:bg-dark-800 rounded-lg transition border border-dark-700"
            title="Refrescar datos"
          >
            <RotateCw size={15} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Contenido Principal: Grafo Interactivo + Panel Lateral */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Lienzo SVG del Grafo */}
        <div className="flex-1 h-full bg-radial-dark relative overflow-hidden flex items-center justify-center">
          {loading ? (
            <div className="flex flex-col items-center justify-center text-slate-400 space-y-3">
              <RotateCw size={32} className="animate-spin text-indigo-500" />
              <p className="text-sm">Generando topología social del servidor...</p>
            </div>
          ) : (
            <div 
              className="w-full h-full flex items-center justify-center transition-transform duration-300"
              style={{ transform: `scale(${zoom})` }}
            >
              <svg
                ref={svgRef}
                viewBox="0 0 800 600"
                className="w-full h-full max-w-4xl max-h-[85vh] select-none"
              >
                <defs>
                  {/* Gradientes para las aristas */}
                  <linearGradient id="edgeGradientDefault" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#a855f7" stopOpacity="0.4" />
                  </linearGradient>
                  <linearGradient id="edgeGradientActive" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#818cf8" stopOpacity="0.9" />
                  </linearGradient>
                  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                  </filter>
                </defs>

                {/* Aristas (Conexiones entre usuarios) */}
                <g className="edges">
                  {filteredEdges.map((edge, idx) => {
                    const sourceNode = nodeMap[edge.source];
                    const targetNode = nodeMap[edge.target];
                    if (!sourceNode || !targetNode) return null;

                    const isConnectedToFocus = activeFocusId && (edge.source === activeFocusId || edge.target === activeFocusId);
                    const strokeWidth = 1.2 + edge.affinity * 4.5;
                    const strokeOpacity = activeFocusId 
                      ? (isConnectedToFocus ? 0.9 : 0.08)
                      : Math.max(0.15, edge.affinity * 0.6);

                    // Curva bezier suave
                    const midX = (sourceNode.x + targetNode.x) / 2;
                    const midY = (sourceNode.y + targetNode.y) / 2;
                    const dx = targetNode.x - sourceNode.x;
                    const dy = targetNode.y - sourceNode.y;
                    const normalX = -dy * 0.12;
                    const normalY = dx * 0.12;
                    const pathD = `M ${sourceNode.x} ${sourceNode.y} Q ${midX + normalX} ${midY + normalY} ${targetNode.x} ${targetNode.y}`;

                    return (
                      <path
                        key={`edge-${idx}`}
                        d={pathD}
                        fill="none"
                        stroke={isConnectedToFocus ? "url(#edgeGradientActive)" : "url(#edgeGradientDefault)"}
                        strokeWidth={isConnectedToFocus ? strokeWidth + 1.5 : strokeWidth}
                        strokeOpacity={strokeOpacity}
                        strokeLinecap="round"
                        className="transition-all duration-300 pointer-events-none"
                      />
                    );
                  })}
                </g>

                {/* Nodos (Usuarios) */}
                <g className="nodes">
                  {layoutNodes.map((node) => {
                    const isFocused = activeFocusId === node.id;
                    const isNeighbor = connectedNodeIds.has(node.id);
                    const isMatchedBySearch = searchQuery && (
                      node.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      node.username.toLowerCase().includes(searchQuery.toLowerCase())
                    );

                    let opacity = 1;
                    if (activeFocusId && !isNeighbor) {
                      opacity = 0.25;
                    }
                    if (searchQuery && !isMatchedBySearch) {
                      opacity = 0.15;
                    }

                    return (
                      <g
                        key={`node-${node.id}`}
                        transform={`translate(${node.x}, ${node.y})`}
                        opacity={opacity}
                        className="cursor-pointer transition-all duration-300"
                        onMouseEnter={() => setHoveredNodeId(node.id)}
                        onMouseLeave={() => setHoveredNodeId(null)}
                        onClick={() => setSelectedNodeId(node.id)}
                      >
                        {/* Halo exterior al hacer hover o foco */}
                        {(isFocused || isMatchedBySearch) && (
                          <circle
                            r={node.r + 9}
                            fill="none"
                            stroke="#818cf8"
                            strokeWidth="2.5"
                            strokeDasharray="4 3"
                            filter="url(#glow)"
                            className="animate-spin-slow"
                          />
                        )}

                        {/* Círculo base del nodo */}
                        <circle
                          r={node.r}
                          fill="#0f172a"
                          stroke={isFocused ? "#38bdf8" : "#475569"}
                          strokeWidth={isFocused ? "3" : "1.8"}
                          className="transition-colors duration-200 shadow-lg"
                        />

                        {/* Avatar o Iniciales */}
                        {node.has_avatar && node.avatar_url ? (
                          <clipPath id={`clip-${node.id}`}>
                            <circle r={node.r - 2} />
                          </clipPath>
                        ) : null}

                        {node.has_avatar && node.avatar_url ? (
                          <image
                            href={node.avatar_url}
                            x={-(node.r - 2)}
                            y={-(node.r - 2)}
                            width={(node.r - 2) * 2}
                            height={(node.r - 2) * 2}
                            clipPath={`url(#clip-${node.id})`}
                            preserveAspectRatio="xMidYMid slice"
                          />
                        ) : (
                          <text
                            textAnchor="middle"
                            dy=".35em"
                            fill="#f8fafc"
                            fontSize={node.r * 0.65}
                            fontWeight="bold"
                            className="pointer-events-none select-none font-sans"
                          >
                            {node.display_name.substring(0, 2).toUpperCase()}
                          </text>
                        )}

                        {/* Etiqueta del Nombre */}
                        <g transform={`translate(0, ${node.r + 14})`}>
                          <rect
                            x={-(node.display_name.length * 3.8 + 8)}
                            y="-9"
                            width={(node.display_name.length * 3.8 + 8) * 2}
                            height="18"
                            rx="5"
                            fill="#020617"
                            fillOpacity="0.85"
                            stroke={isFocused ? "#6366f1" : "#1e293b"}
                            strokeWidth="1"
                          />
                          <text
                            textAnchor="middle"
                            dy=".32em"
                            fill={isFocused ? "#ffffff" : "#94a3b8"}
                            fontSize="10.5"
                            fontWeight={isFocused ? "bold" : "500"}
                            className="pointer-events-none select-none font-sans"
                          >
                            {node.display_name}
                          </text>
                        </g>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          )}
        </div>

        {/* Panel Lateral: Ficha del Usuario Activo y Estadísticas del Grafo */}
        <div className="w-80 border-l border-dark-800 bg-dark-900/90 backdrop-blur-md p-5 flex flex-col justify-between overflow-y-auto z-10 shadow-xl">
          {activeUser ? (
            <div className="space-y-5">
              {/* Encabezado del miembro seleccionado */}
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-indigo-950/80 border border-indigo-700/40 flex items-center justify-center font-bold text-white overflow-hidden shadow-inner text-lg">
                    {activeUser.has_avatar && activeUser.avatar_url ? (
                      <img src={activeUser.avatar_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      activeUser.display_name.substring(0, 2).toUpperCase()
                    )}
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-base leading-tight">{activeUser.display_name}</h3>
                    <p className="text-xs text-slate-400 font-mono">@{activeUser.username}</p>
                    <span className="inline-block mt-1 px-2 py-0.5 bg-dark-800 text-indigo-300 text-[10px] font-medium rounded border border-indigo-800/30">
                      {activeUser.primary_role}
                    </span>
                  </div>
                </div>
              </div>

              {/* Métricas rápidas de locución */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-dark-800/60 p-2.5 rounded-lg border border-dark-700/60">
                  <div className="flex items-center space-x-1.5 text-slate-400 mb-1">
                    <Clock size={12} className="text-indigo-400" />
                    <span>Locución Total</span>
                  </div>
                  <p className="text-sm font-bold text-white">{activeUser.speaking_formatted}</p>
                </div>
                <div className="bg-dark-800/60 p-2.5 rounded-lg border border-dark-700/60">
                  <div className="flex items-center space-x-1.5 text-slate-400 mb-1">
                    <Users size={12} className="text-indigo-400" />
                    <span>Llamadas</span>
                  </div>
                  <p className="text-sm font-bold text-white">{activeUser.total_sessions_analyzed} sesiones</p>
                </div>
              </div>

              {/* Lista de conexiones más fuertes */}
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2 flex items-center justify-between">
                  <span>Principales Conexiones</span>
                  <span className="text-[11px] text-indigo-400 lowercase font-normal">
                    {activeUserConnections.length} vínculos
                  </span>
                </h4>

                <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1 scrollbar-thin">
                  {activeUserConnections.length === 0 ? (
                    <p className="text-xs text-slate-500 py-2">No supera el filtro de {minSessions} sesiones.</p>
                  ) : (
                    activeUserConnections.map((conn, idx) => {
                      if (!conn.peer) return null;
                      return (
                        <div
                          key={idx}
                          onClick={() => setSelectedNodeId(conn.peer.id)}
                          className="flex items-center justify-between p-2 rounded-lg bg-dark-800/40 hover:bg-dark-800 border border-dark-700/40 cursor-pointer transition text-xs"
                        >
                          <div className="flex items-center space-x-2">
                            <div className="w-6 h-6 rounded-full bg-slate-800 text-[10px] font-bold flex items-center justify-center text-slate-300 border border-slate-700">
                              {conn.peer.display_name.substring(0, 2).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-medium text-slate-200">{conn.peer.display_name}</p>
                              <p className="text-[10px] text-slate-500">{conn.shared_speaking_formatted} juntos</p>
                            </div>
                          </div>

                          <div className="text-right">
                            <span className="font-semibold text-indigo-400">{conn.sessions_together}</span>
                            <span className="text-[10px] text-slate-500 ml-1">ses.</span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

              {/* Botón de inspección modal */}
              {onSelectUser && (
                <button
                  onClick={() => onSelectUser(activeUser.id)}
                  className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-indigo-600/90 hover:bg-indigo-600 text-white rounded-lg text-xs font-medium transition shadow-md"
                >
                  <ExternalLink size={14} />
                  <span>Ver Perfil Psicológico Completo</span>
                </button>
              )}
            </div>
          ) : null}

          {/* Dúo dinámico destacado de todo el servidor */}
          {data.stats && data.stats.top_pair && (
            <div className="mt-4 pt-4 border-t border-dark-800">
              <div className="bg-gradient-to-br from-indigo-950/40 to-dark-800 p-3 rounded-xl border border-indigo-900/30 text-xs">
                <div className="flex items-center space-x-1.5 text-amber-400 font-semibold mb-1">
                  <Flame size={14} />
                  <span>Dúo Más Activo del Servidor</span>
                </div>
                <p className="text-white font-medium">
                  {data.stats.top_pair.u1_name} & {data.stats.top_pair.u2_name}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Han compartido <span className="text-indigo-300 font-semibold">{data.stats.top_pair.sessions_together} sesiones</span> ({data.stats.top_pair.shared_time} juntos).
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
