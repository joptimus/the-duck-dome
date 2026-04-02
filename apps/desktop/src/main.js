const { app, BrowserWindow, ipcMain, dialog, Menu, Notification } = require("electron");
const path = require("path");

const DEV_URL = "http://localhost:5173";

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 768,
    icon: path.join(__dirname, "..", "..", "public", "img", "duckdome_icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setMenuBarVisibility(false);
  win.removeMenu();

  win.webContents.on("before-input-event", (event, input) => {
    const isReloadCombo =
      input.type === "keyDown" &&
      ((input.key?.toLowerCase() === "r" && (input.control || input.meta)) || input.key === "F5");
    const isHardReloadCombo =
      input.type === "keyDown" &&
      input.key?.toLowerCase() === "r" &&
      input.shift &&
      (input.control || input.meta);

    if (isHardReloadCombo) {
      event.preventDefault();
      win.webContents.reloadIgnoringCache();
      return;
    }

    if (isReloadCombo) {
      event.preventDefault();
      win.webContents.reload();
      return;
    }

    const isInspectCombo =
      input.type === "keyDown" &&
      ((input.key?.toLowerCase() === "i" && input.shift && (input.control || input.meta)) ||
        input.key === "F12");

    if (!isInspectCombo) {
      return;
    }

    event.preventDefault();
    if (win.webContents.isDevToolsOpened()) {
      win.webContents.closeDevTools();
      return;
    }
    win.webContents.openDevTools({ mode: "detach" });
  });

  win.loadURL(DEV_URL);
}

ipcMain.handle("desktop:pick-directory", async (_event, opts = {}) => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    title: opts.title || "Select Repository Folder",
    defaultPath: opts.defaultPath,
  });
  return {
    canceled: result.canceled,
    path: result.filePaths?.[0] || undefined,
  };
});

ipcMain.handle("desktop:notify", (_event, opts = {}) => {
  if (!Notification.isSupported()) return;
  const notif = new Notification({
    title: opts.title || "DuckDome",
    body: opts.body || "",
  });
  notif.show();
});

const { startBackend, stopBackend } = require("./backend");
let isQuitting = false;

function requestAppQuit() {
  if (isQuitting) {
    return;
  }
  isQuitting = true;
  stopBackend()
    .catch((err) => {
      console.error(`[backend] stop failed: ${err?.message || err}`);
    })
    .finally(() => {
      app.quit();
    });
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  if (app.isPackaged) {
    startBackend();
  }
  createWindow();
});

app.on("window-all-closed", () => {
  requestAppQuit();
});

app.on("activate", () => {
  if (isQuitting) {
    return;
  }
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("before-quit", (event) => {
  if (isQuitting) {
    return;
  }
  event.preventDefault();
  requestAppQuit();
});
