const assert = require('node:assert/strict');
const test = require('node:test');

const { createSettingsController } = require('./settingsController');

function createMemoryStores() {
  let credentials = {};
  let preferences = { onboardingComplete: false };
  return {
    credentialStore: {
      async load() {
        return { ...credentials };
      },
      async save(next) {
        credentials = { ...next };
      },
      async clear() {
        credentials = {};
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

test('settings status summarizes credentials without returning values', async () => {
  const stores = createMemoryStores();
  await stores.credentialStore.save({
    IFLYTEK_APP_ID: 'stored-app',
    IFLYTEK_API_KEY: 'stored-key',
    IFLYTEK_API_SECRET: 'stored-secret',
    IFLYTEK_SPARK_API_PASSWORD: 'stored-spark',
  });
  const controller = createSettingsController({
    ...stores,
    environment: { IFLYTEK_APP_ID: 'env-app' },
  });

  const status = await controller.getStatus();
  const serialized = JSON.stringify(status);

  assert.equal(status.onboardingComplete, false);
  assert.equal(status.credentials.ocr.configured, true);
  assert.equal(status.credentials.ocr.sources.IFLYTEK_APP_ID, 'environment');
  assert.equal(status.credentials.spark.configured, true);
  assert.doesNotMatch(serialized, /stored-key|stored-secret|stored-spark|env-app/);
});

test('settings save validates credentials, marks onboarding complete, and requests restart', async () => {
  const stores = createMemoryStores();
  let restartCount = 0;
  const controller = createSettingsController({
    ...stores,
    environment: {},
    onCredentialsChanged: async () => {
      restartCount += 1;
    },
  });

  await controller.save({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'secret',
  });

  assert.equal(restartCount, 1);
  assert.equal((await stores.preferencesStore.load()).onboardingComplete, true);
  assert.equal((await stores.credentialStore.load()).IFLYTEK_API_SECRET, 'secret');
  await assert.rejects(() => controller.save({ IFLYTEK_APP_ID: 'partial' }), /OCR credentials/);
});

test('settings clear removes stored credentials and resets onboarding', async () => {
  const stores = createMemoryStores();
  await stores.credentialStore.save({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'secret',
  });
  await stores.preferencesStore.save({ onboardingComplete: true });
  const controller = createSettingsController({ ...stores, environment: {} });

  await controller.clear();

  assert.deepEqual(await stores.credentialStore.load(), {});
  assert.equal((await stores.preferencesStore.load()).onboardingComplete, false);
});

test('continueLocal marks onboarding complete without writing credentials', async () => {
  const stores = createMemoryStores();
  const controller = createSettingsController({ ...stores, environment: {} });

  await controller.continueLocal();

  assert.deepEqual(await stores.credentialStore.load(), {});
  assert.equal((await stores.preferencesStore.load()).onboardingComplete, true);
});
