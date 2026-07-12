const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  CredentialEncryptionUnavailableError,
  CredentialStoreCorruptError,
  createCredentialStore,
} = require('./credentialStore');

function createFakeSafeStorage({ available = true } = {}) {
  return {
    isEncryptionAvailable() {
      return available;
    },
    encryptString(value) {
      return Buffer.from(`encrypted:${value}`, 'utf8');
    },
    decryptString(buffer) {
      const text = Buffer.from(buffer).toString('utf8');
      if (!text.startsWith('encrypted:')) {
        throw new Error('bad ciphertext');
      }
      return text.slice('encrypted:'.length);
    },
  };
}

function createStore(options = {}) {
  const userDataPath = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-credentials-'));
  return createCredentialStore({
    safeStorage: createFakeSafeStorage(options),
    userDataPath,
    fsImpl: fs,
  });
}

test('encrypted credential store round trips without plaintext on disk', async () => {
  const store = createStore();

  await store.save({
    IFLYTEK_APP_ID: 'test-app',
    IFLYTEK_API_KEY: 'test-key',
    IFLYTEK_API_SECRET: 'test-secret',
    IFLYTEK_SPARK_API_PASSWORD: 'spark-secret',
  });

  assert.deepEqual(await store.load(), {
    IFLYTEK_APP_ID: 'test-app',
    IFLYTEK_API_KEY: 'test-key',
    IFLYTEK_API_SECRET: 'test-secret',
    IFLYTEK_SPARK_API_PASSWORD: 'spark-secret',
  });
  const onDisk = fs.readFileSync(store.filePath, 'utf8');
  assert.doesNotMatch(onDisk, /test-secret|spark-secret/);
  assert.match(onDisk, /"schemaVersion":1/);
  assert.match(onDisk, /"ciphertext":/);
});

test('save overwrites atomically and clear removes the encrypted file', async () => {
  const store = createStore();

  await store.save({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'old-secret',
  });
  await store.save({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'new-secret',
  });

  assert.equal((await store.load()).IFLYTEK_API_SECRET, 'new-secret');
  assert.doesNotMatch(fs.readFileSync(store.filePath, 'utf8'), /old-secret|new-secret/);
  await store.clear();
  assert.equal(fs.existsSync(store.filePath), false);
  assert.deepEqual(await store.load(), {});
});

test('corrupt ciphertext and unsupported schema fail closed', async () => {
  const store = createStore();
  fs.mkdirSync(path.dirname(store.filePath), { recursive: true });

  fs.writeFileSync(store.filePath, JSON.stringify({ schemaVersion: 1, ciphertext: 'not-base64??' }));
  await assert.rejects(() => store.load(), CredentialStoreCorruptError);

  fs.writeFileSync(store.filePath, JSON.stringify({ schemaVersion: 99, ciphertext: 'ZW5jcnlwdGVkOnt9' }));
  await assert.rejects(() => store.load(), CredentialStoreCorruptError);
});

test('store never falls back to plaintext when safeStorage is unavailable', async () => {
  const store = createStore({ available: false });

  await assert.rejects(
    () => store.save({ IFLYTEK_SPARK_API_PASSWORD: 'spark-secret' }),
    CredentialEncryptionUnavailableError,
  );
  assert.equal(fs.existsSync(store.filePath), false);
});
