const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("duckdome", {
  platform: process.platform,
});
