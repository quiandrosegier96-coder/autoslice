"use strict";

/**
 * AutoSlice — Electron main process
 *
 * Startup sequence:
 *   1. Spawn the PyInstaller backend (autoslice_backend.exe)
 *   2. Spawn the Next.js standalone server (node server.js)
 *   3. Poll GET http://localhost:8000/health until ready (60 s timeout)
 *   4. Create the BrowserWindow and load http://localhost:3000
 *   5. On window close / app quit, terminate both child processes
 */

const { app, BrowserWindow, dialog, shell, ipcMain, nativeImage } = require("electron");
const { autoUpdater } = require("electron-updater");
const path   = require("path");
const http   = require("http");
const crypto = require("crypto");
const { spawn } = require("child_process");

// ── Resource paths ─────────────────────────────────────────────────────────

// In a packaged app, extra resources land in process.resourcesPath.
// In dev (npm start), they live in electron/resources/.
const RESOURCES = app.isPackaged
  ? process.resourcesPath
  : path.join(__dirname, "resources");

const BACKEND_EXE  = path.join(RESOURCES, "backend", "autoslice_backend.exe");
const NODE_EXE     = path.join(RESOURCES, "node",    "node.exe");
const SERVER_JS    = path.join(RESOURCES, "frontend", "server.js");
const FRONTEND_DIR = path.join(RESOURCES, "frontend");

const BACKEND_URL  = "http://localhost:8000";
const FRONTEND_URL = "http://localhost:3000";
const HEALTH_URL   = `${BACKEND_URL}/health`;

// ── Process handles ────────────────────────────────────────────────────────

let backendProc  = null;
let frontendProc = null;

// ── Log directory (AppData/Roaming/AutoSlice/logs) ─────────────────────────

const LOG_DIR = path.join(app.getPath("appData"), "AutoSlice", "logs");
const fs      = require("fs");
try { fs.mkdirSync(LOG_DIR, { recursive: true }); } catch (_) {}

function openLog(name) {
  try {
    return fs.openSync(path.join(LOG_DIR, name), "w");
  } catch (_) {
    return "ignore";
  }
}

function localJwtSecret(userDataDir) {
  const secretPath = path.join(userDataDir, ".jwt-secret");
  try {
    if (fs.existsSync(secretPath)) return fs.readFileSync(secretPath, "utf8").trim();
    const secret = crypto.randomBytes(48).toString("base64url");
    fs.writeFileSync(secretPath, secret, { encoding: "utf8", mode: 0o600, flag: "wx" });
    return secret;
  } catch (error) {
    throw new Error(`Unable to initialize local authentication storage: ${error.message}`);
  }
}

// ── Spawn servers ──────────────────────────────────────────────────────────

function startServers() {
  const userDataDir = app.getPath("userData");
  const uploadDir   = path.join(userDataDir, "temp");
  const dbPath      = path.join(userDataDir, "autoslice.db");
  const dataDir     = path.join(RESOURCES, "backend", "_internal", "data");

  try { fs.mkdirSync(uploadDir, { recursive: true }); } catch (_) {}

  const env = Object.assign({}, process.env, {
    AUTOSLICE_DATA_DIR: dataDir,
    UPLOAD_DIR:         uploadDir,
    DB_PATH:            dbPath,
    JWT_SECRET_KEY:     localJwtSecret(userDataDir),
  });

  // ── Backend ──────────────────────────────────────────────────────────────
  backendProc = spawn(BACKEND_EXE, [], {
    cwd:   path.join(RESOURCES, "backend"),
    env,
    stdio: ["ignore", openLog("backend.log"), openLog("backend-err.log")],
    windowsHide: true,
  });

  backendProc.on("error", (err) => {
    console.error("Backend failed to start:", err.message);
  });

  // ── Frontend ─────────────────────────────────────────────────────────────
  const feEnv = Object.assign({}, process.env, {
    PORT:     "3000",
    HOSTNAME: "127.0.0.1",
    // Tell Next.js where to proxy /api calls
    BACKEND_URL: "http://localhost:8000",
  });

  frontendProc = spawn(NODE_EXE, [SERVER_JS], {
    cwd:   FRONTEND_DIR,
    env:   feEnv,
    stdio: ["ignore", openLog("frontend.log"), openLog("frontend-err.log")],
    windowsHide: true,
  });

  frontendProc.on("error", (err) => {
    console.error("Frontend failed to start:", err.message);
  });
}

function stopServers() {
  for (const proc of [backendProc, frontendProc]) {
    if (proc && !proc.killed) {
      try { proc.kill("SIGTERM"); } catch (_) {}
    }
  }
}

// ── Health polling ─────────────────────────────────────────────────────────

function pollHealth(url, timeoutMs = 60_000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;

    function attempt() {
      if (Date.now() > deadline) {
        return reject(new Error(`Backend did not start within ${timeoutMs / 1000}s`));
      }
      http.get(url, (res) => {
        if (res.statusCode === 200) return resolve();
        setTimeout(attempt, 1000);
      }).on("error", () => setTimeout(attempt, 1000));
    }

    attempt();
  });
}

// ── Splash / loading window ────────────────────────────────────────────────

function createSplash() {
  const splash = new BrowserWindow({
    width:           500,
    height:          340,
    frame:           false,
    transparent:     true,
    resizable:       false,
    alwaysOnTop:     true,
    skipTaskbar:     true,
    webPreferences:  { nodeIntegration: false },
  });

  splash.loadURL(`data:text/html,
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><style>
      *{margin:0;padding:0;box-sizing:border-box}
      html,body{width:500px;height:340px;overflow:hidden}
      body{background:#111;display:flex;align-items:center;justify-content:center;
           font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
           border-radius:12px}
      .spinner{width:52px;height:52px;border:3px solid #222;
               border-top-color:#e02424;border-radius:50%;
               animation:spin .8s linear infinite;margin:0 auto 22px}
      @keyframes spin{to{transform:rotate(360deg)}}
      h1{color:#fff;font-size:24px;font-weight:700;margin-bottom:8px;text-align:center}
      p{color:#555;font-size:13px;text-align:center}
    </style></head>
    <body>
      <div>
        <div class="spinner"></div>
        <h1>AutoSlice</h1>
        <p>Starting local services…</p>
      </div>
    </body></html>`);

  return splash;
}

