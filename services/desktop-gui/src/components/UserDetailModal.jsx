import React, { useEffect, useState, useRef } from 'react';
import { 
  X, 
  MessageSquare, 
  Upload, 
  Check, 
  Clock, 
  BookOpen, 
  Sliders, 
  Quote, 
  RotateCw,
  Edit2,
  Save,
  Filter,
  Heart,
  ThumbsDown
} from 'lucide-react';
import { fetchUserDetail, uploadAvatar, updateUserData } from '../api';

const BIG_FIVE_NAMES = {
  openness: { name: 'Apertura a la Experiencia', desc: 'Curiosidad intelectual, receptividad a nuevas ideas y creatividad.' },
  conscientiousness: { name: 'Responsabilidad / Meticulosidad', desc: 'Organización, persistencia, control de impulsos y rigor.' },
  extraversion: { name: 'Extraversión', desc: 'Sociabilidad, asertividad, entusiasmo y dinamismo verbal.' },
  agreeableness: { name: 'Amabilidad / Afabilidad', desc: 'Empatía, cooperación, calidez interpersonal y confianza.' },
  neuroticism: { name: 'Reactividad Emocional / Neuroticismo', desc: 'Sensibilidad al estrés, fluctuaciones de humor y vulnerabilidad.' },
};

// Palabras comunes (stopwords) en español para filtrar del diccionario
const COMMON_STOPWORDS = new Set([
  'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 'con', 'no', 'una', 
  'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 'sí', 'porque', 'esta', 'son', 
  'entre', 'está', 'cuando', 'muy', 'sin', 'sobre', 'ser', 'tiene', 'también', 'me', 'hasta', 'hay', 'donde', 
  'quien', 'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 
  'ante', 'ellos', 'e', 'esto', 'mí', 'antes', 'algunos', 'qué', 'unos', 'yo', 'otro', 'otras', 'otra', 'él', 
  'tanto', 'esa', 'estos', 'mucho', 'quienes', 'nada', 'muchos', 'cual', 'sea', 'poco', 'ella', 'estar', 
  'haber', 'estas', 'estaba', 'estamos', 'fue', 'fueron', 'va', 'vamos', 'van', 'hacer', 'hace', 'hacen', 'ahí', 'acá'
]);

