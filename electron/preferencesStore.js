'use strict';

const path = require('node:path');

const PREFERENCE_FIELDS = Object.freeze(['onboardingComplete']);
const SCHEMA_VERSION = 1;

function validatePreferences(preferences = {}) {
  for (const key of Object.keys(preferences)) {
    if (!PREFERENCE_FIELDS.includes(key)) {
      throw new Error(`Unsupported preference field: ${key}`);
    }
  }
  if (Object.prototype.hasOwnProperty.call(preferences, 'onboardingComplete')
    && typeof preferences.onboardingComplete !== 'boolean') {
    throw new Error('onboardingComplete must be a boolean');
  }
  return Object.freeze({
    onboardingComplete: preferences.onboardingComplete === true,
  });
}

function fileExists(fsImpl, filePath) {
  try {
    return fsImpl.existsSync(filePath);
  } catch (_error) {
    return false;
  }
}

function createPreferencesStore({ userDataPath, fsImpl }) {
  if (!userDataPath) {
    throw new Error('userDataPath is required');
  }
  if (!fsImpl) {
    throw new Error('fsImpl is required');
  }

  const directory = path.join(userDataPath, 'preferences');
  const filePath = path.join(directory, 'preferences.json');

  return Object.freeze({
    filePath,

    async load() {
      if (!fileExists(fsImpl, filePath)) {
        return { onboardingComplete: false };
      }
      const parsed = JSON.parse(fsImpl.readFileSync(filePath, 'utf8'));
      if (!parsed || parsed.schemaVersion !== SCHEMA_VERSION || typeof parsed.preferences !== 'object') {
        throw new Error('Unsupported preferences file');
      }
      return validatePreferences(parsed.preferences);
    },

    async save(preferences) {
      const normalized = validatePreferences(preferences);
      fsImpl.mkdirSync(directory, { recursive: true });
      const body = JSON.stringify({
        schemaVersion: SCHEMA_VERSION,
        preferences: normalized,
      });
      const tempPath = path.join(
        directory,
        `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`,
      );
      try {
        fsImpl.writeFileSync(tempPath, body, { encoding: 'utf8', mode: 0o600 });
        fsImpl.renameSync(tempPath, filePath);
      } finally {
        if (fileExists(fsImpl, tempPath)) {
          fsImpl.rmSync(tempPath, { force: true });
        }
      }
    },
  });
}

module.exports = {
  createPreferencesStore,
  validatePreferences,
};
