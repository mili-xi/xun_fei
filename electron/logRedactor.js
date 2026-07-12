'use strict';

const REDACTION = '[REDACTED]';

function normalizeSecrets(values = []) {
  return [...new Set(
    values
      .map((value) => (value === undefined || value === null ? '' : String(value)))
      .filter(Boolean),
  )].sort((left, right) => right.length - left.length);
}

function redactText(text, secrets) {
  let output = text;
  for (const secret of secrets) {
    output = output.split(secret).join(REDACTION);
  }
  return output;
}

function findOverlapBoundary(text, safeLimit, secrets) {
  let adjusted = safeLimit;
  for (const secret of secrets) {
    let index = text.indexOf(secret);
    while (index !== -1) {
      const end = index + secret.length;
      if (index < adjusted && end > adjusted) {
        adjusted = index;
      }
      index = text.indexOf(secret, index + 1);
    }
  }
  return adjusted;
}

function createStreamingRedactor(values = []) {
  const secrets = normalizeSecrets(values);
  const maxSecretLength = secrets.reduce((max, secret) => Math.max(max, secret.length), 0);
  let pending = '';

  return Object.freeze({
    write(chunk) {
      const text = chunk === undefined || chunk === null ? '' : String(chunk);
      if (secrets.length === 0) {
        return text;
      }
      pending += text;
      let safeLimit = pending.length - maxSecretLength;
      if (safeLimit <= 0) {
        return '';
      }
      safeLimit = findOverlapBoundary(pending, safeLimit, secrets);
      if (safeLimit <= 0) {
        return '';
      }
      const output = pending.slice(0, safeLimit);
      pending = pending.slice(safeLimit);
      return redactText(output, secrets);
    },

    flush() {
      const output = redactText(pending, secrets);
      pending = '';
      return output;
    },
  });
}

module.exports = {
  createStreamingRedactor,
};
