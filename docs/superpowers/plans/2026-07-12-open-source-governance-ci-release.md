# Open Source Governance, CI, And Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the cleaned source into a legally open, contributor-friendly project with enforceable CI, security checks, and reproducible credential-free Windows releases.

**Architecture:** Apache-2.0 covers original source while third-party notices preserve upstream licenses. GitHub Actions separates fast pull-request CI from CodeQL and tag-only Windows release jobs. Runtime inputs are downloaded from official HTTPS sources into ignored staging directories, pinned by a committed lock manifest, and recursively scanned before GitHub Release publication.

**Tech Stack:** Apache-2.0, Contributor Covenant, GitHub Actions, CodeQL, Dependabot, Gitleaks, Node/Python tests, Electron Builder, PowerShell, CycloneDX/SBOM tooling, GitHub Releases.

---

### Task 1: Establish Legal And Maintainer Metadata

**Files:**
- Create: `LICENSE`
- Create: `NOTICE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `MAINTAINERS.md`
- Modify: `package.json`

- [ ] **Step 1: Verify the right to license every original contribution**

Review contributor and asset provenance without opening removed credential blobs:

```powershell
git shortlog -sne --all
git log --format='%H%x09%an%x09%ae' --all | Sort-Object -Unique
git log --oneline -- build 前端 后端 electron
```

Expected: the owner confirms in the task record that they hold or have obtained the right to publish the contributions from `@Hans-0521` and `@cyx180-code` under Apache-2.0, as already represented in the approved design discussion. Audit icons, installer artwork, copied samples, and third-party source separately. If any contribution cannot be licensed, stop and either remove/replace it with reviewed original work or retain its existing compatible license and attribution; do not relabel third-party work as Apache-2.0.

- [ ] **Step 2: Add the canonical Apache-2.0 license**

Run:

```powershell
Invoke-WebRequest 'https://www.apache.org/licenses/LICENSE-2.0.txt' -OutFile LICENSE
Select-String -Path LICENSE -Pattern 'Apache License' | Select-Object -First 1
```

Expected: the canonical January 2004 Apache License 2.0 text is saved and the first match is present.

- [ ] **Step 3: Add the project NOTICE**

Create `NOTICE` with this factual content:

```text
Xunfei Job Assistant
Copyright 2026 mili-xi and contributors

This product includes software developed by third parties. Their licenses are
listed in THIRD_PARTY_NOTICES.md and in the generated release SBOM.

This is an independent community project. It is not affiliated with or
endorsed by iFlytek or OpenAI. Product and company names are trademarks of
their respective owners.
```

- [ ] **Step 4: Add maintainership and third-party boundaries**

`MAINTAINERS.md` names `@mili-xi` as primary maintainer and describes responsibility for reviews, issue triage, security response, and releases. It lists `@Hans-0521` and `@cyx180-code` only as historical contributors, not maintainers.

`THIRD_PARTY_NOTICES.md` records Electron, Python, Flask, requests, websocket-client, ffmpeg, NSIS, and 7-Zip with project URLs and license families. State that the exact release inventory is generated in the SBOM and that ffmpeg redistribution must use a build whose license is compatible with the distributed project.

- [ ] **Step 5: Verify metadata consistency**

Add a Node test in `electron/packageConfig.test.js` asserting `package.json.license === 'Apache-2.0'` and `version === '1.1.0'`. Run:

```powershell
node --test electron/packageConfig.test.js
```

Expected: pass.

- [ ] **Step 6: Commit legal metadata**

```powershell
git add -- LICENSE NOTICE THIRD_PARTY_NOTICES.md MAINTAINERS.md package.json electron/packageConfig.test.js
git commit -m "docs: establish Apache-2.0 project governance"
```

### Task 2: Add Community And Security Processes

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `GOVERNANCE.md`
- Create: `CHANGELOG.md`
- Create: `.github/CODEOWNERS`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `tests/test_repository_contract.py`

- [ ] **Step 1: Write the failing community-file contract**

Create `tests/test_repository_contract.py` with `unittest` and `Path`. Assert required governance files exist, `LICENSE` contains Apache 2.0, `SECURITY.md` names GitHub private vulnerability reporting, `CODEOWNERS` names `@mili-xi`, and the independent-project disclaimer is present. Restrict unfinished-marker checks to public governance/README documents; construct the forbidden strings as `"T" + "BD"` and `"PLACE" + "HOLDER"` so the contract test does not match its own source. Do not scan application source comments.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
```

