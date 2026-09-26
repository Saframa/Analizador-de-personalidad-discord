const BASE_URL = 'http://127.0.0.1:8000';

export async function fetchStatus() {
  const res = await fetch(`${BASE_URL}/api/status`);
  if (!res.ok) throw new Error('Error al obtener estado');
  return res.json();
}

export async function toggleRecorder() {
  const res = await fetch(`${BASE_URL}/api/daemon/recorder/toggle`, { method: 'POST' });
  return res.json();
}

export async function toggleWatcher() {
  const res = await fetch(`${BASE_URL}/api/daemon/watcher/toggle`, { method: 'POST' });
  return res.json();
}

export async function triggerProcessAll() {
  const res = await fetch(`${BASE_URL}/api/daemon/process-all`, { method: 'POST' });
  return res.json();
}

export async function fetchGlobalStats() {
  const res = await fetch(`${BASE_URL}/api/stats/global`);
  if (!res.ok) throw new Error('Error al obtener estadísticas globales');
  return res.json();
}

export async function fetchUsers() {
  const res = await fetch(`${BASE_URL}/api/users`);
  if (!res.ok) throw new Error('Error al listar usuarios');
  return res.json();
}

export async function fetchUserDetail(userId) {
  const res = await fetch(`${BASE_URL}/api/users/${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error(`Error al obtener usuario ${userId}`);
  return res.json();
}

export async function updateUserData(userId, payload) {
  const res = await fetch(`${BASE_URL}/api/users/${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Error al actualizar datos');
  return res.json();
}

export async function uploadAvatar(userId, file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/api/users/${encodeURIComponent(userId)}/avatar`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Error al subir avatar');
  return res.json();
}

export async function sendChatMessage(userId, message, backend = 'auto') {
  const res = await fetch(`${BASE_URL}/api/chat/${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, backend }),
  });
  if (!res.ok) throw new Error('Error en el chat');
  return res.json();
}

export async function clearChatHistory(userId) {
  const res = await fetch(`${BASE_URL}/api/chat/${encodeURIComponent(userId)}/clear`, {
    method: 'POST',
  });
  return res.json();
}

export async function synthesizeSpeech(userId, text) {
  const res = await fetch(`${BASE_URL}/api/tts/${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Error al sintetizar voz');
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function fetchDiscordChannels() {
  const res = await fetch(`${BASE_URL}/api/discord/channels`);
  if (!res.ok) throw new Error('Error al obtener canales de Discord');
  return res.json();
}

export async function joinDiscordChannel(channelId) {
  const res = await fetch(`${BASE_URL}/api/discord/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ channel_id: channelId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al conectar al canal');
  }
  return res.json();
}

export async function leaveDiscordChannel() {
  const res = await fetch(`${BASE_URL}/api/discord/leave`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Error al desconectar del canal');
  }
  return res.json();
}

