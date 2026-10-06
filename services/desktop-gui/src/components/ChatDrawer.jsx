import React, { useState, useEffect, useRef } from 'react';
import { 
  X, 
  Send, 
  Trash2, 
  Volume2, 
  RotateCw
} from 'lucide-react';
import { sendChatMessage, clearChatHistory, synthesizeSpeech, fetchUserDetail } from '../api';

export default function ChatDrawer({ userId, onClose }) {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [userProfile, setUserProfile] = useState(null);
  const [backend, setBackend] = useState('auto');
  const [playingAudioIdx, setPlayingAudioIdx] = useState(null);
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    if (userId) {
      fetchUserDetail(userId).then(setUserProfile).catch(console.error);
      setMessages([
        {
          role: 'system_greeting',
          content: `Conectado al gemelo digital de ${userId}. Escribe un mensaje para conversar.`,
        }
      ]);
    }
  }, [userId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    const text = inputText.trim();
    if (!text || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      const res = await sendChatMessage(userId, text, backend);
      const replyText = res.reply || res.response || '';
      const assistantMsg = {
        role: 'assistant',
        content: replyText,
        model_used: res.model_used || (backend === 'auto' ? 'Gemini / LLaMA' : backend),
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'error',
          content: `Error al obtener respuesta: ${err.message}`,
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = async () => {
    if (!window.confirm('¿Reiniciar el contexto de esta conversación?')) return;
    try {
      await clearChatHistory(userId);
      setMessages([
        {
          role: 'system_greeting',
          content: 'Conversación reiniciada. El gemelo ha olvidado los turnos previos.',
        }
      ]);
    } catch (err) {
      console.error(err);
    }
  };

  const handlePlayVoice = async (text, idx) => {
    const cleanText = (text || '').trim();
    if (!cleanText) {
      alert('No hay texto para sintetizar.');
      return;
    }
    try {
      setPlayingAudioIdx(idx);
      const audioUrl = await synthesizeSpeech(userId, cleanText);
      if (audioRef.current) {
        audioRef.current.src = audioUrl;
        audioRef.current.play();
        audioRef.current.onended = () => setPlayingAudioIdx(null);
      }
    } catch (err) {
      alert(`Error al sintetizar voz: ${err.message}`);
      setPlayingAudioIdx(null);
    }
  };

  if (!userId) return null;

  const displayName = userProfile?.display_name || userId;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs select-none">
      <div className="w-full max-w-xl bg-dark-900 border-l border-dark-700 h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        
        {/* Header del Chat */}
        <div className="h-14 px-5 border-b border-dark-700 bg-dark-850 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-xs bg-dark-800 border border-dark-650 overflow-hidden flex items-center justify-center text-xs font-bold text-slate-300 flex-shrink-0">
              {userProfile?.has_avatar ? (
                <img
                  src={`http://127.0.0.1:8000${userProfile.avatar_url}`}
                  alt={displayName}
                  className="w-full h-full object-cover"
                />
              ) : (
                displayName.slice(0, 2).toUpperCase()
              )}
            </div>
            <div>
              <div className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                <span>{displayName}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-xs bg-dark-800 text-indigo-300 border border-dark-700 font-normal">
                  Gemelo Digital
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-mono">
                @{userProfile?.username || userId}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* Selector de backend */}
            <select
              value={backend}
              onChange={(e) => setBackend(e.target.value)}
              className="text-xs bg-dark-800 text-slate-300 border border-dark-700 rounded-xs px-2 py-1 focus:outline-none"
              title="Motor LLM"
            >
              <option value="auto">Motor: Auto</option>
              <option value="gemini">Gemini Flash</option>
              <option value="llama">LLaMA 3.3 (Groq)</option>
            </select>

            {/* Reiniciar chat */}
            <button
              onClick={handleClearChat}
              className="p-1.5 rounded-xs bg-dark-800 hover:bg-dark-750 text-slate-400 hover:text-slate-200 border border-dark-700 transition-colors"
              title="Reiniciar chat"
            >
              <Trash2 size={15} />
            </button>

            {/* Cerrar Drawer */}
            <button
              onClick={onClose}
              className="p-1.5 rounded-xs bg-dark-800 hover:bg-dark-750 text-slate-400 hover:text-white border border-dark-700 transition-colors"
              title="Cerrar chat"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* Zona de Mensajes */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
          {messages.map((msg, index) => {
            if (msg.role === 'system_greeting') {
              return (
                <div
                  key={index}
                  className="p-3 rounded-xs bg-dark-850/80 border border-dark-750 text-center text-xs text-slate-400"
                >
                  {msg.content}
                </div>
              );
            }

            if (msg.role === 'error') {
              return (
                <div
                  key={index}
                  className="p-3 rounded-xs bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300"
                >
                  {msg.content}
                </div>
              );
            }

            const isUser = msg.role === 'user';

            return (
              <div
                key={index}
                className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-xs px-3.5 py-2.5 text-sm ${
                    isUser
                      ? 'bg-indigo-600 text-white'
                      : 'bg-dark-850 border border-dark-700 text-slate-200'
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed select-text">{msg.content}</p>

                  {/* Acciones debajo de la respuesta del gemelo */}
                  {!isUser && (
                    <div className="mt-2 pt-1.5 border-t border-dark-750 flex items-center justify-between text-[11px] text-slate-500">
                      <div className="flex items-center space-x-1.5 font-mono">
                        <span>{msg.model_used || 'LLM'}</span>
                        {msg.timestamp && <span>· {msg.timestamp}</span>}
                      </div>

                      {/* Botón sutil para escuchar con su voz clonada */}
                      {userProfile?.has_voice_sample && (
                        <button
                          onClick={() => handlePlayVoice(msg.content, index)}
                          disabled={playingAudioIdx === index}
                          className="flex items-center space-x-1 text-slate-400 hover:text-indigo-300 transition-colors p-1 rounded-xs hover:bg-dark-800"
                          title="Escuchar con voz clonada F5-TTS"
                        >
                          <Volume2 size={13} className={playingAudioIdx === index ? "text-indigo-400 animate-pulse" : ""} />
                          <span>{playingAudioIdx === index ? 'Generando...' : 'Escuchar'}</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Indicador de escritura */}
          {loading && (
            <div className="flex items-center space-x-2 text-slate-500 text-xs p-2">
              <RotateCw size={13} className="animate-spin text-indigo-400" />
              <span>{displayName} está pensando...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input de Mensaje al pie */}
        <form
          onSubmit={handleSendMessage}
          className="p-3 border-t border-dark-700 bg-dark-850 flex items-center space-x-2"
        >
          <input
            type="text"
            placeholder={`Habla con ${displayName}...`}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={loading}
            className="flex-1 px-3.5 py-2 rounded-xs bg-dark-900 border border-dark-700 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !inputText.trim()}
            className="p-2 rounded-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white transition-colors"
            title="Enviar mensaje"
          >
            <Send size={16} />
          </button>
        </form>

        {/* Elemento de Audio Oculto */}
        <audio ref={audioRef} className="hidden" />
      </div>
    </div>
  );
}
