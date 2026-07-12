const assert = require('node:assert/strict');
const test = require('node:test');

const { createAppController } = require('./appController');

function createMemoryStores({ onboardingComplete = false, credentials = {} } = {}) {
  let storedCredentials = { ...credentials };
  let preferences = { onboardingComplete };
  return {
    credentialStore: {
      async load() {
        return { ...storedCredentials };
      },
      async save(next) {
        storedCredentials = { ...next };
      },
      async clear() {
        storedCredentials = {};
      },
    },
    preferencesStore: {
      async load() {
        return { ...preferences };
      },
      async save(next) {
        preferences = { ...next };
      },
    },
  };
}

function createHarness(options = {}) {
  const events = [];
  const stores = createMemoryStores(options);
  const controller = createAppController({
    app: {
      isPackaged: false,
      getAppPath: () => 'C:\\app',
      getPath: () => 'C:\\user-data',
      getVersion: () => '1.1.0',
      quit: () => events.push(['quit']),
    },
    BrowserWindow: function BrowserWindow(config) {
      events.push(['window', config]);
      return {
        loadURL: (url) => events.push(['loadURL', url]),
        loadFile: (file) => events.push(['loadFile', file]),
        isDestroyed: () => false,
        webContents: { send: (...args) => events.push(['send', ...args]) },
      };
    },
    dialog: {
      showErrorBox: (...args) => events.push(['error', ...args]),
      showMessageBox: async (...args) => events.push(['message', ...args]),
    },
    spawn: (...args) => {
      events.push(['spawn', args]);
      return {
        stdout: { on() {} },
        stderr: { on() {} },
        once() {},
        on() {},
        kill() { events.push(['kill']); },
        killed: false,
      };
    },
    backend: {
      getAppRoot: () => 'C:\\app',
      findFreePort: async () => 5123,
      createLaunchToken: () => 'launch-token',
      buildBackendLaunchConfig: ({ env, launchToken }) => ({
        pythonExe: 'python.exe',
        args: ['app.py'],
        options: { env: { ...env, XUNFEI_LAUNCH_TOKEN: launchToken }, stdio: ['ignore', 'pipe', 'pipe'] },
      }),
      inspectBundledResources: () => ({ errors: [], warnings: [] }),
      waitForHealth: async ({ launchToken }) => events.push(['waitForHealth', launchToken]),
      fetchHealthData: async ({ launchToken }) => {
        events.push(['fetchHealthData', launchToken]);
        return { data: { status: 'ok' } };
      },
      summarizeStartupWarnings: () => [],
    },
    processEnv: options.environment || {},
    safeStorage: { isEncryptionAvailable: () => true },
    resourcesPath: 'C:\\resources',
    ...stores,
  });
  return { controller, events, stores };
}

test('app controller opens settings before backend when onboarding is incomplete', async () => {
  const { controller, events } = createHarness({ onboardingComplete: false });

  await controller.start();

  assert.ok(events.some(([kind]) => kind === 'loadFile'));
  assert.equal(events.some(([kind]) => kind === 'spawn'), false);
});

test('app controller starts backend with resolved credentials after onboarding', async () => {
  const { controller, events } = createHarness({
    onboardingComplete: true,
    credentials: {
      IFLYTEK_APP_ID: 'stored-app',
      IFLYTEK_API_KEY: 'stored-key',
      IFLYTEK_API_SECRET: 'stored-secret',
    },
    environment: { IFLYTEK_APP_ID: 'env-app' },
  });

  await controller.start();

  const spawnEvent = events.find(([kind]) => kind === 'spawn');
  assert.ok(spawnEvent);
  const env = spawnEvent[1][2].env;
  assert.equal(env.IFLYTEK_APP_ID, 'env-app');
  assert.equal(env.IFLYTEK_API_KEY, 'stored-key');
  assert.equal(env.IFLYTEK_API_SECRET, 'stored-secret');
  assert.equal(env.XUNFEI_LAUNCH_TOKEN, 'launch-token');
  assert.deepEqual(
    events.filter(([kind]) => kind === 'waitForHealth' || kind === 'fetchHealthData').map((entry) => entry[1]),
    ['launch-token', 'launch-token'],
  );
});

test('settings save callback starts backend exactly once', async () => {
  const { controller, events } = createHarness({ onboardingComplete: false });

  await controller.start();
  await controller.settings.save({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'secret',
  });

  assert.equal(events.filter(([kind]) => kind === 'spawn').length, 1);
});