Expected: failures naming the missing governance files.

- [ ] **Step 3: Write the contribution contract**

`CONTRIBUTING.md` must contain exact commands for a `.venv`, `pip install -r requirements.txt`, `npm ci`, Python tests, Electron tests, package preflight, branch naming, pull-request review, and a statement that credentials, resumes, recordings, and generated binaries must never be committed.

`GOVERNANCE.md` defines lazy consensus for routine work, primary-maintainer final responsibility, required review/CI for `main`, security exception handling, semantic versioning, and release ownership.

- [ ] **Step 4: Add private security reporting**

`SECURITY.md` instructs reporters to use GitHub private vulnerability reporting from the Security tab. It prohibits public disclosure of credentials or personal resume/audio data, promises acknowledgement within seven days without guaranteeing a fix date, lists supported version `1.1.x`, and documents the rotate-first response to a credential incident.

- [ ] **Step 5: Add community templates**

Use Contributor Covenant 2.1 for `CODE_OF_CONDUCT.md`. `CODEOWNERS` contains:

```text
* @mili-xi
/.github/ @mili-xi
/electron/ @mili-xi
/后端/ @mili-xi
```

Issue forms collect reproducible bug details and user-facing feature outcomes without requesting credentials, resumes, recordings, or other personal data. The voluntary adoption form is owned by the impact/application plan so its evidence contract and metrics validation stay together.

- [ ] **Step 6: Add changelog and PR review checklist**

Initialize `CHANGELOG.md` using Keep a Changelog headings for `Unreleased` and `1.1.0`, describing credential removal, BYOK settings, source-only history, CI/security, and clean releases. The PR template requires tests, secret scan, docs impact, and confirmation that no generated artifact or personal data is included.

- [ ] **Step 7: Verify GREEN**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
```

Expected: pass.

- [ ] **Step 8: Commit community processes**

```powershell
git add -- CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md GOVERNANCE.md CHANGELOG.md .github tests/test_repository_contract.py
git commit -m "docs: add contributor and security processes"
```

### Task 3: Add Pull-Request CI And Security Automation

**Files:**
- Create: `electron/workflowConfig.test.js`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/codeql.yml`
- Create: `.github/workflows/dependency-review.yml`
- Create: `.github/workflows/secret-scan.yml`
- Create: `.github/dependabot.yml`
- Create: `requirements-dev.txt`
- Modify: `pyrightconfig.json`
- Modify: `package.json`
- Modify: `package-lock.json`

- [ ] **Step 1: Pin workflow-test and developer tooling**

Create `requirements-dev.txt` with exactly:

```text
cyclonedx-bom==7.3.0
pip-tools==7.5.3
ruff==0.15.21
```

Pin the Node tools used by source checks and release verification:

```powershell
npm install --save-dev --save-exact pyright@1.1.411 yaml@2.9.0 `
  @cyclonedx/cyclonedx-npm@6.0.0 7zip-bin@5.2.0 @electron/asar@4.2.0
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Expected: `package.json`, `package-lock.json`, and `requirements-dev.txt` contain only the selected exact versions.

- [ ] **Step 2: Write a failing structured workflow contract test**

Create `electron/workflowConfig.test.js` using `yaml.parse()` rather than text matching. Load each workflow as an object and assert:

- CI triggers on pull requests and pushes to `main`/`dev`;
- source jobs use Node `24.15.0` and Python `3.13.14` from clean installs;
- package preflight runs;
- workflow permissions default to read-only;
- CodeQL covers `python` and `javascript-typescript`;
- every `uses:` value ends in a 40-character commit SHA;
- release permissions are absent from pull-request CI.

- [ ] **Step 3: Verify RED**

```powershell
node --test electron/workflowConfig.test.js
```

Expected: failure because workflows do not exist.

- [ ] **Step 4: Implement CI workflows with immutable action pins**

Set workflow display names exactly to `CI`, `CodeQL`, `Dependency Review`, and `Secret Scan`; the publication plan derives required status contexts from those names. `ci.yml` uses `permissions: contents: read`, Windows and Ubuntu source-test jobs, Node cache from `package-lock.json`, Python cache from `requirements.txt`, `npm ci`, `pip install`, `node --test electron/*.test.js`, `python -m unittest discover -s tests -v`, Ruff, Pyright, and `npm run verify:packaging-context`.

