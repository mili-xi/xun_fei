const assert = require('node:assert/strict');
const test = require('node:test');

const {
  CREDENTIAL_FIELDS,
  getSensitiveValues,
  resolveCredentialEnvironment,
  summarizeCredentialStatus,
  validateCredentialPatch,
} = require('./credentialConfig');

test('credential fields are the only supported secret environment names', () => {
  assert.deepEqual(CREDENTIAL_FIELDS, [
    'IFLYTEK_APP_ID',
    'IFLYTEK_API_KEY',
    'IFLYTEK_API_SECRET',
    'IFLYTEK_SPARK_API_PASSWORD',
  ]);
});

test('environment values override stored values without mutating inputs', () => {
  const env = { IFLYTEK_APP_ID: 'env-app' };
  const stored = {
    IFLYTEK_APP_ID: 'stored-app',
    IFLYTEK_API_KEY: 'stored-key',
    IFLYTEK_API_SECRET: 'stored-secret',
    IFLYTEK_SPARK_API_PASSWORD: 'stored-spark',
  };

  const resolved = resolveCredentialEnvironment(env, stored);

  assert.equal(resolved.IFLYTEK_APP_ID, 'env-app');
  assert.equal(resolved.IFLYTEK_API_KEY, 'stored-key');
  assert.equal(resolved.IFLYTEK_API_SECRET, 'stored-secret');
  assert.equal(resolved.IFLYTEK_SPARK_API_PASSWORD, 'stored-spark');
  assert.deepEqual(env, { IFLYTEK_APP_ID: 'env-app' });
  assert.deepEqual(stored, {
    IFLYTEK_APP_ID: 'stored-app',
    IFLYTEK_API_KEY: 'stored-key',
    IFLYTEK_API_SECRET: 'stored-secret',
    IFLYTEK_SPARK_API_PASSWORD: 'stored-spark',
  });
  resolved.IFLYTEK_API_KEY = 'changed';
  assert.equal(resolved.IFLYTEK_API_KEY, 'stored-key');
});

test('credential patch rejects unknown fields and partial OCR credentials', () => {
  assert.throws(
    () => validateCredentialPatch({ UNKNOWN_SECRET: 'value' }),
    /Unsupported credential field/,
  );
  assert.throws(
    () => validateCredentialPatch({ IFLYTEK_APP_ID: 'app-only' }),
    /IFLYTEK_APP_ID, IFLYTEK_API_KEY, IFLYTEK_API_SECRET/,
  );

  assert.deepEqual(validateCredentialPatch({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'secret',
    IFLYTEK_SPARK_API_PASSWORD: '',
  }), {
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: 'key',
    IFLYTEK_API_SECRET: 'secret',
    IFLYTEK_SPARK_API_PASSWORD: '',
  });
});

test('credential status summarizes sources without exposing values', () => {
  const resolved = resolveCredentialEnvironment(
    { IFLYTEK_APP_ID: 'env-app' },
    {
      IFLYTEK_APP_ID: 'stored-app',
      IFLYTEK_API_KEY: 'stored-key',
      IFLYTEK_API_SECRET: 'stored-secret',
      IFLYTEK_SPARK_API_PASSWORD: 'stored-spark',
    },
  );

  const summary = summarizeCredentialStatus(resolved);
  const serialized = JSON.stringify(summary);

  assert.equal(summary.ocr.configured, true);
  assert.equal(summary.ocr.sources.IFLYTEK_APP_ID, 'environment');
  assert.equal(summary.ocr.sources.IFLYTEK_API_KEY, 'stored');
  assert.equal(summary.spark.configured, true);
  assert.equal(summary.spark.source, 'stored');
  assert.doesNotMatch(serialized, /env-app|stored-key|stored-secret|stored-spark/);
});

test('sensitive value extraction returns non-empty values only', () => {
  assert.deepEqual(getSensitiveValues({
    IFLYTEK_APP_ID: 'app',
    IFLYTEK_API_KEY: '',
    IFLYTEK_API_SECRET: 'secret',
    EXTRA: 'ignored',
  }), ['app', 'secret']);
});
