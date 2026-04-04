const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("duckdome", {
  platform: process.platform,
  pickDirectory: async (title, defaultPath) => {
    try {
      return await ipcRenderer.invoke("desktop:pick-directory", { title, defaultPath });
    } catch {
      return { canceled: true };
    }
  },
  notify: (title, body) => {
    ipcRenderer.invoke("desktop:notify", { title, body });
  },
});