Use these resolved official action commits and preserve the readable version in a comment:

```text
actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd              # v5
actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e            # v6
actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1e          # v6
github/codeql-action/*@1ad29ea4a422cce9a242a9fae469541dcd08addc         # v4
actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0
gitleaks/gitleaks-action@dcedce43c6f43de0b836d1fe38946645c9c638dc       # v2
```

`dependency-review.yml` runs only on pull requests with read-only contents permission. `secret-scan.yml` runs Gitleaks on pull requests, pushes, and a weekly schedule with redacted output.

- [ ] **Step 5: Add deterministic developer checks**

Add `npm` scripts `test`, `test:python`, `lint`, and `verify`. Configure Ruff for Python 3.13 without rewriting unrelated style in the first pass; limit the initial rule set to syntax, undefined names, import correctness, and common security mistakes. Configure Pyright to check the backend at its current strictness without silently excluding modified files.

- [ ] **Step 6: Configure Dependabot**

Add weekly npm, pip, and GitHub Actions updates, grouped by ecosystem, with a limit of five open PRs and `@mili-xi` as reviewer.

- [ ] **Step 7: Run local workflow contracts and checks**

```powershell
npm ci
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
node --test electron/workflowConfig.test.js
npm run verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
```

Expected: all checks pass.

- [ ] **Step 8: Commit CI and automation**

```powershell
git add -- .github requirements-dev.txt pyrightconfig.json package.json package-lock.json electron/workflowConfig.test.js tests/test_repository_contract.py
git commit -m "ci: add tests and security automation"
```

### Task 4: Build A Reproducible Windows Runtime Staging Pipeline

**Files:**
- Create: `scripts/windows-runtime.lock.json`
- Create: `scripts/prepare-windows-runtime.ps1`
- Create: `scripts/test-prepare-windows-runtime.ps1`
- Create: `requirements-release.txt`
- Modify: `package.json`

- [ ] **Step 1: Write failing manifest and script tests**

The test creates local synthetic ZIP and 7z archives and asserts the preparation script rejects a wrong SHA-256, accepts the correct hash, stages only under the resolved output directory, and never reads `.env`. It asserts each manifest item has an HTTPS URL, exact version, immutable filename, 64-character lowercase SHA-256, source URL, and license URL. Add a traversal fixture such as `..\escaped.txt` and assert it is rejected before extraction. Assert the executable contract is exactly `runtime\ffmpeg.exe` and the packaged Electron launcher injects that same resolved path as `FFMPEG_PATH`.

- [ ] **Step 2: Verify RED**

```powershell
pwsh -File scripts/test-prepare-windows-runtime.ps1
```

Expected: failure because the manifest and preparation script do not exist.

- [ ] **Step 3: Commit the reviewed immutable runtime manifest**

Use this selected manifest content; verify both remote checksum sources again during implementation before committing it:

```json
{
  "schemaVersion": 1,
  "python": {
    "version": "3.13.14",
    "url": "https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip",
    "filename": "python-3.13.14-embed-amd64.zip",
    "sha256": "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907",
    "archiveType": "zip",
    "sourceUrl": "https://www.python.org/downloads/release/python-31314/",
    "licenseUrl": "https://docs.python.org/3/license.html"
  },
  "ffmpeg": {
    "version": "2026-07-06-git-c6498178bb",
    "url": "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-2026-07-06-git-c6498178bb-essentials_build.7z",
    "filename": "ffmpeg-2026-07-06-git-c6498178bb-essentials_build.7z",
    "sha256": "036ec18558000a80847f69a30052438274202670e13ed7e47491ba2c7058dd53",
    "archiveType": "7z",
    "sourceUrl": "https://github.com/FFmpeg/FFmpeg/commit/c6498178bb",
    "licenseUrl": "https://www.gnu.org/licenses/gpl-3.0.txt"
  }
}
```

The selected Gyan essentials build is GPLv3. Keep it as a separately licensed bundled program, include its license/source notice in the release, and do not describe it as Apache-2.0 code.

- [ ] **Step 4: Generate the hashed Python release lock**

