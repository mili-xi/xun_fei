'use strict';

const {
  resolveCredentialEnvironment,
  summarizeCredentialStatus,
  validateCredentialPatch,
} = require('./credentialConfig');

function createSettingsController({
  credentialStore,
  preferencesStore,
  environment = process.env,
  onCredentialsChanged = async () => {},
}) {
  if (!credentialStore || !preferencesStore) {
    throw new Error('credentialStore and preferencesStore are required');
  }

  async function getStatus() {
    const [stored, preferences] = await Promise.all([
      credentialStore.load(),
      preferencesStore.load(),
    ]);
    const resolved = resolveCredentialEnvironment(environment, stored);
    return Object.freeze({
      onboardingComplete: preferences.onboardingComplete === true,
      credentials: summarizeCredentialStatus(resolved),
    });
  }

  return Object.freeze({
    getStatus,

    async save(patch) {
      const validated = validateCredentialPatch(patch);
      await credentialStore.save(validated);
      await preferencesStore.save({ onboardingComplete: true });
      await onCredentialsChanged();
      return getStatus();
    },

    async clear() {
      await credentialStore.clear();
      await preferencesStore.save({ onboardingComplete: false });
      return getStatus();
    },

    async continueLocal() {
      await preferencesStore.save({ onboardingComplete: true });
      await onCredentialsChanged();
      return getStatus();
    },
  });
}

function registerSettingsIpc({ ipcMain, settingsController }) {
  if (!ipcMain || !settingsController) {
    return;
  }
  ipcMain.handle('settings:getStatus', () => settingsController.getStatus());
  ipcMain.handle('settings:save', (_event, patch) => settingsController.save(patch));
  ipcMain.handle('settings:clear', () => settingsController.clear());
  ipcMain.handle('settings:continueLocal', () => settingsController.continueLocal());
}

module.exports = {
  createSettingsController,
  registerSettingsIpc,
};
