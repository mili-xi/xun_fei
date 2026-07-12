const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const yaml = require('yaml');

const ROOT = path.resolve(__dirname, '..');
const WORKFLOWS = path.join(ROOT, '.github', 'workflows');

function loadWorkflow(name) {
  const filePath = path.join(WORKFLOWS, name);
  assert.equal(fs.existsSync(filePath), true, `${name} must exist`);
  return yaml.parse(fs.readFileSync(filePath, 'utf8'));
}

function asArray(value) {
  if (value === undefined || value === null) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

function trigger(workflow, name) {
  const on = workflow.on || workflow.true;
  return on ? on[name] : undefined;
}

function collectUses(value, found = []) {
  if (Array.isArray(value)) {
    for (const item of value) {
      collectUses(item, found);
    }
    return found;
  }
  if (value && typeof value === 'object') {
    if (typeof value.uses === 'string') {
      found.push(value.uses);
    }
    for (const child of Object.values(value)) {
      collectUses(child, found);
    }
  }
  return found;
}

test('CI workflow runs immutable source checks with read-only permissions', () => {
  const workflow = loadWorkflow('ci.yml');

  assert.equal(workflow.name, 'CI');
  assert.ok(trigger(workflow, 'pull_request'));
  assert.deepEqual(asArray(trigger(workflow, 'push').branches).sort(), ['dev', 'main']);
  assert.deepEqual(workflow.permissions, { contents: 'read' });

  const serialized = JSON.stringify(workflow);
  assert.match(serialized, /24\.15\.0/);
  assert.match(serialized, /3\.13\.14/);
  assert.match(serialized, /npm ci/);
  assert.match(serialized, /npm run verify:packaging-context/);
  assert.doesNotMatch(serialized, /contents":"write/);
});

test('security workflows and Dependabot are configured', () => {
  const codeql = loadWorkflow('codeql.yml');
  const dependencyReview = loadWorkflow('dependency-review.yml');
  const secretScan = loadWorkflow('secret-scan.yml');
  const dependabotPath = path.join(ROOT, '.github', 'dependabot.yml');

  assert.equal(codeql.name, 'CodeQL');
  assert.deepEqual(codeql.jobs.analyze.strategy.matrix.language.sort(), ['javascript-typescript', 'python']);
  assert.equal(dependencyReview.name, 'Dependency Review');
  assert.ok(trigger(dependencyReview, 'pull_request'));
  assert.equal(secretScan.name, 'Secret Scan');
  assert.ok(trigger(secretScan, 'pull_request'));
  assert.ok(trigger(secretScan, 'push'));
  assert.ok(trigger(secretScan, 'schedule'));
  const secretScanConfig = JSON.stringify(secretScan);
  assert.match(secretScanConfig, /gitleaks git \. --redact --exit-code 1/);
  assert.doesNotMatch(secretScanConfig, /gitleaks-action/);
  assert.equal(fs.existsSync(dependabotPath), true, 'dependabot.yml must exist');
});

test('all workflow actions are pinned to immutable SHAs', () => {
  const workflows = ['ci.yml', 'codeql.yml', 'dependency-review.yml', 'secret-scan.yml']
    .map(loadWorkflow);
  const uses = workflows.flatMap((workflow) => collectUses(workflow));

  assert.ok(uses.length > 0);
  for (const action of uses) {
    assert.match(action, /@[0-9a-f]{40}$/i, `${action} must be pinned to a full commit SHA`);
  }
});
