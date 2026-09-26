import React, { useState, useEffect } from 'react';
import Navigation from './components/Navigation';
import GlobalStatsView from './components/GlobalStatsView';
import UsersView from './components/UsersView';
import HardwareView from './components/HardwareView';
import TtsStudioView from './components/TtsStudioView';
import UserDetailModal from './components/UserDetailModal';
import ChatDrawer from './components/ChatDrawer';
import { fetchStatus } from './api';
import { AlertCircle, RotateCw } from 'lucide-react';

export default function App() {
  const [currentTab, setCurrentTab] = useState('stats');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState(false);

  // Modales y Drawers
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [chatUserId, setChatUserId] = useState(null);

  const pollStatus = async () => {
    try {
      const data = await fetchStatus();
      setStatus(data);
      setStatusError(false);
    } catch (err) {
      setStatusError(true);
    }
  };

  useEffect(() => {
    pollStatus();
    const interval = setInterval(pollStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-dark-950 text-slate-200">
      {/* Navegación y Header */}
      <Navigation
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        isMenuOpen={isMenuOpen}
        onToggleMenu={() => setIsMenuOpen(!isMenuOpen)}
        status={status}
      />

      {/* Banner de desconexión del backend si ocurre */}
      {statusError && (
        <div className="bg-amber-950/80 border-b border-amber-800/80 px-4 py-2 text-xs text-amber-200 flex items-center justify-between z-20">
          <div className="flex items-center space-x-2">
            <AlertCircle size={14} className="text-amber-400" />
            <span>Conectando con el servidor local de IA en http://127.0.0.1:8000...</span>
          </div>
          <button
            onClick={pollStatus}
            className="flex items-center space-x-1 text-amber-300 hover:text-white underline text-xs"
          >
            <RotateCw size={12} />
            <span>Reintentar</span>
          </button>
        </div>
      )}

      {/* Contenedor Principal de Vistas */}
      <main className="flex-1 overflow-hidden relative">
        {currentTab === 'stats' && (
          <GlobalStatsView
            onSelectUser={(userId) => setSelectedUserId(userId)}
          />
        )}

        {currentTab === 'users' && (
          <UsersView
            onSelectUser={(userId) => setSelectedUserId(userId)}
            onOpenChat={(userId) => setChatUserId(userId)}
          />
        )}

        {currentTab === 'hardware' && (
          <HardwareView
            status={status}
            onRefresh={pollStatus}
          />
        )}

        {currentTab === 'tts' && (
          <TtsStudioView />
        )}
      </main>

      {/* Modal de Inspección de Usuario */}
      {selectedUserId && (
        <UserDetailModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
          onOpenChat={(uid) => {
            setSelectedUserId(null);
            setChatUserId(uid);
          }}
        />
      )}

      {/* Slide-over Drawer de Chat con Gemelo */}
      {chatUserId && (
        <ChatDrawer
          userId={chatUserId}
          onClose={() => setChatUserId(null)}
        />
      )}
    </div>
  );
}
