const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const net = require('net');
const fs = require('fs');

let mainWindow;
let pythonProcess = null;
let isQuitting = false;
let restartAttempts = 0;
const MAX_RESTARTS = 3;

const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;
const API_PORT = 8000;
const API_URL = `http://127.0.0.1:${API_PORT}`;

function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', (err) => {
      if (err.code === 'EADDRINUSE') {
        resolve(true);
      } else {
        resolve(false);
      }
    });
    server.once('listening', () => {
      server.close(() => resolve(false));
    });
    server.listen(port, '127.0.0.1');
  });
}

function checkBackendHealth(timeoutMs = 600) {
  return new Promise((resolve) => {
    const req = http.get(`${API_URL}/api/status`, { timeout: timeoutMs }, (res) => {
      if (res.statusCode === 200) {
        resolve(true);
      } else {
        resolve(false);
      }
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function killProcessOnPort(port) {
  if (process.platform === 'win32') {
    try {
      const out = execSync(`netstat -ano | findstr :${port}`, { encoding: 'utf-8' });
      const lines = out.split('\n');
      for (const line of lines) {
        if (line.includes('LISTENING')) {
          const parts = line.trim().split(/\s+/);
          const pid = parts[parts.length - 1];
          if (pid && pid !== '0' && pid !== process.pid.toString()) {
            console.log(`[Electron] Liberando proceso no responsivo en puerto ${port} (PID ${pid})...`);
            try {
              execSync(`taskkill /F /PID ${pid}`);
            } catch (err) {}
          }
        }
      }
    } catch (e) {
      // Puerto ya libre
    }
  }
}

async function waitForPortToBeFree(port, maxWaitMs = 2500) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const inUse = await isPortInUse(port);
    if (!inUse) return true;
    await new Promise((r) => setTimeout(r, 150));
  }
  return !(await isPortInUse(port));
}

function resolvePythonCommand() {
  if (process.env.PYTHON_PATH && fs.existsSync(process.env.PYTHON_PATH)) {
    return process.env.PYTHON_PATH;
  }
  const candidates = ['python', 'py', 'python3'];
  for (const cmd of candidates) {
    try {
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch (e) {}
  }
  return 'python';
}

async function startPythonBackend() {
  if (isQuitting) return;

  // 1. Si el backend ya está vivo y respondiendo con HTTP 200, no lo interrumpimos
  const isHealthy = await checkBackendHealth(500);
  if (isHealthy) {
    console.log(`[Electron] Backend FastAPI ya está en ejecución y saludable en ${API_URL}.`);
    restartAttempts = 0;
    return;
  }

  // 2. Si el puerto está ocupado por un proceso zombie o colgado, liberarlo limpiamente
  const inUse = await isPortInUse(API_PORT);
  if (inUse) {
    console.log(`[Electron] Puerto ${API_PORT} ocupado pero no responde. Liberando...`);
    killProcessOnPort(API_PORT);
    const freed = await waitForPortToBeFree(API_PORT, 2500);
    if (!freed) {
      console.warn(`[Electron] Advertencia: El socket del puerto ${API_PORT} tardó en liberarse.`);
    }
  }

  const aiPipelineDir = path.resolve(__dirname, '..', '..', 'ai-pipeline');
  const pythonCmd = resolvePythonCommand();
  console.log(`[Electron] Iniciando backend FastAPI (${pythonCmd}) desde ${aiPipelineDir}...`);

  try {
    pythonProcess = spawn(pythonCmd, ['-u', 'api/server.py'], {
      cwd: aiPipelineDir,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: 'pipe',
    });
  } catch (err) {
    console.error(`[Electron Error] No se pudo lanzar el proceso de Python:`, err);
    return;
  }

  const pid = pythonProcess.pid;
  const launchTime = Date.now();

  pythonProcess.stdout.on('data', (data) => {
    const text = data.toString().trim();
    console.log(`[FastAPI]: ${text}`);
    if (text.includes('Application startup complete')) {
      restartAttempts = 0; // Reiniciar contador tras arranque exitoso
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[FastAPI Err]: ${data.toString().trim()}`);
  });

  pythonProcess.on('close', async (code) => {
    console.log(`[FastAPI] Proceso ${pid} terminado con código ${code}`);
    pythonProcess = null;

    // Si se cerró inesperadamente durante el arranque y no estamos saliendo de la app
    if (!isQuitting && code !== 0 && code !== null) {
      const aliveDuration = Date.now() - launchTime;
      if (aliveDuration < 15000 && restartAttempts < MAX_RESTARTS) {
        restartAttempts++;
        console.warn(`[Electron] FastAPI cayó prematuramente (${aliveDuration}ms). Reintento ${restartAttempts}/${MAX_RESTARTS} en 1.5s...`);
        setTimeout(() => {
          startPythonBackend();
        }, 1500);
      }
    }
  });
}

function killPython() {
  isQuitting = true;
  if (pythonProcess && pythonProcess.pid) {
    console.log(`[Electron] Deteniendo backend FastAPI (PID ${pythonProcess.pid})...`);
    if (process.platform === 'win32') {
      try {
        execSync(`taskkill /F /T /PID ${pythonProcess.pid}`);
      } catch (e) {}
    } else {
      pythonProcess.kill();
    }
    pythonProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#07090e',
    title: 'Discord Twin Profiler',
    titleBarStyle: 'default',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  const distPath = path.join(__dirname, '..', 'dist', 'index.html');
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173').catch(() => {
      if (fs.existsSync(distPath)) {
        mainWindow.loadFile(distPath);
      }
    });
  } else if (fs.existsSync(distPath)) {
    mainWindow.loadFile(distPath);
  } else {
    mainWindow.loadURL('http://localhost:5173');
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https:') || url.startsWith('http:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  killPython();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killPython();
});

app.on('will-quit', () => {
  killPython();
});

process.on('SIGINT', () => {
  killPython();
  process.exit(0);
});

process.on('SIGTERM', () => {
  killPython();
  process.exit(0);
});

process.on('exit', () => {
  killPython();
});
