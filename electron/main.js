const { app, BrowserWindow, dialog, ipcMain, safeStorage } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');

const backend = require('./backendLauncher');
const { createAppController } = require('./appController');
const { createCredentialStore } = require('./credentialStore');
const { createPreferencesStore } = require('./preferencesStore');

let controller = null;

function createController() {
  const userDataPath = app.getPath('userData');
  const credentialStore = createCredentialStore({ safeStorage, userDataPath, fsImpl: fs });
  const preferencesStore = createPreferencesStore({ userDataPath, fsImpl: fs });
  return createAppController({
    app,
    BrowserWindow,
    dialog,
    spawn,
    backend,
    credentialStore,
    preferencesStore,
    processEnv: process.env,
    resourcesPath: process.resourcesPath,
    ipcMain,
  });
}

app.whenReady().then(async () => {
  try {
    controller = createController();
    await controller.start();
  } catch (error) {
    dialog.showErrorBox('启动失败', error.message);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (controller) {
    controller.stopBackend();
  }
  app.quit();
});

app.on('before-quit', () => {
  if (controller) {
    controller.stopBackend();
  }
});
