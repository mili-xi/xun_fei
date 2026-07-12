const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const FORBIDDEN_TRACKED_PATTERNS = [
  /(^|[/\\])\.env($|[./\\])/i,
  /(^|[/\\])dist([/\\]|$)/i,
  /(^|[/\\])runtime([/\\]|$)/i,
  /\.(exe|msi|zip|7z|blockmap)$/i,
];

function normalizePath(value) {
  return value.replace(/\\/g, '/');
}

function isAllowedReferenceFile(filePath) {
  return normalizePath(filePath) === '.env.example';
}

function listGitPaths(args) {
  const result = spawnSync('git', args, {
    cwd: ROOT,
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error(`git ${args.join(' ')} failed`);
  }
  return result.stdout.split(/\r?\n/).filter(Boolean);
}

function listTrackedAndStagedPaths() {
  const stagedDeletes = new Set(
    listGitPaths(['diff', '--cached', '--name-only', '--diff-filter=D']).map(normalizePath),
  );
  return [
    ...listGitPaths(['ls-files']).filter((filePath) => !stagedDeletes.has(normalizePath(filePath))),
    ...listGitPaths(['diff', '--cached', '--name-only', '--diff-filter=ACMR']),
  ];
}

function findForbiddenTrackedInputs(paths = listTrackedAndStagedPaths()) {
  const uniquePaths = [...new Set(paths.map(normalizePath))];
  return uniquePaths.filter((filePath) => {
    if (isAllowedReferenceFile(filePath)) {
      return false;
    }
    return FORBIDDEN_TRACKED_PATTERNS.some((pattern) => pattern.test(filePath));
  });
}

function loadPackageConfig() {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
}

function validatePackageConfig(pkg = loadPackageConfig()) {
  const errors = [];
  const resources = pkg.build && Array.isArray(pkg.build.extraResources)
    ? pkg.build.extraResources
    : [];
  const resourceSources = resources.map((entry) => normalizePath(String(entry.from || '')));

  if (pkg.license !== 'Apache-2.0') {
    errors.push('package.json license must be Apache-2.0');
  }
  if (pkg.version !== '1.1.0') {
    errors.push('package.json version must be 1.1.0');
  }
  if (resourceSources.includes('.env')) {
    errors.push('package.json must not package .env');
  }
  if (!pkg.build || !pkg.build.win || !Array.isArray(pkg.build.win.target)) {
    errors.push('package.json build.win.target must list release targets');
  } else {
    for (const target of ['nsis', 'zip']) {
      if (!pkg.build.win.target.includes(target)) {
        errors.push(`package.json build.win.target must include ${target}`);
      }
    }
  }
  return errors;
}

function runPackagingPolicy() {
  const errors = [
    ...findForbiddenTrackedInputs().map((filePath) => `forbidden tracked packaging input: ${filePath}`),
    ...validatePackageConfig(),
  ];
  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }
}

if (require.main === module) {
  try {
    runPackagingPolicy();
    console.log('packaging context ok');
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

module.exports = {
  findForbiddenTrackedInputs,
  isAllowedReferenceFile,
  runPackagingPolicy,
  validatePackageConfig,
};
