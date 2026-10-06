import React, { useState, useEffect, useRef } from 'react';
import { 
  Volume2, 
  RotateCw, 
  Download, 
  Check, 
  AlertCircle
} from 'lucide-react';
import { fetchUsers, synthesizeSpeech } from '../api';

const QUICK_PROMPTS = [
  "¿Qué hacés, bo? ¿Todo bien? Acá andamos viendo qué sale.",
  "Mirá que no me convence para nada eso, posta te lo digo.",
  "Na, dejate de joder, eso quedó totalmente flama.",
  "Che, ¿vamos a jugar al Rocket o te vas a seguir haciendo el distraído?"
];

export default function TtsStudioView({ isBackendReady }) {
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [inputText, setInputText] = useState(QUICK_PROMPTS[0]);
  const [loading, setLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    fetchUsers().then((data) => {
      const uList = Array.isArray(data) ? data : (data?.users || []);
      setUsers(uList);
      if (uList.length > 0 && !selectedUserId) {
        const withVoice = uList.find((u) => u.has_voice_sample);
        setSelectedUserId(withVoice ? withVoice.user_id : uList[0].user_id);
      }
    }).catch(console.error);
  }, [isBackendReady]);

  const handleSynthesize = async () => {
    if (!selectedUserId || !inputText.trim()) return;
    try {
      setLoading(true);
      setError(null);
      const url = await synthesizeSpeech(selectedUserId, inputText.trim());
      setAudioUrl(url);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedUser = users.find((u) => u.user_id === selectedUserId);

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto overflow-y-auto h-full">
      {/* Título */}
      <div>
        <h1 className="text-xl font-bold text-slate-100 tracking-tight">
          Estudio de Síntesis y Clonación de Voz
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Prueba el modelo local F5-TTS en tu NVIDIA RTX 4070 con las muestras extraídas de Discord
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Panel de Configuración y Selección de Usuario */}
        <div className="p-5 rounded-xs bg-dark-900 border border-dark-700 space-y-4">
          <div className="border-b border-dark-700/60 pb-3">
            <h2 className="font-semibold text-slate-200 text-sm">
              Selección de Voz
            </h2>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">
                Amigo / Perfil:
              </label>
              <select
                value={selectedUserId}
                onChange={(e) => {
                  setSelectedUserId(e.target.value);
                  setAudioUrl(null);
                }}
                className="w-full px-3 py-2 rounded-xs bg-dark-850 border border-dark-700 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                {users.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.display_name} (@{u.username}) {u.has_voice_sample ? '• Con Voz' : '• Sin Muestra'}
                  </option>
                ))}
              </select>
            </div>

            {selectedUser && (
              <div className="p-3.5 rounded-xs bg-dark-850 border border-dark-750 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Estado de muestra:</span>
                  {selectedUser.has_voice_sample ? (
                    <span className="text-emerald-400 font-medium flex items-center space-x-1">
                      <Check size={13} />
                      <span>Muestra Lista</span>
                    </span>
                  ) : (
                    <span className="text-amber-400 font-medium flex items-center space-x-1">
                      <AlertCircle size={13} />
                      <span>Falta Muestra</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-slate-500">
                  <span>Voz registrada:</span>
                  <span className="text-slate-300 font-mono">
                    {selectedUser.speaking_formatted || '0m'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Panel de Texto y Síntesis */}
        <div className="lg:col-span-2 p-5 rounded-xs bg-dark-900 border border-dark-700 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="border-b border-dark-700/60 pb-3 flex items-center justify-between">
              <h2 className="font-semibold text-slate-200 text-sm">
                Texto a Sintetizar
              </h2>
              <span className="text-[11px] text-slate-500">
                F5-TTS Español Neutro/Rioplatense
              </span>
            </div>

            <textarea
              rows={4}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Escribe la frase que quieres que diga..."
              className="w-full p-3 rounded-xs bg-dark-850 border border-dark-700 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none font-sans"
            />

            {/* Frases rápidas */}
            <div className="space-y-1.5">
              <span className="text-[11px] text-slate-500 font-medium">
                Frases de prueba rápida:
              </span>
              <div className="flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => setInputText(prompt)}
                    className="text-left text-[11px] px-2.5 py-1 rounded-xs bg-dark-850 hover:bg-dark-800 text-slate-400 hover:text-slate-200 border border-dark-750 transition-colors"
                  >
                    "{prompt.slice(0, 32)}..."
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-3 pt-4 border-t border-dark-700/60">
            {error && (
              <div className="p-3 rounded-xs bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300">
                {error}
              </div>
            )}

            <div className="flex items-center space-x-3">
              <button
                onClick={handleSynthesize}
                disabled={loading || !inputText.trim() || !selectedUser?.has_voice_sample}
                className="flex-1 py-2.5 px-4 rounded-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-semibold flex items-center justify-center space-x-2 transition-colors shadow-sm"
              >
                {loading ? (
                  <>
                    <RotateCw size={15} className="animate-spin" />
                    <span>Sintetizando en GPU RTX 4070...</span>
                  </>
                ) : (
                  <>
                    <Volume2 size={15} />
                    <span>Generar y Reproducir Audio</span>
                  </>
                )}
              </button>

              {audioUrl && (
                <a
                  href={audioUrl}
                  download={`tts_${selectedUserId}.wav`}
                  className="p-2.5 rounded-xs bg-dark-850 hover:bg-dark-800 text-slate-300 border border-dark-700 transition-colors"
                  title="Descargar archivo WAV"
                >
                  <Download size={16} />
                </a>
              )}
            </div>

            {audioUrl && (
              <div className="pt-2">
                <audio ref={audioRef} controls src={audioUrl} className="w-full h-8" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
