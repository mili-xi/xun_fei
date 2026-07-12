const assert = require('node:assert/strict');
const test = require('node:test');

const {
  findForbiddenTrackedInputs,
  isAllowedReferenceFile,
  validatePackageConfig,
} = require('./packagingPolicy');

test('package config does not bundle env files and declares OSS release metadata', () => {
  const errors = validatePackageConfig({
    version: '1.1.0',
    license: 'Apache-2.0',
    build: {
      extraResources: [{ from: '后端', to: 'app-resources/backend' }],
      win: { target: ['nsis', 'zip'] },
    },
  });
  assert.deepEqual(errors, []);
});

test('package config rejects env resources', () => {
  const errors = validatePackageConfig({
    version: '1.1.0',
    license: 'Apache-2.0',
    build: {
      extraResources: [{ from: '.env', to: 'app-resources/.env' }],
      win: { target: ['nsis', 'zip'] },
    },
  });
  assert.match(errors.join('\n'), /must not package \.env/);
});

test('tracked input policy allows .env.example but rejects generated and secret-bearing inputs', () => {
  assert.equal(isAllowedReferenceFile('.env.example'), true);
  assert.deepEqual(
    findForbiddenTrackedInputs([
      '.env.example',
      '.env',
      'dist/app.zip',
      'runtime/ffmpeg.exe',
      'src/index.js',
    ]),
    ['.env', 'dist/app.zip', 'runtime/ffmpeg.exe'],
  );
});
