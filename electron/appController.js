'use strict';

const fs = require('node:fs');
const path = require('node:path');

const backendDefaults = require('./backendLauncher');
const { resolveCredentialEnvironment } = require('./credentialConfig');
const { getSensitiveValues } = require('./credentialConfig');
const { createStreamingRedactor } = require('./logRedactor');
const { createSettingsController, registerSettingsIpc } = require('./settingsController');

function createAppController({
  app,
  BrowserWindow,
  dialog,
  spawn,
  backend = backendDefaults,
  credentialStore,
  preferencesStore,
  processEnv = process.env,
  resourcesPath = process.resourcesPath,
  ipcMain,
}) {
  if (!app || !BrowserWindow || !dialog || !spawn || !credentialStore || !preferencesStore) {
    throw new Error('app controller dependencies are required');
  }

  let backendProcess = null;
  let mainWindow = null;
  let settingsWindow = null;
  let startupWarnings = [];
  let startingBackend = null;

  const settings = createSettingsController({
    credentialStore,
    preferencesStore,
    environment: processEnv,
    onCredentialsChanged: async () => {
      await startBackendIfNeeded();
      closeSettingsWindow();
    },
  });
  registerSettingsIpc({ ipcMain, settingsController: settings });

  function getWindowIconPath() {
    if (app.isPackaged) {
      return undefined;
    }
    const candidate = path.join(app.getAppPath(), 'build', 'app-icon.ico');
    return fs.existsSync(candidate) ? candidate : undefined;
  }

  function pipeBackendLogs(child, sensitiveValues) {
    const userData = app.getPath('userData');
    fs.mkdirSync(userData, { recursive: true });
    const stdout = fs.createWriteStream(path.join(userData, 'backend.out.log'), { flags: 'a' });
    const stderr = fs.createWriteStream(path.join(userData, 'backend.err.log'), { flags: 'a' });
    const stdoutRedactor = createStreamingRedactor(sensitiveValues);
    const stderrRedactor = createStreamingRedactor(sensitiveValues);
    child.stdout.on('data', (chunk) => stdout.write(stdoutRedactor.write(chunk)));
    child.stderr.on('data', (chunk) => stderr.write(stderrRedactor.write(chunk)));
    child.on('close', () => {
      stdout.write(stdoutRedactor.flush());
      stderr.write(stderrRedactor.flush());
      stdout.end();
      stderr.end();
    });
  }

  async function buildBackendEnvironment() {
    const stored = await credentialStore.load();
    const resolved = resolveCredentialEnvironment(processEnv, stored);
    return {
      env: { ...processEnv, ...resolved },
      sensitiveValues: getSensitiveValues(resolved),
    };
  }

  async function startBackendIfNeeded() {
    if (backendProcess) {
      return backendProcess;
    }
    if (startingBackend) {
      return startingBackend;
    }
    startingBackend = (async () => {
      const appRoot = backend.getAppRoot({
        isPackaged: app.isPackaged,
        appPath: app.getAppPath(),
        resourcesPath,
      });
      const port = await backend.findFreePort(Number(processEnv.PORT || 5000), 30);
      const launchToken = backend.createLaunchToken();
      const { env, sensitiveValues } = await buildBackendEnvironment();
      const launchConfig = backend.buildBackendLaunchConfig({
        appRoot,
        port,
        env,
        launchToken,
      });
      const resourceReport = backend.inspectBundledResources({ appRoot, launchConfig });
      if (resourceReport.errors.length > 0) {
        throw new Error(resourceReport.errors.join('\n'));
      }
      startupWarnings = [...resourceReport.warnings];
      backendProcess = spawn(launchConfig.pythonExe, launchConfig.args, launchConfig.options);
      pipeBackendLogs(backendProcess, sensitiveValues);
      backendProcess.once('exit', (code, signal) => {
        backendProcess = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-exit', { code, signal });
        }
      });
      await backend.waitForHealth({ port, timeoutMs: 45000, launchToken });
      const healthData = await backend.fetchHealthData({ port, timeoutMs: 5000, launchToken });
      startupWarnings = backend.summarizeStartupWarnings({ resourceReport, healthData });
      createMainWindow(port);
      return backendProcess;
    })();
    try {
      return await startingBackend;
    } finally {
      startingBackend = null;
    }
  }

  function createMainWindow(port) {
    if (mainWindow && !mainWindow.isDestroyed()) {
      return mainWindow;
    }
    mainWindow = new BrowserWindow({
      width: 1180,
      height: 820,
      minWidth: 960,
      minHeight: 680,
      title: 'Xunfei Job Assistant',
      backgroundColor: '#080E1A',
      icon: getWindowIconPath(),
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    mainWindow.loadURL(`http://127.0.0.1:${port}/`);
    return mainWindow;
  }

  function createSettingsWindow() {
    if (settingsWindow && !settingsWindow.isDestroyed()) {
      return settingsWindow;
    }
    settingsWindow = new BrowserWindow({
      width: 720,
      height: 680,
      minWidth: 640,
      minHeight: 560,
      title: 'Credential Settings',
      backgroundColor: '#0B1020',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        preload: path.join(__dirname, 'settings-preload.js'),
      },
    });
    settingsWindow.loadFile(path.join(__dirname, 'settings', 'index.html'));
    return settingsWindow;
  }

  function closeSettingsWindow() {
    if (settingsWindow && !settingsWindow.isDestroyed() && typeof settingsWindow.close === 'function') {
      settingsWindow.close();
    }
    settingsWindow = null;
  }

  async function start() {
    const preferences = await preferencesStore.load();
    if (preferences.onboardingComplete !== true) {
      createSettingsWindow();
      return { mode: 'settings' };
    }
    await startBackendIfNeeded();
    return { mode: 'app' };
  }

  function stopBackend() {
    if (!backendProcess || backendProcess.killed) {
      return;
    }
    backendProcess.kill();
    backendProcess = null;
  }

  return Object.freeze({
    settings,
    start,
    stopBackend,
    getStartupWarnings: () => [...startupWarnings],
  });
}

module.exports = {
  createAppController,
};