```powershell
.\.venv\Scripts\python.exe -m piptools compile --generate-hashes --resolver=backtracking `
  --output-file requirements-release.txt requirements.txt
rg -n "(^|[<>=~!])\s*[0-9].*,|\*" requirements-release.txt
```

Expected: `requirements-release.txt` pins every transitive dependency with hashes; the range/floating-version scan has no match.

- [ ] **Step 5: Implement staging for the embeddable interpreter**

The PowerShell script resolves and validates the output path before network access, downloads into a unique temporary directory, verifies SHA-256 before extraction, and uses `require('7zip-bin').path7za` for the pinned 7z executable. After extracting Python, replace `python313._pth` with exactly:

```text
python313.zip
.
Lib\site-packages
import site
```

Install the locked wheels from the host build Python without bootstrapping pip into the embedded runtime:

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: `
  --platform win_amd64 --implementation cp --python-version 3.13 --abi cp313 `
  --target runtime\python\Lib\site-packages -r requirements-release.txt
```

Stage the executable at `runtime\ffmpeg.exe`, matching the existing Electron/backend resolution contract. Put its packaged license/readme under `runtime\licenses\ffmpeg\`; reject any archive entry whose resolved destination escapes the output root. Cleanup runs in `finally` on success or failure.

- [ ] **Step 6: Run tests and a real staging pass**

```powershell
pwsh -File scripts/test-prepare-windows-runtime.ps1
pwsh -File scripts/prepare-windows-runtime.ps1 -Manifest scripts/windows-runtime.lock.json -Output runtime
runtime\python\python.exe -c "import flask, requests, websocket; print('runtime imports ok')"
runtime\python\python.exe -m unittest discover -s tests -v
```

Expected: script tests and all Python tests pass from the staged runtime.

- [ ] **Step 7: Commit reproducible runtime inputs**

```powershell
git add -- scripts requirements-release.txt package.json package-lock.json
git commit -m "build: stage pinned Windows runtime inputs"
```

### Task 5: Recursively Verify Final Release Artifacts

**Files:**
- Create: `scripts/verify-release-artifacts.ps1`
- Create: `scripts/test-verify-release-artifacts.ps1`
- Modify: `electron/buildInstaller.js`
- Modify: `electron/buildInstaller.test.js`
- Modify: `package.json`

- [ ] **Step 1: Write failing artifact-verifier tests**

Build synthetic directory/ZIP fixtures containing `.env`, a secret sentinel, a clean `.env.example`, and normal source. Assert the verifier rejects forbidden files/values without printing the sentinel, accepts clean fixtures, and writes a SHA-256 checksum file in normal mode. Add `-ScanOnly` coverage proving a pre-existing `SHA256SUMS.txt` remains byte-for-byte unchanged while recursive scanning still runs.

- [ ] **Step 2: Verify RED**

```powershell
pwsh -File scripts/test-verify-release-artifacts.ps1
```

Expected: failure because the verifier does not exist.

- [ ] **Step 3: Implement recursive verification**

The verifier resolves `7zip-bin` and `@electron/asar` from the pinned direct dev dependencies, expands ZIP/7z/NSIS containers and `app.asar` into a unique temporary directory, scans names and contents for forbidden credential files and sensitive values read internally from the documented credential environment names, deletes extraction output in `finally`, and emits only path/category findings. Sensitive values are never accepted as command-line arguments and never echoed. Normal mode creates `SHA256SUMS.txt` only after a clean scan; `-ScanOnly` never creates, deletes, or rewrites a checksum file and is used for independently downloaded artifacts.

Make `npm run build:release` the only release-build entry point. It calls `buildInstaller.js`, which runs packaging preflight, invokes Electron Builder once with `--win nsis zip --publish never`, then runs the final verifier. Keep `npm run pack` only for an unpacked local diagnostic build; CI and release documentation must never use it for publication.

- [ ] **Step 4: Run tests and clean package build**

```powershell
node --test electron/buildInstaller.test.js
pwsh -File scripts/test-verify-release-artifacts.ps1
npm run build:release
```

Expected: all tests pass; NSIS and ZIP exist, `win-unpacked` contains no `.env`, and checksums are generated only after scanning.

- [ ] **Step 5: Commit release verification**

```powershell
git add -- scripts electron/buildInstaller.js electron/buildInstaller.test.js package.json package-lock.json
git commit -m "build: verify final Windows release artifacts"
```

### Task 6: Add Manual Release Preflight And Tag-Only Publication

**Files:**
- Create: `.github/workflows/release-windows.yml`
- Create: `scripts/renderReleaseNotes.js`
- Create: `scripts/renderReleaseNotes.test.js`
- Modify: `electron/workflowConfig.test.js`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Write a failing release-workflow contract**

Parse the workflow with `yaml`. Assert it accepts `workflow_dispatch` for a non-publishing cloud preflight and `v*` tag pushes for publication. Assert the build/scan job is read-only on both events; the publish job runs only for a tag push, checks tag commit equals `main` and package version equals the tag, and alone receives `contents: write`. Both paths run full tests, secret/package scans, pinned runtime staging, NSIS+ZIP build, recursive verification, release-note rendering, SBOMs, and checksums. Add a unit test proving `renderReleaseNotes.js` extracts the non-empty `1.1.0` section from `CHANGELOG.md` and fails without changing output when the heading is absent or duplicated.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/workflowConfig.test.js
node --test scripts/renderReleaseNotes.test.js
```

