const assert = require('node:assert/strict');
const test = require('node:test');

const { createStreamingRedactor } = require('./logRedactor');

test('streaming redactor masks full secret values', () => {
  const redactor = createStreamingRedactor(['spark-secret', 'api-key']);

  const output = redactor.write('token=spark-secret key=api-key') + redactor.flush();

  assert.equal(output, 'token=[REDACTED] key=[REDACTED]');
});

test('streaming redactor masks secrets split across chunks', () => {
  const redactor = createStreamingRedactor(['cross-chunk-secret']);

  const first = redactor.write('prefix cross-ch');
  const second = redactor.write('unk-secret suffix');
  const final = redactor.flush();

  assert.equal(first.includes('cross-ch'), false);
  assert.equal(first + second + final, 'prefix [REDACTED] suffix');
});

test('streaming redactor ignores blank and duplicate values', () => {
  const redactor = createStreamingRedactor(['', 'same-secret', 'same-secret']);

  const output = redactor.write('same-secret') + redactor.flush();

  assert.equal(output, '[REDACTED]');
});
