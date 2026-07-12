const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xunfeiSettings', {
  getStatus: () => ipcRenderer.invoke('settings:getStatus'),
  save: (patch) => ipcRenderer.invoke('settings:save', patch),
  clear: () => ipcRenderer.invoke('settings:clear'),
  continueLocal: () => ipcRenderer.invoke('settings:continueLocal'),
});
