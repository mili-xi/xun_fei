const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));

test('package metadata is ready for the planned open-source release', () => {
  assert.equal(pkg.version, '1.1.0');
  assert.equal(pkg.license, 'Apache-2.0');
  assert.equal(pkg.private, true);
  assert.equal(pkg.build.productName, 'Xunfei Job Assistant');
});

test('package resources exclude repository env files and include Windows release targets', () => {
  const resourceSources = pkg.build.extraResources.map((entry) => entry.from);
  assert.equal(resourceSources.includes('.env'), false);
  assert.deepEqual(pkg.build.win.target, ['nsis', 'zip']);
});
