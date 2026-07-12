const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');

const APP_RESOURCES_DIR = 'app-resources';
const BACKEND_DIR_NAMES = ['backend', '\u540e\u7aef'];
const FRONTEND_DIR_NAMES = ['frontend', '\u524d\u7aef'];

function getAppRoot({ isPackaged, appPath, resourcesPath }) {
  if (isPackaged) {
    return path.join(resourcesPath, APP_RESOURCES_DIR);
  }
  return appPath;
}

function findExistingDir(appRoot, names) {
  for (const name of names) {
    const candidate = path.join(appRoot, name);
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return path.join(appRoot, names[0]);
}

function prependPath(value, entry) {
  if (!value) {
    return entry;
  }
  return `${entry}${path.delimiter}${value}`;
}

function getBundledEnvFile(appRoot) {
  return path.join(appRoot, '.env');
}

function getBundledFfmpegPath(appRoot) {
  return path.join(appRoot, 'runtime', 'ffmpeg.exe');
}

function buildPythonBootstrapScript() {
  return [
    'import runpy',
    'import sys',
    'backend_dir = sys.argv[1]',
    'app_path = sys.argv[2]',
    'sys.path.insert(0, backend_dir)',
    'runpy.run_path(app_path, run_name="__main__")',
  ].join('; ');
}

function createLaunchToken() {
  return crypto.randomBytes(32).toString('base64url');
}

function buildBackendLaunchConfig({
  appRoot,
  port,
  env = process.env,
  launchToken,
}) {
  const backendDir = findExistingDir(appRoot, BACKEND_DIR_NAMES);
  const frontendDir = findExistingDir(appRoot, FRONTEND_DIR_NAMES);
  const pythonExe = path.join(appRoot, 'runtime', 'python', 'python.exe');
  const flaskApp = path.join(backendDir, 'app.py');
  return {
    pythonExe,
    backendDir,
    frontendDir,
    backendEntry: flaskApp,
    args: ['-c', buildPythonBootstrapScript(), backendDir, flaskApp],
    options: {
      cwd: appRoot,
      env: {
        ...env,
        PORT: String(port),
        FLASK_DEBUG: '0',
        FRONTEND_DIR: frontendDir,
        PYTHONPATH: prependPath(env.PYTHONPATH, backendDir),
        ...(launchToken ? { XUNFEI_LAUNCH_TOKEN: launchToken } : {}),
      },
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  };
}

function inspectBundledResources({ appRoot, launchConfig }) {
  const errors = [];
  const warnings = [];
  const envFile = getBundledEnvFile(appRoot);
  const ffmpegExe = getBundledFfmpegPath(appRoot);

  if (!fs.existsSync(launchConfig.pythonExe)) {
    errors.push(`缺少 Python 运行时: ${launchConfig.pythonExe}`);
  }
  if (!fs.existsSync(launchConfig.backendEntry)) {
    errors.push(`缺少后端入口: ${launchConfig.backendEntry}`);
  }
  if (!fs.existsSync(launchConfig.frontendDir)) {
    errors.push(`缺少前端目录: ${launchConfig.frontendDir}`);
  }
  if (!fs.existsSync(envFile)) {
    warnings.push(`未找到运行配置文件: ${envFile}`);
  }
  if (!fs.existsSync(ffmpegExe)) {
    warnings.push(`未找到音频转换工具 ffmpeg.exe: ${ffmpegExe}`);
  }

  return {
    envFile,
    ffmpegExe,
    errors,
    warnings,
  };
}

function canListen(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close(() => resolve(true));
    });
    server.listen(port, host);
  });
}

async function findFreePort(startPort = 5000, attempts = 30) {
  for (let offset = 0; offset < attempts; offset += 1) {
    const port = startPort + offset;
    if (await canListen(port)) {
      return port;
    }
  }
  throw new Error(`No free port found from ${startPort} after ${attempts} attempts`);
}

function buildHealthRequestOptions({ port, timeoutMs, launchToken }) {
  return {
    hostname: '127.0.0.1',
    port,
    path: '/api/health',
    timeout: timeoutMs,
    headers: launchToken ? { 'X-Xunfei-Launch-Token': launchToken } : {},
  };
}

function isHealthyPayload(body) {
  try {
    const payload = JSON.parse(body);
    return payload && payload.code === 0 && payload.data && payload.data.status === 'ok';
  } catch (_error) {
    return false;
  }
}

function waitForHealth({
  port,
  timeoutMs = 30000,
  intervalMs = 500,
  launchToken,
}) {
  const deadline = Date.now() + timeoutMs;

  return new Promise((resolve, reject) => {
    function check() {
      const request = http.get(
        buildHealthRequestOptions({ port, timeoutMs: Math.min(intervalMs, 1000), launchToken }),
        (response) => {
          let body = '';
          response.setEncoding('utf8');
          response.on('data', (chunk) => {
            body += chunk;
          });
          response.on('end', () => {
            if (response.statusCode === 200 && isHealthyPayload(body)) {
              resolve();
              return;
            }
            retry();
          });
        },
      );

      request.on('timeout', () => {
        request.destroy();
      });
      request.on('error', retry);
    }

    function retry() {
      if (Date.now() >= deadline) {
        reject(new Error(`Backend health check timed out on port ${port}`));
        return;
      }
      setTimeout(check, intervalMs);
    }

    check();
  });
}

function fetchHealthData({ port, timeoutMs = 5000, launchToken }) {
  return new Promise((resolve, reject) => {
    const request = http.get(
      buildHealthRequestOptions({ port, timeoutMs, launchToken }),
      (response) => {
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk) => {
          body += chunk;
        });
        response.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Invalid health response: ${error.message}`));
          }
        });
      },
    );

    request.on('timeout', () => {
      request.destroy(new Error(`Health request timed out on port ${port}`));
    });
    request.on('error', reject);
  });
}

function summarizeStartupWarnings({ resourceReport, healthData }) {
  const warnings = [...resourceReport.warnings];
  const data = healthData && healthData.data ? healthData.data : {};

  if (data.env_file_present === false) {
    warnings.push('未检测到 .env，AI 能力可能只能使用演示或兜底流程。');
  }
  if (data.ffmpeg_available === false) {
    warnings.push('未检测到 ffmpeg，部分音频转写场景可能不可用。');
  }
  if (data.spark_configured === false) {
    warnings.push('星火对话未配置，部分问答会退回本地兜底逻辑。');
  }
  if (data.ocr_configured === false) {
    warnings.push('OCR 未配置，图片简历解析可能不可用。');
  }
  if (data.voice_configured === false) {
    warnings.push('语音能力未完整配置，语音识别或语音合成可能不可用。');
  }

  return [...new Set(warnings)];
}

module.exports = {
  APP_RESOURCES_DIR,
  BACKEND_DIR_NAMES,
  buildPythonBootstrapScript,
  buildBackendLaunchConfig,
  createLaunchToken,
  fetchHealthData,
  findFreePort,
  getBundledEnvFile,
  getBundledFfmpegPath,
  getAppRoot,
  inspectBundledResources,
  summarizeStartupWarnings,
  waitForHealth,
};