export default function UserDetailModal({ userId, onClose, onOpenChat }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarTimestamp, setAvatarTimestamp] = useState(Date.now());
  const [filterStopwords, setFilterStopwords] = useState(true);
  const [wordSearch, setWordSearch] = useState('');
  const [isEditingMeta, setIsEditingMeta] = useState(false);
  const [editDisplayName, setEditDisplayName] = useState('');
  const [editNicknames, setEditNicknames] = useState('');
  const fileInputRef = useRef(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchUserDetail(userId);
      setUser(data);
      setEditDisplayName(data.display_name || '');
      setEditNicknames((data.nicknames || []).join(', '));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      loadData();
    }
  }, [userId]);

  const handleAvatarChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setAvatarUploading(true);
      await uploadAvatar(userId, file);
      setAvatarTimestamp(Date.now());
      loadData();
    } catch (err) {
      alert(`Error al subir avatar: ${err.message}`);
    } finally {
      setAvatarUploading(false);
    }
  };

  const handleSaveMeta = async () => {
    try {
      const nicks = editNicknames
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      await updateUserData(userId, {
        display_name: editDisplayName,
        nicknames: nicks,
      });
      setIsEditingMeta(false);
      loadData();
    } catch (err) {
      alert(`Error al guardar datos: ${err.message}`);
    }
  };

  if (!userId) return null;

  const archetype = user?.archetype || {};
  const bigFive = user?.big_five || {};
  const lexicon = user?.lexicon || {};
  const preferences = user?.preferences || { likes: [], dislikes: [] };
  const likes = preferences.likes || [];
  const dislikes = preferences.dislikes || [];
  const rawTopWords = lexicon.top_words || [];

  // Filtrado de vocabulario
  const filteredWords = rawTopWords.filter(([word]) => {
    const w = word.toLowerCase().trim();
    if (filterStopwords && (COMMON_STOPWORDS.has(w) || w.length < 3)) {
      return false;
    }
    if (wordSearch && !w.includes(wordSearch.toLowerCase())) {
      return false;
    }
    return true;
  });

  const maxWordFreq = filteredWords[0]?.[1] || 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-xs select-none">
      <div className="bg-dark-900 border border-dark-700 rounded-xs w-full max-w-5xl h-[92vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Barra Superior de la Inspección */}
        <div className="h-14 px-5 border-b border-dark-700 bg-dark-850 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
              Inspección de Perfil
            </span>
            <span className="text-dark-600">/</span>
            <span className="text-sm font-semibold text-slate-200">
              {user?.display_name || userId}
            </span>
          </div>

          <div className="flex items-center space-x-2.5">
            {/* Botón Chat con Gemelo Digital arriba a la derecha */}
            <button
              onClick={() => onOpenChat && onOpenChat(userId)}
              className="btn-primary px-3.5 py-1.5 rounded-xs text-xs font-semibold flex items-center space-x-2 shadow-sm"
              title="Abrir chat con gemelo digital"
            >
              <MessageSquare size={15} />
              <span>Chatear con Gemelo</span>
            </button>

            {/* Cerrar modal */}
            <button
              onClick={onClose}
              className="btn-secondary p-1.5 rounded-xs text-slate-400 hover:text-white"
              title="Cerrar"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Contenido Principal con Scroll */}
        {loading && !user ? (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            <RotateCw className="animate-spin mr-2" size={20} />
            <span>Cargando perfil psicológico...</span>
          </div>
        ) : error && !user ? (
          <div className="flex-1 p-6 text-center text-rose-400 flex flex-col items-center justify-center">
            <p className="font-semibold">{error}</p>
            <button
              onClick={loadData}
              className="mt-3 px-4 py-1.5 rounded-xs bg-dark-800 text-slate-200 text-xs border border-dark-700"
            >
              Reintentar
            </button>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Header del Perfil: Foto, Nombre, Apodos, Stats */}
            <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex items-start sm:items-center space-x-4">
                {/* Avatar cuadrado con botón de subida manual */}
                <div className="relative group w-20 h-20 rounded-xs bg-dark-800 border border-dark-600 overflow-hidden flex-shrink-0 flex items-center justify-center text-xl font-bold text-slate-300">
                  {user?.has_avatar ? (
                    <img
                      src={`http://127.0.0.1:8000${user.avatar_url}?t=${avatarTimestamp}`}
                      alt={user.display_name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    user?.display_name?.slice(0, 2).toUpperCase()
                  )}

                  {/* Overlay para subir foto */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={avatarUploading}
                    className="absolute inset-0 bg-black/80 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center text-[10px] text-slate-200 transition-opacity p-1 text-center"
                    title="Cargar foto manualmente"
                  >
                    <Upload size={16} className="mb-0.5" />
                    <span>{avatarUploading ? 'Subiendo...' : 'Cambiar Foto'}</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleAvatarChange}
                    className="hidden"
                  />
                </div>

                {/* Info y Edición de Nombres */}
                <div className="space-y-1">
                  {!isEditingMeta ? (
                    <div>
                      <div className="flex items-center space-x-2">
                        <h2 className="text-xl font-bold text-slate-100">
                          {user.display_name}
                        </h2>
                        <button
                          onClick={() => setIsEditingMeta(true)}
                          className="p-1 rounded-xs text-slate-500 hover:text-slate-300"
                          title="Editar nombre y apodos"
                        >
                          <Edit2 size={13} />
                        </button>
                      </div>
                      <p className="text-xs text-slate-400 font-mono">
                        @{user.username} · ID: {user.user_id}
                      </p>
                      {user.nicknames && user.nicknames.length > 0 && (
                        <div className="flex items-center space-x-1.5 mt-1.5 flex-wrap gap-1">
                          <span className="text-[11px] text-slate-500">Apodos:</span>
                          {user.nicknames.map((nick, idx) => (
                            <span
                              key={idx}
                              className="text-[11px] px-2 py-0.5 rounded-xs bg-dark-800 text-slate-300 border border-dark-700"
                            >
                              {nick}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={editDisplayName}
                        onChange={(e) => setEditDisplayName(e.target.value)}
                        placeholder="Nombre para mostrar"
                        className="px-2.5 py-1 rounded-xs bg-dark-800 border border-dark-600 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 w-64"
                      />
                      <input
                        type="text"
                        value={editNicknames}
                        onChange={(e) => setEditNicknames(e.target.value)}
                        placeholder="Apodos separados por comas"
                        className="px-2.5 py-1 rounded-xs bg-dark-800 border border-dark-600 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 w-64"
                      />
                      <div className="flex space-x-2">
                        <button
                          onClick={handleSaveMeta}
                          className="btn-primary px-3 py-1 text-xs font-medium flex items-center space-x-1"
                        >
                          <Save size={12} />
                          <span>Guardar</span>
                        </button>
                        <button
                          onClick={() => setIsEditingMeta(false)}
                          className="btn-secondary px-3 py-1 text-xs"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Estadísticas de Locución */}
              <div className="flex items-center space-x-5 text-xs text-slate-300 border-t md:border-t-0 md:border-l border-dark-750 pt-3 md:pt-0 md:pl-5">
                <div>
                  <div className="text-slate-500 text-[11px]">Voz Registrada</div>
                  <div className="text-sm font-bold text-slate-200 mt-0.5 flex items-center space-x-1.5">
                    <Clock size={14} className="text-cyan-400" />
                    <span>{Math.round(user.total_speaking_seconds / 60)} min</span>
                  </div>
                </div>
                <div>
                  <div className="text-slate-500 text-[11px]">Palabras Totales</div>
                  <div className="text-sm font-bold text-slate-200 mt-0.5 flex items-center space-x-1.5">
                    <BookOpen size={14} className="text-emerald-400" />
                    <span>{(lexicon.total_words || 0).toLocaleString()}</span>
                  </div>
                </div>
                <div>
                  <div className="text-slate-500 text-[11px]">Palabras Únicas</div>
                  <div className="text-sm font-bold text-slate-200 mt-0.5 flex items-center space-x-1.5">
                    <span className="text-violet-400 font-mono text-sm">◈</span>
                    <span>{(lexicon.total_unique_words || lexicon.unique_words || 0).toLocaleString()}</span>
                  </div>
                </div>
                <div>
                  <div className="text-slate-500 text-[11px]">Muestra TTS</div>
                  <div className="text-sm font-bold mt-0.5 flex items-center space-x-1.5">
                    {user.has_voice_sample ? (
                      <span className="text-emerald-400 flex items-center space-x-1">
                        <Check size={14} />
                        <span>F5-TTS Lista</span>
                      </span>
                    ) : (
                      <span className="text-slate-500">Pendiente</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Grid 2 Columnas: Rasgos Big Five vs Arquetipo & Modismos */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              
              {/* Columna Izquierda: Rasgos Big Five Moldeados */}
              <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 space-y-4">
                <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
                  <div className="flex items-center space-x-2">
                    <Sliders size={16} className="text-indigo-400" />
                    <h3 className="font-semibold text-slate-200 text-sm">
                      Rasgos de Personalidad Big Five
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Moldeados dinámicamente
                  </span>
                </div>

                <div className="space-y-3.5">
                  {Object.entries(BIG_FIVE_NAMES).map(([traitKey, info]) => {
                    const traitData = bigFive[traitKey] || { score: 0.5, confidence: 0.5, evidence_quotes: [] };
                    const score = traitData.score ?? 0.5;
                    const percent = Math.round(score * 100);
                    const quotes = traitData.evidence_quotes || [];

                    return (
                      <div key={traitKey} className="space-y-1.5 p-3 rounded-xs bg-dark-900 border border-dark-750">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-300">{info.name}</span>
                          <span className="font-mono font-semibold text-indigo-300">{score.toFixed(2)} ({percent}%)</span>
                        </div>
                        <div className="w-full bg-dark-800 rounded-none h-2 overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full rounded-none transition-all duration-500"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <p className="text-[11px] text-slate-500">{info.desc}</p>
                        
                        {quotes.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-dark-800 space-y-1">
                            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold flex items-center space-x-1">
                              <Quote size={10} />
                              <span>Citas de Evidencia</span>
                            </span>
                            {quotes.slice(0, 2).map((quote, qIdx) => {
                              const quoteText = typeof quote === 'string' ? quote : (quote?.quote || JSON.stringify(quote));
                              return (
                                <p key={qIdx} className="text-[11px] text-slate-400 italic pl-2 border-l border-dark-700">
                                  "{quoteText}"
                                </p>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Columna Derecha: Arquetipo, Estilo de Humor y Cadencia */}
              <div className="space-y-5">
                {/* Arquetipo */}
                <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 space-y-3.5">
                  <div className="border-b border-dark-700/60 pb-2.5">
                    <h3 className="font-semibold text-slate-200 text-sm">
                      Arquetipo y Rol Conversacional
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                    <div className="p-3 rounded-xs bg-dark-900 border border-dark-750">
                      <div className="text-slate-500 text-[11px]">Rol Principal</div>
                      <div className="font-semibold text-slate-200 mt-1">
                        {archetype.primary_role || 'No clasificado aún'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xs bg-dark-900 border border-dark-750">
                      <div className="text-slate-500 text-[11px]">Rol Secundario</div>
                      <div className="font-semibold text-slate-200 mt-1">
                        {archetype.secondary_role || 'No clasificado'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xs bg-dark-900 border border-dark-750 sm:col-span-2">
                      <div className="text-slate-500 text-[11px]">Estilo de Humor</div>
                      <div className="font-semibold text-slate-200 mt-1">
                        {archetype.humor_style || 'Neutro / Conversacional'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xs bg-dark-900 border border-dark-750 sm:col-span-2">
                      <div className="text-slate-500 text-[11px]">Cadencia y Turno de Habla</div>
                      <div className="font-semibold text-slate-200 mt-1">
                        {archetype.dialogue_cadence || 'Moderada'}
                      </div>
                    </div>
                  </div>

                  {/* Modismos y Muletillas */}
                  {archetype.preferred_idioms && archetype.preferred_idioms.length > 0 && (
                    <div className="pt-2">
                      <div className="text-xs text-slate-400 font-medium mb-1.5">
                        Modismos y Muletillas Clave:
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {archetype.preferred_idioms.map((idiom, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-xs bg-dark-900 border border-dark-750 text-indigo-300 text-xs font-mono"
                          >
                            {idiom}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Gustos y Preferencias Reales (Likes y Dislikes) */}
                {((likes && likes.length > 0) || (dislikes && dislikes.length > 0)) && (
                  <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 space-y-3.5">
                    <div className="border-b border-dark-700/60 pb-2.5 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Heart size={16} className="text-rose-400" />
                        <h3 className="font-semibold text-slate-200 text-sm">
                          Gustos y Preferencias Reales
                        </h3>
                      </div>
                      <span className="text-[11px] text-slate-500">
                        Detectados en conversaciones
                      </span>
                    </div>

                    <div className="space-y-3">
                      {likes && likes.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold text-emerald-400 mb-1.5 flex items-center space-x-1.5">
                            <span>❤️ Cosas que le gustan / Pasiones:</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {likes.map((like, idx) => (
                              <span
                                key={idx}
                                className="px-2.5 py-1 rounded-xs bg-emerald-950/40 border border-emerald-700/50 text-emerald-300 text-xs font-medium"
                              >
                                {like}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {dislikes && dislikes.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold text-rose-400 mb-1.5 flex items-center space-x-1.5">
                            <span>❌ Cosas que le desagradan / No le gustan:</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {dislikes.map((dislike, idx) => (
                              <span
                                key={idx}
                                className="px-2.5 py-1 rounded-xs bg-rose-950/40 border border-rose-700/50 text-rose-300 text-xs font-medium"
                              >
                                {dislike}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Diccionario de Palabras Utilizadas */}
                <div className="p-4 rounded-xs bg-dark-850 border border-dark-700 space-y-3.5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-dark-700/60 pb-2.5">
                    <div>
                      <h3 className="font-semibold text-slate-200 text-sm">
                        Diccionario y Frecuencia de Palabras
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        {(lexicon.total_unique_words || lexicon.unique_words || filteredWords.length).toLocaleString()} términos únicos catalogados
                      </p>
                    </div>

                    {/* Filtros */}
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setFilterStopwords(!filterStopwords)}
                        className={`px-2.5 py-1 rounded-xs text-[11px] border font-medium transition-colors flex items-center space-x-1 ${
                          filterStopwords
                            ? 'bg-indigo-950/60 border-indigo-700/70 text-indigo-300'
                            : 'bg-dark-800 border-dark-700 text-slate-400'
                        }`}
                        title="Ocultar palabras comunes como 'de', 'la', 'que', etc."
                      >
                        <Filter size={11} />
                        <span>Sin Stopwords</span>
                      </button>
                    </div>
                  </div>

                  {/* Input buscar palabra */}
                  <input
                    type="text"
                    placeholder="Filtrar palabra en diccionario..."
                    value={wordSearch}
                    onChange={(e) => setWordSearch(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-xs bg-dark-900 border border-dark-750 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />

                  {/* Lista de palabras con frecuencias */}
                  <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
                    {filteredWords.slice(0, 150).map(([word, count], idx) => {
                      const barWidth = Math.round((count / maxWordFreq) * 100);
                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-2 rounded-xs bg-dark-900 border border-dark-750 text-xs"
                        >
                          <div className="flex items-center space-x-2 flex-1 mr-3">
                            <span className="font-mono text-slate-300 font-medium">{word}</span>
                          </div>

                          <div className="flex items-center space-x-3 w-40">
                            <div className="flex-1 bg-dark-800 rounded-none h-1.5 overflow-hidden">
                              <div
                                className="bg-cyan-500 h-full rounded-none"
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                            <span className="font-mono text-slate-400 text-[11px] w-8 text-right">
                              {count}
                            </span>
                          </div>
                        </div>
                      );
                    })}

                    {filteredWords.length === 0 && (
                      <div className="text-center py-6 text-slate-500 text-xs">
                        No hay palabras que coincidan con el filtro actual
                      </div>
                    )}
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
}