Expected: failure because `release-windows.yml` does not exist.

- [ ] **Step 3: Implement a reusable build/verify job and isolated publish job**

The Windows `build-and-verify` job has read-only repository permissions on both events. Pin checkout/setup actions to the SHAs from Task 3, set Node `24.15.0` and Python `3.13.14`, fetch full history, run `npm ci`, exact Python dependencies, all tests, Gitleaks, package preflight, runtime staging, and `npm run build:release`. On a tag event, fail unless `HEAD == origin/main` and `package.json.version == $tag.TrimStart('v')`.

Generate both SBOMs with the already pinned tools:

```powershell
node scripts/renderReleaseNotes.js --version 1.1.0 --changelog CHANGELOG.md `
  --output dist\release-notes.md
npx cyclonedx-npm --output-format JSON --output-file dist\xunfei-job-assistant-npm.cdx.json
cyclonedx-py requirements requirements-release.txt --output-format JSON `
  --output-file dist\xunfei-job-assistant-python.cdx.json
pwsh -File scripts/verify-release-artifacts.ps1 -Dist dist
```

The final verifier run occurs after SBOM generation, replaces the earlier build checksum manifest, and includes every intended upload except `SHA256SUMS.txt` itself. A workflow contract test must enforce this ordering.

Upload the already verified release directory using these immutable official action pins:

```text
actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02   # v4
actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0 # v5
```

Upload one artifact named `verified-release` with `if-no-files-found: error`, containing only the top-level installer, portable ZIP, release notes, checksum manifest, and SBOMs. The `publish` job is conditional on a `push` event whose ref starts with `refs/tags/v`, receives `contents: write`, downloads that artifact to `verified-release/`, asserts the expected one-EXE/one-ZIP/one-checksum/one-notes/two-SBOM layout, and rechecks every manifest entry. Enumerate exact paths rather than passing wildcards to a native command:

```powershell
$releaseRoot = (Resolve-Path 'verified-release').Path
$installer = @(Get-ChildItem $releaseRoot -File -Filter '*.exe')
$portable = @(Get-ChildItem $releaseRoot -File -Filter '*.zip')
$sboms = @(Get-ChildItem $releaseRoot -File -Filter '*.cdx.json')
$checksum = @(Get-Item (Join-Path $releaseRoot 'SHA256SUMS.txt'))
$notes = @(Get-Item (Join-Path $releaseRoot 'release-notes.md'))
if ($installer.Count -ne 1 -or $portable.Count -ne 1 -or $sboms.Count -ne 2 -or
    $checksum.Count -ne 1 -or $notes.Count -ne 1) { throw 'Verified release layout is invalid.' }
$assetPaths = @($installer.FullName, $portable.FullName) + @($sboms.FullName) + `
  @($checksum[0].FullName, $notes[0].FullName)
& gh release create $env:GITHUB_REF_NAME --repo mili-xi/xun_fei --verify-tag `
  --title $env:GITHUB_REF_NAME --notes-file $notes[0].FullName @assetPaths
if ($LASTEXITCODE -ne 0) { throw 'GitHub Release publication failed.' }
```

