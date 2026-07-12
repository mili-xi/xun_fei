const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

function firstExistingPath(candidates) {
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return null;
}

function firstExistingFile(candidates) {
  return firstExistingPath(candidates.filter(Boolean));
}

function firstExistingDir(candidates) {
  return firstExistingPath(candidates.filter(Boolean));
}

function resolveNsisDir() {
  return firstExistingDir([
    process.env.ELECTRON_BUILDER_NSIS_DIR,
    path.join(process.env.LOCALAPPDATA || '', 'electron-builder', 'Cache', 'nsis', 'nsis-3.0.4.1'),
  ]);
}

function resolveNsisResourcesDir() {
  return firstExistingDir([
    process.env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR,
    path.join(process.env.LOCALAPPDATA || '', 'electron-builder', 'Cache', 'nsis', 'nsis-resources-3.4.1'),
  ]);
}

function resolveSevenZipPath() {
  return firstExistingFile([
    process.env.ELECTRON_BUILDER_7ZIP_PATH,
    'C:\\Program Files\\7-Zip\\7z.exe',
    'C:\\Program Files (x86)\\7-Zip\\7z.exe',
    'C:\\Program Files\\NVIDIA Corporation\\NVIDIA App\\7z.exe',
  ]);
}

function buildEnv() {
  const env = {
    ...process.env,
    CSC_IDENTITY_AUTO_DISCOVERY: 'false',
  };

  const nsisDir = resolveNsisDir();
  const nsisResourcesDir = resolveNsisResourcesDir();
  const sevenZipPath = resolveSevenZipPath();

  if (nsisDir) {
    env.ELECTRON_BUILDER_NSIS_DIR = nsisDir;
  }
  if (nsisResourcesDir) {
    env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR = nsisResourcesDir;
  }
  if (sevenZipPath) {
    env.ELECTRON_BUILDER_7ZIP_PATH = sevenZipPath;
  }

  return env;
}

function printResolvedTools(env) {
  const resolved = [
    ['ELECTRON_BUILDER_NSIS_DIR', env.ELECTRON_BUILDER_NSIS_DIR],
    ['ELECTRON_BUILDER_NSIS_RESOURCES_DIR', env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR],
    ['ELECTRON_BUILDER_7ZIP_PATH', env.ELECTRON_BUILDER_7ZIP_PATH],
  ];

  for (const [key, value] of resolved) {
    if (value) {
      console.log(`${key}=${value}`);
    }
  }
}

function main() {
  const env = buildEnv();
  printResolvedTools(env);
  const cliPath = path.join(process.cwd(), 'node_modules', 'electron-builder', 'cli.js');

  const child = spawn(
    process.execPath,
    [cliPath, '--win', 'nsis'],
    {
      cwd: process.cwd(),
      env,
      stdio: 'inherit',
      windowsHide: true,
    },
  );

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 1);
  });
}

if (require.main === module) {
  main();
}

module.exports = {
  buildEnv,
  resolveNsisDir,
  resolveNsisResourcesDir,
  resolveSevenZipPath,
};
