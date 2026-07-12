'use strict';

const path = require('node:path');

const STORE_SCHEMA_VERSION = 1;

class CredentialEncryptionUnavailableError extends Error {
  constructor() {
    super('Credential encryption is unavailable on this device.');
    this.name = 'CredentialEncryptionUnavailableError';
  }
}

class CredentialStoreCorruptError extends Error {
  constructor(message = 'Credential store is corrupt or unsupported.') {
    super(message);
    this.name = 'CredentialStoreCorruptError';
  }
}

function ensureEncryptionAvailable(safeStorage) {
  if (!safeStorage || typeof safeStorage.isEncryptionAvailable !== 'function'
    || !safeStorage.isEncryptionAvailable()) {
    throw new CredentialEncryptionUnavailableError();
  }
}

function fileExists(fsImpl, filePath) {
  try {
    return fsImpl.existsSync(filePath);
  } catch (_error) {
    return false;
  }
}

function parseEnvelope(raw) {
  try {
    const envelope = JSON.parse(raw);
    if (!envelope || envelope.schemaVersion !== STORE_SCHEMA_VERSION
      || typeof envelope.ciphertext !== 'string' || !envelope.ciphertext) {
      throw new Error('unsupported envelope');
    }
    return envelope;
  } catch (error) {
    throw corruptStoreError(error);
  }
}

function corruptStoreError(cause) {
  const error = new CredentialStoreCorruptError();
  error.cause = cause;
  return error;
}

function decryptEnvelope(safeStorage, envelope) {
  try {
    const encrypted = Buffer.from(envelope.ciphertext, 'base64');
    const plaintext = safeStorage.decryptString(encrypted);
    const payload = JSON.parse(plaintext);
    if (!payload || payload.schemaVersion !== STORE_SCHEMA_VERSION
      || typeof payload.credentials !== 'object' || payload.credentials === null) {
      throw new Error('unsupported payload');
    }
    return { ...payload.credentials };
  } catch (error) {
    throw corruptStoreError(error);
  }
}

function createCredentialStore({ safeStorage, userDataPath, fsImpl }) {
  if (!userDataPath) {
    throw new Error('userDataPath is required');
  }
  if (!fsImpl) {
    throw new Error('fsImpl is required');
  }

  const directory = path.join(userDataPath, 'credentials');
  const filePath = path.join(directory, 'iflytek-credentials.enc.json');

  return Object.freeze({
    filePath,

    async load() {
      if (!fileExists(fsImpl, filePath)) {
        return {};
      }
      ensureEncryptionAvailable(safeStorage);
      const envelope = parseEnvelope(fsImpl.readFileSync(filePath, 'utf8'));
      return decryptEnvelope(safeStorage, envelope);
    },

    async save(credentials) {
      ensureEncryptionAvailable(safeStorage);
      fsImpl.mkdirSync(directory, { recursive: true, mode: 0o700 });
      const payload = JSON.stringify({
        schemaVersion: STORE_SCHEMA_VERSION,
        credentials: { ...(credentials || {}) },
      });
      const ciphertext = safeStorage.encryptString(payload).toString('base64');
      const envelope = JSON.stringify({ schemaVersion: STORE_SCHEMA_VERSION, ciphertext });
      const tempPath = path.join(
        directory,
        `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`,
      );
      try {
        fsImpl.writeFileSync(tempPath, envelope, { encoding: 'utf8', mode: 0o600 });
        fsImpl.renameSync(tempPath, filePath);
      } finally {
        if (fileExists(fsImpl, tempPath)) {
          fsImpl.rmSync(tempPath, { force: true });
        }
      }
    },

    async clear() {
      if (fileExists(fsImpl, filePath)) {
        fsImpl.rmSync(filePath, { force: true });
      }
    },
  });
}

module.exports = {
  CredentialEncryptionUnavailableError,
  CredentialStoreCorruptError,
  createCredentialStore,
};
