'use strict';

const CREDENTIAL_FIELDS = Object.freeze([
  'IFLYTEK_APP_ID',
  'IFLYTEK_API_KEY',
  'IFLYTEK_API_SECRET',
  'IFLYTEK_SPARK_API_PASSWORD',
]);

const OCR_FIELDS = Object.freeze([
  'IFLYTEK_APP_ID',
  'IFLYTEK_API_KEY',
  'IFLYTEK_API_SECRET',
]);

function cleanValue(value) {
  if (value === undefined || value === null) {
    return '';
  }
  return String(value).trim();
}

function blankCredentialObject() {
  return Object.fromEntries(CREDENTIAL_FIELDS.map((field) => [field, '']));
}

function validateKnownFields(input) {
  for (const key of Object.keys(input || {})) {
    if (!CREDENTIAL_FIELDS.includes(key)) {
      throw new Error(`Unsupported credential field: ${key}`);
    }
  }
}

function normalizeCredentialObject(input = {}) {
  validateKnownFields(input);
  const normalized = blankCredentialObject();
  for (const field of CREDENTIAL_FIELDS) {
    normalized[field] = cleanValue(input[field]);
  }
  return normalized;
}

function assertCompleteOcrTrio(credentials) {
  const present = OCR_FIELDS.filter((field) => credentials[field]);
  if (present.length > 0 && present.length !== OCR_FIELDS.length) {
    throw new Error(`OCR credentials must be provided together: ${OCR_FIELDS.join(', ')}`);
  }
}

function validateCredentialPatch(patch = {}) {
  const normalized = normalizeCredentialObject(patch);
  assertCompleteOcrTrio(normalized);
  return Object.freeze({ ...normalized });
}

function resolveCredentialEnvironment(environment = {}, stored = {}) {
  validateKnownFields(stored);
  const resolved = {};
  const sources = {};
  for (const field of CREDENTIAL_FIELDS) {
    const envValue = cleanValue(environment[field]);
    const storedValue = cleanValue(stored[field]);
    if (envValue) {
      resolved[field] = envValue;
      sources[field] = 'environment';
    } else if (storedValue) {
      resolved[field] = storedValue;
      sources[field] = 'stored';
    } else {
      resolved[field] = '';
      sources[field] = 'missing';
    }
  }
  Object.defineProperty(resolved, '__sources', {
    value: Object.freeze({ ...sources }),
    enumerable: false,
  });
  return Object.freeze(resolved);
}

function summarizeCredentialStatus(resolved = {}) {
  const sources = resolved.__sources || {};
  const ocrSources = Object.fromEntries(
    OCR_FIELDS.map((field) => [field, sources[field] || (cleanValue(resolved[field]) ? 'provided' : 'missing')]),
  );
  return Object.freeze({
    ocr: Object.freeze({
      configured: OCR_FIELDS.every((field) => Boolean(cleanValue(resolved[field]))),
      sources: Object.freeze(ocrSources),
    }),
    spark: Object.freeze({
      configured: Boolean(cleanValue(resolved.IFLYTEK_SPARK_API_PASSWORD)),
      source: sources.IFLYTEK_SPARK_API_PASSWORD
        || (cleanValue(resolved.IFLYTEK_SPARK_API_PASSWORD) ? 'provided' : 'missing'),
    }),
  });
}

function getSensitiveValues(credentials = {}) {
  return CREDENTIAL_FIELDS
    .map((field) => cleanValue(credentials[field]))
    .filter(Boolean);
}

module.exports = {
  CREDENTIAL_FIELDS,
  getSensitiveValues,
  resolveCredentialEnvironment,
  summarizeCredentialStatus,
  validateCredentialPatch,
};
