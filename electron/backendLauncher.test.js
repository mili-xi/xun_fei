const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const path = require('node:path');
const test = require('node:test');

const {
  buildBackendLaunchConfig,
  buildPythonBootstrapScript,
  findFreePort,
  inspectBundledResources,
  getAppRoot,
  summarizeStartupWarnings,
} = require('./backendLauncher');

test('getAppRoot uses source root in development', () => {
  assert.equal(getAppRoot({ isPackaged: false, appPath: 'C:\\app' }), 'C:\\app');
});

test('getAppRoot uses app-resources in packaged builds', () => {
  assert.equal(
    getAppRoot({ isPackaged: true, resourcesPath: 'C:\\installed\\resources' }),
    path.join('C:\\installed\\resources', 'app-resources'),
  );
});

test('buildBackendLaunchConfig points at bundled Python and Flask app', () => {
  const appRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-launcher-'));
  const backendDir = path.join(appRoot, 'backend');
  const frontendDir = path.join(appRoot, 'frontend');
  fs.mkdirSync(path.join(appRoot, 'runtime', 'python'), { recursive: true });
  fs.mkdirSync(backendDir, { recursive: true });
  fs.mkdirSync(frontendDir, { recursive: true });

  const config = buildBackendLaunchConfig({
    appRoot,
    port: 5123,
    env: { EXISTING: '1', PYTHONPATH: 'C:\\existing\\pythonpath' },
  });

  assert.equal(
    config.pythonExe,
    path.join(appRoot, 'runtime', 'python', 'python.exe'),
  );
  assert.equal(
    config.args[0],
    '-c',
  );
  assert.equal(
    config.args[1],
    buildPythonBootstrapScript(),
  );
  assert.equal(
    config.args[2],
    backendDir,
  );
  assert.equal(
    config.args[3],
    path.join(appRoot, 'backend', 'app.py'),
  );
  assert.equal(config.backendDir, backendDir);
  assert.equal(config.frontendDir, frontendDir);
  assert.equal(config.backendEntry, path.join(appRoot, 'backend', 'app.py'));
  assert.equal(config.options.cwd, appRoot);
  assert.equal(config.options.env.PORT, '5123');
  assert.equal(config.options.env.FLASK_DEBUG, '0');
  assert.equal(config.options.env.EXISTING, '1');
  assert.equal(config.options.env.FRONTEND_DIR, frontendDir);
  assert.equal(config.options.env.PYTHONPATH, `${backendDir}${path.delimiter}C:\\existing\\pythonpath`);
  assert.equal(config.options.windowsHide, true);
});

test('buildBackendLaunchConfig falls back to Chinese source directory names', () => {
  const appRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-launcher-source-'));
  const backendDir = path.join(appRoot, '\u540e\u7aef');
  const frontendDir = path.join(appRoot, '\u524d\u7aef');
  fs.mkdirSync(path.join(appRoot, 'runtime', 'python'), { recursive: true });
  fs.mkdirSync(backendDir, { recursive: true });
  fs.mkdirSync(frontendDir, { recursive: true });

  const config = buildBackendLaunchConfig({
    appRoot,
    port: 5124,
    env: {},
  });

  assert.equal(config.args[2], backendDir);
  assert.equal(config.args[3], path.join(backendDir, 'app.py'));
  assert.equal(config.backendEntry, path.join(backendDir, 'app.py'));
  assert.equal(config.options.env.FRONTEND_DIR, frontendDir);
  assert.equal(config.options.env.PYTHONPATH, backendDir);
});

test('findFreePort skips occupied ports', async () => {
  const occupied = await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(server));
  });

  try {
    const usedPort = occupied.address().port;
    const freePort = await findFreePort(usedPort, 5);
    assert.notEqual(freePort, usedPort);
    assert.ok(freePort > usedPort);
  } finally {
    await new Promise((resolve) => occupied.close(resolve));
  }
});

test('inspectBundledResources reports missing optional and required files', () => {
  const appRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xunfei-resources-'));
  const backendDir = path.join(appRoot, 'backend');
  const frontendDir = path.join(appRoot, 'frontend');
  const pythonDir = path.join(appRoot, 'runtime', 'python');
  fs.mkdirSync(backendDir, { recursive: true });
  fs.mkdirSync(frontendDir, { recursive: true });
  fs.mkdirSync(pythonDir, { recursive: true });
  fs.writeFileSync(path.join(pythonDir, 'python.exe'), '');
  fs.writeFileSync(path.join(backendDir, 'app.py'), '');

  const launchConfig = buildBackendLaunchConfig({
    appRoot,
    port: 5000,
    env: {},
  });

  const report = inspectBundledResources({ appRoot, launchConfig });
  assert.deepEqual(report.errors, []);
  assert.equal(report.warnings.length, 2);
  assert.match(report.warnings[0], /\.env/);
  assert.match(report.warnings[1], /ffmpeg/);

  fs.rmSync(frontendDir, { recursive: true, force: true });
  const brokenReport = inspectBundledResources({ appRoot, launchConfig });
  assert.equal(brokenReport.errors.length, 1);
  assert.match(brokenReport.errors[0], /前端目录/);
});

test('summarizeStartupWarnings merges backend health warnings without duplicates', () => {
  const warnings = summarizeStartupWarnings({
    resourceReport: {
      warnings: ['未找到运行配置文件: C:\\app\\.env'],
    },
    healthData: {
      data: {
        env_file_present: false,
        ffmpeg_available: false,
        spark_configured: false,
        ocr_configured: false,
        voice_configured: false,
      },
    },
  });

  assert.equal(warnings.length, 6);
  assert.ok(warnings.some((warning) => warning.includes('.env')));
  assert.ok(warnings.some((warning) => warning.includes('ffmpeg')));
  assert.ok(warnings.some((warning) => warning.includes('星火对话')));
});
