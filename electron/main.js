const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const {
  buildBackendLaunchConfig,
  fetchHealthData,
  findFreePort,
  getAppRoot,
  inspectBundledResources,
  summarizeStartupWarnings,
  waitForHealth,
} = require('./backendLauncher');

let backendProcess = null;
let mainWindow = null;
let startupWarnings = [];

function getWindowIconPath() {
  if (app.isPackaged) {
    return undefined;
  }
  const candidate = path.join(app.getAppPath(), 'build', 'app-icon.ico');
  return fs.existsSync(candidate) ? candidate : undefined;
}

function getStartupCheckStatePath() {
  return path.join(app.getPath('userData'), 'startup-check.json');
}

function readJsonFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return null;
  }
}

function writeJsonFile(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2), 'utf8');
}

function readLogTail(fileName, maxChars = 2000) {
  const filePath = path.join(app.getPath('userData'), fileName);
  if (!fs.existsSync(filePath)) {
    return '';
  }
  const content = fs.readFileSync(filePath, 'utf8').trim();
  if (content.length <= maxChars) {
    return content;
  }
  return content.slice(-maxChars);
}

function formatStartupError(error) {
  const errLog = readLogTail('backend.err.log');
  if (!errLog) {
    return error.message;
  }
  return `${error.message}\n\n后端错误日志：\n${errLog}`;
}

function pipeBackendLogs(child) {
  const logDir = app.getPath('userData');
  fs.mkdirSync(logDir, { recursive: true });
  const stdout = fs.createWriteStream(path.join(logDir, 'backend.out.log'), { flags: 'a' });
  const stderr = fs.createWriteStream(path.join(logDir, 'backend.err.log'), { flags: 'a' });

  child.stdout.on('data', (chunk) => stdout.write(chunk));
  child.stderr.on('data', (chunk) => stderr.write(chunk));
  child.on('close', () => {
    stdout.end();
    stderr.end();
  });
}

async function startBackend() {
  const appRoot = getAppRoot({
    isPackaged: app.isPackaged,
    appPath: app.getAppPath(),
    resourcesPath: process.resourcesPath,
  });
  const port = await findFreePort(Number(process.env.PORT || 5000), 30);
  const launchConfig = buildBackendLaunchConfig({
    appRoot,
    port,
    env: process.env,
  });
  const resourceReport = inspectBundledResources({ appRoot, launchConfig });

  if (resourceReport.errors.length > 0) {
    throw new Error(resourceReport.errors.join('\n'));
  }
  startupWarnings = [...resourceReport.warnings];

  backendProcess = spawn(
    launchConfig.pythonExe,
    launchConfig.args,
    launchConfig.options,
  );
  pipeBackendLogs(backendProcess);

  backendProcess.once('exit', (code, signal) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-exit', { code, signal });
    }
  });

  await waitForHealth({ port, timeoutMs: 45000 });
  const healthData = await fetchHealthData({ port, timeoutMs: 5000 });
  startupWarnings = summarizeStartupWarnings({
    resourceReport,
    healthData,
  });
  return { port };
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    title: '讯飞求职助手',
    backgroundColor: '#080E1A',
    icon: getWindowIconPath(),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${port}/`);
}

async function maybeShowStartupWarnings() {
  if (startupWarnings.length === 0) {
    return;
  }

  const statePath = getStartupCheckStatePath();
  const currentState = {
    version: app.getVersion(),
    warnings: startupWarnings,
  };
  const previousState = readJsonFile(statePath);

  if (
    previousState
    && previousState.version === currentState.version
    && JSON.stringify(previousState.warnings) === JSON.stringify(currentState.warnings)
  ) {
    return;
  }

  writeJsonFile(statePath, currentState);
  await dialog.showMessageBox({
    type: 'warning',
    title: '首次启动自检',
    message: '程序已启动，但检测到以下可选能力或资源需要留意：',
    detail: startupWarnings.map((warning, index) => `${index + 1}. ${warning}`).join('\n'),
  });
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    return;
  }
  backendProcess.kill();
  backendProcess = null;
}

app.whenReady().then(async () => {
  try {
    const { port } = await startBackend();
    createWindow(port);
    await maybeShowStartupWarnings();
  } catch (error) {
    dialog.showErrorBox('启动失败', formatStartupError(error));
    app.quit();
  }
});

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', () => {
  stopBackend();
});
