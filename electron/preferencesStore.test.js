const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { createPreferencesStore } = require('./preferencesStore');

function createStore() {
  const userDataPath = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-preferences-'));
  return createPreferencesStore({ userDataPath, fsImpl: fs });
}

test('preferences default to incomplete without creating a file', async () => {
  const store = createStore();

  assert.deepEqual(await store.load(), { onboardingComplete: false });
  assert.equal(fs.existsSync(store.filePath), false);
});

test('preferences round trip only the onboarding boolean', async () => {
  const store = createStore();

  await store.save({ onboardingComplete: true });

  assert.deepEqual(await store.load(), { onboardingComplete: true });
  assert.match(fs.readFileSync(store.filePath, 'utf8'), /"onboardingComplete":true/);
});

test('preferences reject credential-shaped and unknown keys', async () => {
  const store = createStore();

  await assert.rejects(
    () => store.save({ onboardingComplete: true, IFLYTEK_API_KEY: 'secret' }),
    /Unsupported preference field/,
  );
  await assert.rejects(
    () => store.save({ onboardingComplete: true, theme: 'dark' }),
    /Unsupported preference field/,
  );
});

test('preferences reject non-boolean onboarding state', async () => {
  const store = createStore();

  await assert.rejects(
    () => store.save({ onboardingComplete: 'yes' }),
    /onboardingComplete must be a boolean/,
  );
});
