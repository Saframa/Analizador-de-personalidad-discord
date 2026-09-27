const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');

let mainWindow;
let pythonProcess = null;

const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;
const API_PORT = 8000;
const API_URL = `http://127.0.0.1:${API_PORT}`;

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
            console.log(`[Electron] Liberando proceso previo en puerto ${port} (PID ${pid})...`);
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

function startPythonBackend() {
  // Asegurar puerto limpio para no servir código viejo en memoria
  killProcessOnPort(API_PORT);

  const aiPipelineDir = path.resolve(__dirname, '..', '..', 'ai-pipeline');
  console.log(`[Electron] Iniciando backend FastAPI desde ${aiPipelineDir}...`);

  pythonProcess = spawn('python', ['-u', 'api/server.py'], {
    cwd: aiPipelineDir,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: 'pipe',
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[FastAPI]: ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[FastAPI Err]: ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[FastAPI] Proceso terminado con código ${code}`);
  });
}

function killPython() {
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

app.on('will-quit', () => {
  killPython();
});

process.on('exit', () => {
  killPython();
});