`workflow_dispatch` completes after build/scan and can never reach `gh release create`. Only the conditional publish job receives `contents: write`; all other workflow scopes remain read-only. Do not claim code signing.

- [ ] **Step 4: Finalize the `1.1.0` changelog**

Obtain `$releaseDate = Get-Date -Format 'yyyy-MM-dd'` during implementation and create the `1.1.0` heading with that value. Move all release-ready entries from `Unreleased` beneath it, including credential architecture, removed embedded secrets, cleaned history, source-only distribution, Apache licensing, governance, CI/security, and reproducible release verification. The committed changelog contains the resolved ISO date, never a template token.

- [ ] **Step 5: Run contracts and commit**

```powershell
node --test electron/workflowConfig.test.js
node --test scripts/renderReleaseNotes.test.js
npm run verify
git add -- .github/workflows/release-windows.yml electron/workflowConfig.test.js scripts/renderReleaseNotes.js scripts/renderReleaseNotes.test.js CHANGELOG.md
git commit -m "ci: publish verified Windows releases from tags"
```

### Task 7: Document The Public Project And Capture A Real Demo

**Files:**
- Rewrite: `README.md`
- Create: `README.zh-CN.md`
- Create: `docs/architecture.md`
- Create: `docs/security-model.md`
- Create: `docs/assets/app-overview.png`
- Modify: `tests/test_repository_contract.py`

- [ ] **Step 1: Add failing documentation contracts**

Assert both READMEs include Apache-2.0, GitHub Releases downloads, BYOK/no bundled credentials, primary maintainer, contribution/security links, current limitations, no affiliation statement, screenshot, source setup, test commands, and checksum/no-code-signing disclosure. Assert they do not link to tracked `dist/` artifacts or claim external users.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
```

Expected: failure against the current internal-distribution README.

- [ ] **Step 3: Write English and Chinese project documentation**

Use the factual positioning approved in the design: an independent, local-first open-source desktop job-search assistant for Chinese-speaking users. Document resume analysis, JD matching, interview practice, voice functions, BYOK configuration, architecture, privacy boundaries, setup, CI, Releases, contribution, security reporting, and limitations. State that no verified public adoption metrics exist yet.

- [ ] **Step 4: Capture and inspect the application screenshot**

Run the app with synthetic sample text and no real credentials or personal resume data. Capture the first usable application screen to `docs/assets/app-overview.png`. Inspect the image before commit and verify it contains no name, email, token, application ID, resume, voice transcript, local path, or debug overlay.

- [ ] **Step 5: Document architecture and security model**

`architecture.md` maps renderer, Electron main process, encrypted store, child backend, provider clients, and release pipeline. `security-model.md` records trust boundaries, BYOK ownership, DPAPI limits, local logs, personal-data handling, reporting, and the absence of a hosted maintainer credential proxy.

- [ ] **Step 6: Verify and commit public docs**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
git add -- README.md README.zh-CN.md docs tests/test_repository_contract.py
git commit -m "docs: publish bilingual user and security guides"
```

### Task 8: Review And Verify The Governance/Release Phase

**Files:** All files changed in Tasks 1-7.

- [ ] **Step 1: Run the full non-release suite**

```powershell
npm run verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
gitleaks dir . --redact --exit-code 1
pwsh -File scripts/test-prepare-windows-runtime.ps1
pwsh -File scripts/test-verify-release-artifacts.ps1
git diff origin/dev...HEAD --check
```

Expected: every command exits `0`.

- [ ] **Step 2: Build and inspect a release candidate**

```powershell
pwsh -File scripts/prepare-windows-runtime.ps1 -Manifest scripts/windows-runtime.lock.json -Output runtime
npm run build:release
```

Expected: verified installer and ZIP, SHA-256 checksums, no `.env`, no credential sentinel, and no claim of code signing.

- [ ] **Step 3: Request spec and code-quality reviews**

Use fresh reviewers with the approved design, this plan, and base/head SHAs. Fix all specification gaps and all Critical/Important quality or security findings; rerun Steps 1-2 after every fix.

- [ ] **Step 4: Confirm the phase boundary**

```powershell
git status -sb
git log --oneline --decorate -12
```

Expected: clean reviewed branch. Continue with `2026-07-12-impact-application-and-publish.md`.