// ── Main window ────────────────────────────────────────────────────────────

function createMainWindow() {
  const win = new BrowserWindow({
    width:           1280,
    height:          820,
    minWidth:        900,
    minHeight:       600,
    show:            false,
    title:           "AutoSlice",
    frame:           false,          // remove native title bar
    titleBarStyle:   "hidden",
    webPreferences: {
      preload:             path.join(__dirname, "preload.js"),
      contextIsolation:    true,
      nodeIntegration:     false,
      webSecurity:         true,
    },
  });

  // Open external links in the default browser, not in Electron
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://localhost")) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  return win;
}

// ── Auto-updater ──────────────────────────────────────────────────────────

// Cache last update event so the renderer can request it after mounting
let _lastUpdateInfo = null;

function setupAutoUpdater(mainWin) {
  // Only run in packaged app; skip in dev (`npm start`)
  if (!app.isPackaged) return;

  autoUpdater.autoDownload    = true;   // download silently in background
  autoUpdater.autoInstallOnAppQuit = true; // install when user quits normally

  function sendUpdate(payload) {
    _lastUpdateInfo = payload;
    mainWin.webContents.send("update-status", payload);
  }

  autoUpdater.on("checking-for-update", () => {
    console.log("Checking for updates…");
  });

  autoUpdater.on("update-available", (info) => {
    console.log(`Update available: ${info.version}`);
    sendUpdate({
      status:      "available",
      version:     info.version,
      releaseName: info.releaseName || `v${info.version}`,
    });
  });

  autoUpdater.on("update-not-available", () => {
    console.log("App is up to date.");
  });

  autoUpdater.on("download-progress", (p) => {
    console.log(`Downloading update: ${Math.round(p.percent)}%`);
  });

  autoUpdater.on("update-downloaded", (info) => {
    console.log(`Update downloaded: ${info.version}`);
    sendUpdate({
      status:      "downloaded",
      version:     info.version,
      releaseName: info.releaseName || `v${info.version}`,
    });
  });

  autoUpdater.on("error", (err) => {
    // Log silently — don't bother the user with network errors
    console.error("Auto-updater error:", err.message);
  });

  // Check 8 seconds after startup so the app feels responsive first
  setTimeout(() => {
    autoUpdater.checkForUpdates().catch((err) => {
      console.error("Update check failed:", err.message);
    });
  }, 8000);

  // Re-check every 2 hours while the app is running
  setInterval(() => {
    autoUpdater.checkForUpdates().catch(() => {});
  }, 2 * 60 * 60 * 1000);

  // Re-send cached status when window regains focus (catches users who missed the initial event)
  mainWin.on("focus", () => {
    if (_lastUpdateInfo) {
      mainWin.webContents.send("update-status", _lastUpdateInfo);
    }
  });
}

// ── App lifecycle ──────────────────────────────────────────────────────────

// ── IPC handlers (used by preload bridge) ─────────────────────────────────

ipcMain.handle("get-version",     () => app.getVersion());
ipcMain.handle("install-update",   () => autoUpdater.quitAndInstall(false, true));
ipcMain.handle("get-update-status", () => _lastUpdateInfo);

ipcMain.handle("open-external", (_event, url) => shell.openExternal(url));

// Window controls for custom title bar
ipcMain.handle("window-minimize",     (e) => BrowserWindow.fromWebContents(e.sender)?.minimize());
ipcMain.handle("window-maximize",     (e) => {
  const w = BrowserWindow.fromWebContents(e.sender);
  w?.isMaximized() ? w.unmaximize() : w.maximize();
});
ipcMain.handle("window-close",        (e) => BrowserWindow.fromWebContents(e.sender)?.close());
ipcMain.handle("window-is-maximized", (e) => BrowserWindow.fromWebContents(e.sender)?.isMaximized() ?? false);

ipcMain.handle("save-file", async (_event, filename, buffer) => {
  const { canceled, filePath } = await dialog.showSaveDialog({
    defaultPath: filename,
    filters: [
      { name: "3MF Files", extensions: ["3mf"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });
  if (canceled || !filePath) return { saved: false };
  fs.writeFileSync(filePath, Buffer.from(buffer));
  return { saved: true, filePath };
});

// ── App lifecycle ──────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startServers();

  const splash  = createSplash();
  const mainWin = createMainWindow();

  try {
    await pollHealth(HEALTH_URL, 90_000);
  } catch (err) {
    splash.close();
    const logPath = path.join(LOG_DIR, "backend.log");
    dialog.showErrorBox(
      "AutoSlice — startup failed",
      `The local backend did not start.\n\n${err.message}\n\nCheck logs at:\n${logPath}`,
    );
    app.quit();
    return;
  }

  // Both backend (health OK) and frontend need a moment to warm up
  await new Promise((r) => setTimeout(r, 1200));

  mainWin.loadURL(FRONTEND_URL);

  mainWin.once("ready-to-show", () => {
    splash.close();
    mainWin.show();
    setupAutoUpdater(mainWin);
  });

  mainWin.on("closed", () => {
    stopServers();
  });
});

app.on("window-all-closed", () => {
  stopServers();
  app.quit();
});

app.on("before-quit", () => {
  stopServers();
});
