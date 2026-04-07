"use strict";

/**
 * AutoSlice — Electron preload script
 *
 * Exposes a minimal, safe API to the renderer via contextBridge.
 * All file I/O stays in the main process; the renderer calls these
 * methods through the bridge without ever getting direct Node.js access.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("autoslice", {
  /**
   * Save a Blob/ArrayBuffer returned by the convert API as a local file.
   * Triggers the native Save dialog.
   */
  saveFile: (filename, buffer) =>
    ipcRenderer.invoke("save-file", filename, buffer),

  /**
   * Return the app version string.
   */
  getVersion: () => ipcRenderer.invoke("get-version"),

  /**
   * Open a URL in the default system browser.
   */
  openExternal: (url) => ipcRenderer.invoke("open-external", url),

  // Custom title bar window controls
  windowMinimize:    () => ipcRenderer.invoke("window-minimize"),
  windowMaximize:    () => ipcRenderer.invoke("window-maximize"),
  windowClose:       () => ipcRenderer.invoke("window-close"),
  windowIsMaximized: () => ipcRenderer.invoke("window-is-maximized"),

  // Auto-update
  onUpdateStatus: (cb) => {
    ipcRenderer.on("update-status", (_event, data) => cb(data));
  },
  getUpdateStatus: () => ipcRenderer.invoke("get-update-status"),
  installUpdate: () => ipcRenderer.invoke("install-update"),
});
