const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess = null;

const isDev = process.env.NODE_ENV !== 'production' && !app.isPackaged;
const API_PORT = 8000;
const API_URL = `http://127.0.0.1:${API_PORT}`;

function checkApiAlive(callback) {
  const req = http.get(`${API_URL}/api/status`, (res) => {
    if (res.statusCode === 200) {
      callback(true);
    } else {
      callback(false);
    }
  });
  req.on('error', () => callback(false));
  req.setTimeout(1000, () => {
    req.abort();
    callback(false);
  });
}

function startPythonBackend() {
  checkApiAlive((alive) => {
    if (alive) {
      console.log('FastAPI backend already running.');
      return;
    }

    const aiPipelineDir = path.resolve(__dirname, '..', '..', 'ai-pipeline');
    console.log(`Starting FastAPI backend from ${aiPipelineDir}...`);

    pythonProcess = spawn('python', ['api/server.py'], {
      cwd: aiPipelineDir,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: 'pipe',
    });

    pythonProcess.stdout.on('data', (data) => {
      console.log(`[Python]: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      console.error(`[Python Err]: ${data}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`Python backend exited with code ${code}`);
    });
  });
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

  const fs = require('fs');
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
  if (pythonProcess) {
    try {
      pythonProcess.kill();
    } catch (e) {}
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    try {
      pythonProcess.kill();
    } catch (e) {}
  }
});
