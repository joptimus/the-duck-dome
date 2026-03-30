const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");

const DEV_URL = "http://localhost:5173";

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 768,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
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

const { startBackend, stopBackend } = require("./backend");

app.whenReady().then(() => {
  if (app.isPackaged) {
    startBackend();
  }
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("before-quit", () => {
  stopBackend();
});
