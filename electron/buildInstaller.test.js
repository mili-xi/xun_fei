const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const {
  buildEnv,
  resolveNsisDir,
  resolveNsisResourcesDir,
  resolveSevenZipPath,
} = require('./buildInstaller');

test('build installer helpers honor explicit environment overrides', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-installer-'));
  const nsisDir = path.join(tempRoot, 'nsis');
  const nsisResourcesDir = path.join(tempRoot, 'nsis-resources');
  const sevenZipPath = path.join(tempRoot, '7z.exe');

  fs.mkdirSync(nsisDir, { recursive: true });
  fs.mkdirSync(nsisResourcesDir, { recursive: true });
  fs.writeFileSync(sevenZipPath, '');

  const previous = {
    ELECTRON_BUILDER_NSIS_DIR: process.env.ELECTRON_BUILDER_NSIS_DIR,
    ELECTRON_BUILDER_NSIS_RESOURCES_DIR: process.env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR,
    ELECTRON_BUILDER_7ZIP_PATH: process.env.ELECTRON_BUILDER_7ZIP_PATH,
  };

  process.env.ELECTRON_BUILDER_NSIS_DIR = nsisDir;
  process.env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR = nsisResourcesDir;
  process.env.ELECTRON_BUILDER_7ZIP_PATH = sevenZipPath;

  try {
    assert.equal(resolveNsisDir(), nsisDir);
    assert.equal(resolveNsisResourcesDir(), nsisResourcesDir);
    assert.equal(resolveSevenZipPath(), sevenZipPath);

    const env = buildEnv();
    assert.equal(env.ELECTRON_BUILDER_NSIS_DIR, nsisDir);
    assert.equal(env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR, nsisResourcesDir);
    assert.equal(env.ELECTRON_BUILDER_7ZIP_PATH, sevenZipPath);
    assert.equal(env.CSC_IDENTITY_AUTO_DISCOVERY, 'false');
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value == null) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
});
