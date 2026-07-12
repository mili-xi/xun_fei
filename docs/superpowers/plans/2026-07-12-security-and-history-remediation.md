# Security And History Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove leaked credentials and binary history while preserving source attribution, then replace bundled secrets with encrypted per-user configuration and safe backend error handling.

**Architecture:** Rewrite every reachable Git ref to remove `.env`, `dist/`, `runtime/`, and packaged binaries before feature work. The Electron main process owns encrypted credentials through `safeStorage`, injects them only into the Flask child process, and never exposes values to the business renderer. Python uses one typed environment-backed `Settings` object, validates secure endpoints, and maps upstream failures to redacted public errors.

**Tech Stack:** Git filter-repo, Git LFS, Gitleaks, Node.js 24, Electron `safeStorage`/IPC/preload, Python 3.13 dataclasses/unittest, Flask, requests, websocket-client, PowerShell.

---

### Task 1: Enforce The External Safety Gate

**Files:** None.

- [ ] **Step 1: Verify required command-line tools**

Run:

```powershell
gh --version
gh auth status
git filter-repo --version
git lfs version
gitleaks version
node --version
python --version
pwsh --version
```

Expected: every command exits `0`; `gh auth status` names `mili-xi`. If `gh` is missing or unauthenticated, stop and ask the owner to install/authenticate it as required by the GitHub publish workflow.

- [ ] **Step 2: Verify the owner-completed private visibility change**

Run:

```powershell
gh repo view mili-xi/xun_fei --json visibility,defaultBranchRef --jq '{visibility: .visibility, default: .defaultBranchRef.name}'
```

Expected: `visibility` is `PRIVATE`; the owner has already completed this change. This plan must not change visibility again. Stop before cloning additional history if the private repository cannot be verified.

- [ ] **Step 3: Obtain explicit credential-rotation confirmation**

Ask the owner to confirm that every iFlytek application ID, API key, API secret, Spark password, and alias credential ever shipped in `.env` or `dist/` has been revoked or rotated. Do not store credential values or screenshots in Git, the plan, logs, or the knowledge base.

Expected: an explicit confirmation in the task conversation. Without it, no rewritten refs may be pushed.

### Task 2: Freeze Remote Writes And Create A Recoverable Rewrite Workspace

**Files:**
- Existing: `docs/superpowers/specs/2026-07-12-codex-oss-readiness-design.md`
- Existing: `docs/superpowers/plans/2026-07-12-security-and-history-remediation.md`
- Existing: `docs/superpowers/plans/2026-07-12-open-source-governance-ci-release.md`
- Existing: `docs/superpowers/plans/2026-07-12-impact-application-and-publish.md`

- [ ] **Step 1: Verify and export every approved documentation commit**

Run from the current `agent/oss-readiness` checkout:

```powershell
git status --short
if ($LASTEXITCODE -ne 0 -or (git status --porcelain)) { throw 'The planning checkout must be clean.' }
$patchDir = Resolve-Path '..'
$patchDir = Join-Path $patchDir 'oss-readiness-docs-patches'
New-Item -ItemType Directory -Path $patchDir -ErrorAction Stop | Out-Null
git format-patch --output-directory $patchDir origin/dev..HEAD
if ($LASTEXITCODE -ne 0) { throw 'Unable to export approved documentation commits.' }
Get-ChildItem $patchDir -Filter '*.patch' | Select-Object Name, Length
```

Expected: the worktree is clean and the patch directory contains all approved design and plan commits. `git format-patch --output-directory` preserves patch bytes; do not use PowerShell text redirection for mbox output.

- [ ] **Step 2: Freeze repository writes and snapshot every remote ref**

Ask the owner to pause pushes, merges, tag creation, and release publication until the rewritten repository has been recloned and verified. Then run:

```powershell
git ls-remote --heads --tags origin | Sort-Object | Set-Content -Encoding ascii ..\pre-rewrite-remote-refs.txt
gh repo view mili-xi/xun_fei --json visibility,defaultBranchRef --jq '{visibility: .visibility, default: .defaultBranchRef.name}'
Get-Content ..\pre-rewrite-remote-refs.txt
$rulesets = @(gh api repos/mili-xi/xun_fei/rulesets | ConvertFrom-Json)
if ($rulesets.Count -ne 0) { throw 'Existing rulesets require a separately approved snapshot/restore procedure before rewrite.' }
$protectionResponse = gh api --include repos/mili-xi/xun_fei/branches/main/protection 2>&1
if ($LASTEXITCODE -eq 0) { throw 'Existing main protection requires a separately approved snapshot/restore procedure before rewrite.' }
if ($protectionResponse -notmatch '404') { throw 'Unable to prove that main has no branch protection.' }
```

Expected: the owner explicitly confirms the write freeze, visibility is `PRIVATE`, default branch is `dev`, the snapshot records every branch/tag SHA without reading file contents, and no pre-existing protection would be silently weakened. If protection exists, stop instead of deleting or bypassing it.

- [ ] **Step 3: Create an access-restricted recovery mirror that will never be rewritten**

Run from the workspace `work/` directory:

```powershell
$workRoot = (Resolve-Path '.').Path
$sensitiveRoot = Join-Path $workRoot 'xun_fei-sensitive-recovery'
if (Test-Path -LiteralPath $sensitiveRoot) { throw 'Sensitive recovery root already exists.' }
$syncRoots = @($env:OneDrive, $env:OneDriveCommercial, $env:OneDriveConsumer) | `
  Where-Object { $_ } | ForEach-Object { [System.IO.Path]::GetFullPath($_).TrimEnd('\') + '\' }
$candidate = [System.IO.Path]::GetFullPath($sensitiveRoot).TrimEnd('\') + '\'
if ($syncRoots | Where-Object { $candidate.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase) }) {
  throw 'Sensitive recovery root is inside a configured sync root.'
}
New-Item -ItemType Directory -Path $sensitiveRoot -ErrorAction Stop | Out-Null
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $sensitiveRoot /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
$unexpectedAcl = (Get-Acl $sensitiveRoot).Access | Where-Object {
  $_.AccessControlType -eq 'Allow' -and $_.IdentityReference.Value -ne $identity
}
if ($unexpectedAcl) { throw 'Sensitive recovery ACL grants another identity access.' }
$recoveryPath = Join-Path $sensitiveRoot 'xun_fei-recovery.git'
git clone --mirror git@github.com:mili-xi/xun_fei.git $recoveryPath
if ($LASTEXITCODE -ne 0) { throw 'Recovery mirror clone failed.' }
git -C $recoveryPath fsck --full
if ($LASTEXITCODE -ne 0) { throw 'Recovery mirror fsck failed.' }
if ((git -C $recoveryPath rev-parse --is-shallow-repository) -ne 'false') { throw 'Recovery mirror is shallow.' }
git -C $recoveryPath remote remove origin
if ($LASTEXITCODE -ne 0) { throw 'Unable to remove recovery mirror remote.' }
$mirrorRefs = @(git -C $recoveryPath show-ref --heads --tags | ForEach-Object {
  (($_ -split '\s+', 2) -join "`t")
} | Sort-Object)
$remoteRefs = @(Get-Content (Join-Path $workRoot 'pre-rewrite-remote-refs.txt'))
if (Compare-Object $remoteRefs $mirrorRefs) { throw 'Recovery mirror refs differ from the frozen remote snapshot.' }
```

Expected: `fsck` succeeds, only the current Windows identity has access, the mirror is non-shallow, has no fetch/push remote, and exactly matches the frozen heads/tags. This directory contains historical secrets and must remain local and access-restricted until final verification.

- [ ] **Step 4: Clone a separate disposable rewrite mirror**

```powershell
$workRoot = (Resolve-Path '.').Path
$recoveryPath = Join-Path $workRoot 'xun_fei-sensitive-recovery\xun_fei-recovery.git'
$rewritePath = Join-Path $workRoot 'xun_fei-history-rewrite.git'
git clone --mirror --no-hardlinks $recoveryPath $rewritePath
if ($LASTEXITCODE -ne 0) { throw 'Rewrite mirror clone failed.' }
git -C $rewritePath remote add origin git@github.com:mili-xi/xun_fei.git
git -C $rewritePath fsck --full
if ($LASTEXITCODE -ne 0) { throw 'Rewrite mirror fsck failed.' }
if ((git -C $rewritePath rev-parse --is-shallow-repository) -ne 'false') { throw 'Rewrite mirror is shallow.' }
```

Expected: the rewrite mirror is complete and independent from the untouched recovery mirror.

- [ ] **Step 5: Record pre-rewrite attribution without opening unsafe blobs**

```powershell
$rewritePath = Join-Path (Resolve-Path '.').Path 'xun_fei-history-rewrite.git'
git -C $rewritePath shortlog -sne refs/heads/dev
if ($LASTEXITCODE -ne 0) { throw 'Unable to record source attribution.' }
$commitCount = git -C $rewritePath rev-list --count refs/heads/dev
if ($LASTEXITCODE -ne 0 -or $commitCount -ne '31') { throw 'Unexpected original dev commit count.' }
$lfsBefore = @(git -C $rewritePath lfs ls-files --all --long)
if ($LASTEXITCODE -ne 0) { throw 'Unable to inventory pre-rewrite LFS pointers.' }
$lfsOids = @($lfsBefore | ForEach-Object { ($_ -split '\s+')[0] } | Sort-Object -Unique)
$lfsOids | Set-Content -Encoding ascii (Join-Path (Resolve-Path '.').Path 'pre-rewrite-lfs-oids.txt')
if ($lfsOids.Count -gt 0) {
  "reachable_lfs_oids=$($lfsOids.Count)" | Set-Content -Encoding ascii `
    (Join-Path (Resolve-Path '.').Path 'lfs-purge-required.txt')
}
```

Expected: 31 commits on the original `dev` line and the known contributor identities. Do not inspect deleted `.env` blobs.

### Task 3: Prove Source Coverage, Rewrite All Refs, And Verify The Remote

**Files:** Git object databases, Git LFS refs, GitHub Releases, and remote refs only.

- [ ] **Step 1: Prove no source-only work will be discarded**

Run inside `xun_fei-history-rewrite.git` before filtering:

```powershell
$branches = git for-each-ref --format='%(refname:short)' refs/heads
if ($LASTEXITCODE -ne 0 -or 'dev' -notin $branches) { throw 'Unable to enumerate source branches.' }
foreach ($branch in $branches) {
  if ($branch -eq 'dev') { continue }
  "=== dev...$branch ==="
  git merge-base refs/heads/dev "refs/heads/$branch" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "dev and $branch have no provable common ancestor." }
  $counts = git rev-list --left-right --count "refs/heads/dev...refs/heads/$branch"
  if ($LASTEXITCODE -ne 0) { throw "Unable to compare dev and $branch." }
  $cherry = @(git cherry refs/heads/dev "refs/heads/$branch")
  if ($LASTEXITCODE -ne 0) { throw "Unable to compare patches on $branch." }
  $uniqueCommits = @($cherry | Where-Object { $_ -like '+ *' } | ForEach-Object { ($_ -split '\s+')[1] })
  foreach ($commit in $uniqueCommits) {
    $sourcePaths = @(git show --pretty='' --name-only $commit -- . `
      ':(exclude).env*' ':(exclude)dist/**' ':(exclude)runtime/**' ':(exclude)**/.env*' `
      ':(exclude)**/*.exe' ':(exclude)**/*.msi' ':(exclude)**/*.zip' `
      ':(exclude)**/*.7z' ':(exclude)**/*.blockmap' | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0) { throw "Unable to inspect unique commit $commit." }
    if ($sourcePaths.Count -gt 0) { throw "$branch has unique source in commit $commit; integrate it before rewrite." }
  }
  $sourceDiff = @(git diff --name-only "refs/heads/dev...refs/heads/$branch" -- . `
    ':(exclude).env*' ':(exclude)dist/**' ':(exclude)runtime/**' ':(exclude)**/.env*' `
    ':(exclude)**/*.exe' ':(exclude)**/*.msi' ':(exclude)**/*.zip' `
    ':(exclude)**/*.7z' ':(exclude)**/*.blockmap' | Where-Object { $_ })
  if ($LASTEXITCODE -ne 0) { throw "Unable to compute source diff for $branch." }
  if ($sourceDiff.Count -gt 0) { throw "$branch contains source not represented by dev." }
  [pscustomobject]@{ branch = $branch; leftRightCount = $counts; uniqueExcludedOnly = $uniqueCommits.Count }
}
```

Expected: no `+` patch from `main`, `xun_fei_backed`, or `xun_fei_front` represents source absent from `dev`. If unique source exists, stop: restore it through a normal reviewed source commit on `dev`, refresh both ref snapshots and mirrors, and obtain the owner's approval of the before/after SHA table before deleting any branch.

- [ ] **Step 2: Remove unsafe paths from every local branch and tag**

```powershell
git filter-repo --force `
  --path-glob '.env*' `
  --path-glob '*/.env*' `
  --path dist/ `
  --path runtime/ `
  --path-glob '*.exe' `
  --path-glob '*.msi' `
  --path-glob '*.zip' `
  --path-glob '*.7z' `
  --path-glob '*.blockmap' `
  --invert-paths
if ($LASTEXITCODE -ne 0) { throw 'git filter-repo failed.' }
if (git remote | Select-String -Quiet '^origin$') {
  git remote set-url origin git@github.com:mili-xi/xun_fei.git
} else {
  git remote add origin git@github.com:mili-xi/xun_fei.git
}
if ($LASTEXITCODE -ne 0) { throw 'Unable to restore rewrite remote.' }
```

Expected: filter-repo rewrites every local branch and tag while preserving source, tests, commit authors, and commit dates. It deliberately removes historical `.env.example` too; Task 4 recreates a reviewed empty example so no earlier revision can hide a value.

- [ ] **Step 3: Consolidate refs only after ancestry and patch-equivalence proof**

```powershell
git merge-base --is-ancestor refs/heads/main refs/heads/dev
if ($LASTEXITCODE -ne 0) { throw 'main contains work not represented in dev.' }
git update-ref refs/heads/main refs/heads/dev
if ($LASTEXITCODE -ne 0) { throw 'Unable to align cleaned main with dev.' }
git update-ref -d refs/heads/xun_fei_backed
git update-ref -d refs/heads/xun_fei_front
git for-each-ref --format='delete %(refname)' refs/tags | git update-ref --stdin
$remainingRefs = @(git for-each-ref --format='%(refname)' refs/heads refs/tags | Sort-Object)
if ($LASTEXITCODE -ne 0 -or (Compare-Object @('refs/heads/dev', 'refs/heads/main') $remainingRefs)) {
  throw 'Cleaned local ref set is not exactly main/dev.'
}
```

Expected: only `refs/heads/main` and `refs/heads/dev` remain and both point at the cleaned source history. No tag remains before the first clean `v1.1.0` release.

- [ ] **Step 4: Prove forbidden paths, LFS pointers, and secrets are absent**

```powershell
$objects = git rev-list --objects --all
if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate rewritten objects.' }
$forbidden = $objects | Select-String -Pattern '(^|/)\.env[^/]*(/|$)|(^|/)(dist|runtime)(/|$)|\.(exe|msi|zip|7z|blockmap)$'
if ($forbidden) { $forbidden; throw 'Forbidden path remains in rewritten history.' }
$lfsFiles = git lfs ls-files --all
if ($LASTEXITCODE -ne 0) { throw 'Unable to scan rewritten LFS pointers.' }
if ($lfsFiles) { $lfsFiles; throw 'Reachable LFS pointer remains.' }
gitleaks git . --redact --report-format json --report-path ..\gitleaks-history.json --exit-code 1
if ($LASTEXITCODE -ne 0) { throw 'Rewritten-history secret scan failed.' }
```

Expected: no forbidden object path, reachable LFS pointer, or Gitleaks finding. Any finding blocks the push; remediate by path/commit identity without copying detected values into chat or logs.

- [ ] **Step 5: Produce the exact before/after ref table and obtain push authorization**

```powershell
git ls-remote --heads --tags origin | Sort-Object | Set-Content -Encoding ascii ..\current-remote-refs.txt
if ($LASTEXITCODE -ne 0) { throw 'Unable to re-read remote refs.' }
$drift = Compare-Object (Get-Content ..\pre-rewrite-remote-refs.txt) (Get-Content ..\current-remote-refs.txt)
if ($drift) { $drift; throw 'Remote refs changed during the freeze; restart the rewrite from a fresh mirror.' }
$remoteMap = @{}
foreach ($line in Get-Content ..\pre-rewrite-remote-refs.txt) {
  if ($line -notmatch '^([0-9a-f]{40})\s+(refs/(heads|tags)/.+)$') { throw 'Malformed remote-ref snapshot.' }
  $remoteMap[$Matches[2]] = $Matches[1]
}
$localMain = git rev-parse refs/heads/main
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve cleaned main.' }
$localDev = git rev-parse refs/heads/dev
if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve cleaned dev.' }
$allRefs = @($remoteMap.Keys + @('refs/heads/main', 'refs/heads/dev') | Sort-Object -Unique)
$refPlan = @($allRefs | ForEach-Object {
  [pscustomobject]@{
    ref = $_
    before = if ($remoteMap.ContainsKey($_)) { $remoteMap[$_] } else { '(absent)' }
    after = if ($_ -eq 'refs/heads/main') { $localMain } elseif ($_ -eq 'refs/heads/dev') { $localDev } else { '(delete)' }
  }
})
$refPlan | Format-Table -AutoSize
```

Expected: no drift and a complete table for every old/new head/tag. Stop here and obtain the owner's explicit authorization for this exact atomic ref plan; a changed SHA or new ref requires rebuilding the mirrors.

- [ ] **Step 6: Apply the authorized plan with per-ref leases and one atomic push**

```powershell
$remoteMap = @{}
foreach ($line in Get-Content ..\pre-rewrite-remote-refs.txt) {
  if ($line -notmatch '^([0-9a-f]{40})\s+(refs/(heads|tags)/.+)$') { throw 'Malformed remote-ref snapshot.' }
  $remoteMap[$Matches[2]] = $Matches[1]
}
$currentRefs = @(git ls-remote --heads --tags origin | Sort-Object)
if ($LASTEXITCODE -ne 0 -or (Compare-Object (Get-Content ..\pre-rewrite-remote-refs.txt) $currentRefs)) {
  throw 'Remote changed after authorization; aborting atomic push.'
}
$desiredRefs = @('refs/heads/main', 'refs/heads/dev')
$pushArgs = @('push', '--atomic', 'origin')
foreach ($ref in $remoteMap.Keys) {
  $pushArgs += "--force-with-lease=${ref}:$($remoteMap[$ref])"
  if ($ref -notin $desiredRefs) { $pushArgs += ":$ref" }
}
foreach ($ref in $desiredRefs) {
  if (-not $remoteMap.ContainsKey($ref)) { $pushArgs += "--force-with-lease=${ref}:" }
  $pushArgs += "${ref}:${ref}"
}
& git @pushArgs
if ($LASTEXITCODE -ne 0) { throw 'Atomic leased ref replacement failed; no partial rewrite is acceptable.' }
$localMain = git rev-parse refs/heads/main
$localDev = git rev-parse refs/heads/dev
$expectedRemote = @("$localDev`trefs/heads/dev", "$localMain`trefs/heads/main") | Sort-Object
$actualRemote = @(git ls-remote --heads --tags origin | Sort-Object)
if ($LASTEXITCODE -ne 0 -or (Compare-Object $expectedRemote $actualRemote)) {
  throw 'Post-push remote refs are not exactly cleaned main/dev.'
}
```

Expected: GitHub accepts one atomic transaction guarded by the frozen SHA of every old ref; the remote then contains exactly `main` and `dev`. Do not use broad `--mirror`, `--force`, or prune pushes.

- [ ] **Step 7: Revoke legacy releases and account for remote LFS storage**

```powershell
$legacy = gh api 'repos/mili-xi/xun_fei/releases?per_page=100' | ConvertFrom-Json | `
  Where-Object { $_.tag_name -in @('1.0.1', 'v1.0.1') }
foreach ($release in $legacy) {
  gh api --method DELETE "repos/mili-xi/xun_fei/releases/$($release.id)"
}
gh release list --repo mili-xi/xun_fei --limit 100
$lfsPurgeFlag = Join-Path (Resolve-Path '..').Path 'lfs-purge-required.txt'
if (Test-Path -LiteralPath $lfsPurgeFlag) {
  Write-Output 'Open a GitHub Support request to purge the recorded orphaned LFS OIDs.'
  Write-Output 'Record only the support ticket ID and purge confirmation; do not paste object contents.'
}
```

Expected: no `1.0.1` release asset remains. Reachable LFS pointers are zero. If the pre-rewrite LFS count was nonzero, GitHub Support purge confirmation is a hard gate before public visibility; save the ticket ID/confirmation outside Git, never object contents. Never re-upload old artifacts.

- [ ] **Step 8: Reclone, rescan, and restore approved docs**

```powershell
git clone git@github.com:mili-xi/xun_fei.git xun_fei-clean
if ($LASTEXITCODE -ne 0) { throw 'Clean verification clone failed.' }
git -C xun_fei-clean switch -c agent/oss-readiness origin/dev
if ($LASTEXITCODE -ne 0) { throw 'Unable to create clean implementation branch.' }
$remoteRefs = @(git -C xun_fei-clean ls-remote --heads --tags origin | Sort-Object)
$cleanMain = git -C xun_fei-clean rev-parse origin/main
$cleanDev = git -C xun_fei-clean rev-parse origin/dev
$expectedRefs = @("$cleanDev`trefs/heads/dev", "$cleanMain`trefs/heads/main") | Sort-Object
if ($LASTEXITCODE -ne 0 -or (Compare-Object $expectedRefs $remoteRefs)) { throw 'Fresh clone sees unexpected remote refs.' }
$cleanObjects = git -C xun_fei-clean rev-list --objects --all
if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate fresh-clone objects.' }
$cleanForbidden = $cleanObjects | Select-String -Pattern '(^|/)\.env[^/]*(/|$)|(^|/)(dist|runtime)(/|$)|\.(exe|msi|zip|7z|blockmap)$'
if ($cleanForbidden) { $cleanForbidden; throw 'Fresh clone contains a forbidden historical path.' }
$cleanLfs = git -C xun_fei-clean lfs ls-files --all
if ($LASTEXITCODE -ne 0) { throw 'Unable to scan fresh-clone LFS pointers.' }
if ($cleanLfs) { throw 'Fresh clone still contains reachable LFS pointers.' }
gitleaks git xun_fei-clean --redact --exit-code 1
if ($LASTEXITCODE -ne 0) { throw 'Fresh-clone secret scan failed.' }
$patchPaths = @(Get-ChildItem ..\oss-readiness-docs-patches -Filter '*.patch' | `
  Sort-Object Name | Select-Object -ExpandProperty FullName)
if ($patchPaths.Count -eq 0) { throw 'Approved documentation patches are missing.' }
git -C xun_fei-clean am @patchPaths
if ($LASTEXITCODE -ne 0) { throw 'Unable to restore approved documentation commits.' }
```

Expected: the fresh clone has no forbidden path or secret finding, and all approved design/plan commits apply. Retain the restricted recovery mirror until the public-release verification plan explicitly authorizes deletion.

### Task 4: Introduce A Typed Backend Configuration Boundary

**Files:**
- Create: `后端/backend_errors.py`
- Modify: `后端/config.py`
- Modify: `tests/test_backend_config_imports.py`
- Modify: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Replace `.env` loading tests with failing pure-environment tests**

Add tests that call `load_settings(mapping)` directly:

```python
def test_settings_ignore_repository_env_files(self):
    settings = config.load_settings({"IFLYTEK_APP_ID": "test-app"})
    self.assertEqual(settings.iflytek_app_id, "test-app")
    self.assertFalse(settings.spark_configured)

def test_settings_reject_insecure_service_urls(self):
    with self.assertRaisesRegex(config.ConfigurationError, "OCR_URL"):
        config.load_settings({"OCR_URL": "http://insecure.invalid"})

def test_settings_aliases_prefer_xfyun_values(self):
    settings = config.load_settings({
        "IFLYTEK_APP_ID": "canonical",
        "XFYUN_APPID": "voice-alias",
    })
    self.assertEqual(settings.xfyun_app_id, "voice-alias")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_backend_config_imports.py" -v
```

Expected: failure because `load_settings`, `Settings`, or `ConfigurationError` does not exist and current code loads `.env` at import time.

- [ ] **Step 3: Define configuration errors once and implement frozen typed settings**

Define `ConfigurationError` and `MissingConfigurationError` only in `后端/backend_errors.py`; `config.py` imports them. Implement a frozen `Settings` dataclass and `load_settings(environ=None)` in `后端/config.py`. The dataclass stores the four canonical secret values after resolving the documented `XFYUN_*` aliases, plus HTTP/WSS endpoints, integer timeouts, model, port, ffmpeg path, and capability properties. It must copy the input mapping, reject non-HTTPS/WSS service URLs, parse bounded positive integers, expose `missing(*names)` and `require(*names)`, and never read files or mutate `os.environ`.

Keep read-only module constants sourced from one `SETTINGS = load_settings()` for one compatibility release, but all modified application code must use `SETTINGS` or an injected `Settings` instance.

- [ ] **Step 4: Remove dotenv and align the public example**

Remove `python-dotenv` from `requirements.txt`. Recreate `.env.example` from reviewed names only, keep every secret field empty, and document it as a reference for shell environment names rather than a file loaded by the application. Add `SPARK_WS_URL=wss://spark-api.xf-yun.com/v3.1/chat` so HTTP and WebSocket endpoints are unambiguous.

- [ ] **Step 5: Run focused and full Python tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_backend_config_imports.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all existing 63 tests plus the new configuration tests pass.

- [ ] **Step 6: Commit the configuration boundary**

```powershell
git add -- .env.example requirements.txt 后端/backend_errors.py 后端/config.py tests/test_backend_config_imports.py
git commit -m "security: centralize backend configuration"
```

### Task 5: Redact Backend Errors And Enforce TLS

**Files:**
- Modify: `后端/backend_errors.py`
- Create: `tests/test_backend_security.py`
- Modify: `后端/llm_client.py`
- Modify: `后端/ocr_client.py`
- Modify: `后端/voice_chat_flow.py`
- Modify: `后端/app.py`
- Delete: `后端/Ifasr_new.py`
- Delete: `后端/trans.py`
- Delete: `后端/demo.pcm`

- [ ] **Step 1: Write failing redaction and TLS tests**

Use a synthetic sentinel that is not a real credential:

```python
TEST_SECRET = "unit-test-secret-sentinel"

def test_upstream_error_does_not_expose_response_body(self):
    response = Mock(status_code=401, text=f"opaque {TEST_SECRET}")
    response.json.side_effect = ValueError("not json")
    with patch.object(llm_client.requests, "post", return_value=response) as post:
        with self.assertRaises(backend_errors.UpstreamServiceError) as caught:
            client.chat([{"role": "user", "content": "ping"}])
    self.assertNotIn(TEST_SECRET, str(caught.exception))
    self.assertIs(post.call_args.kwargs["verify"], True)
```

Add equivalent OCR, WebSocket `ssl.CERT_REQUIRED`/`check_hostname`, Flask response, and captured-log tests. Public errors may include service name, safe status code, correlation ID, and missing variable names, but not response bodies, signed URLs, ffmpeg stderr, or sentinel values.

- [ ] **Step 2: Run the security test and verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_backend_security.py" -v
```

Expected: failures showing raw upstream text or missing explicit TLS options.

- [ ] **Step 3: Implement safe exception types and client injection**

Add `UpstreamServiceError` to `backend_errors.py`; do not redefine either configuration error. Modify LLM/OCR/voice clients to receive `Settings`, validate required names before calls, use `verify=True` for requests, and route all WebSocket calls through one helper using:

```python
sslopt={"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True}
```

Convert upstream failures to fixed public messages while logging only exception type, service, safe status code, and a generated correlation ID.

- [ ] **Step 4: Harden Flask responses and health status**

Remove `env_file_present` from `/api/health`. Replace returned `generation_error` and raw exception text with fixed error codes/messages. Keep capability booleans only. Add optional `XUNFEI_LAUNCH_TOKEN` validation for `/api/health` when Electron supplies a token.

- [ ] **Step 5: Remove unused risky samples**

Delete the unused legacy transcription client, downloader note, and sample PCM. Verify no imports reference them:

```powershell
rg -n "Ifasr_new|import trans|demo\.pcm" 后端 tests electron
```

Expected: no output.

- [ ] **Step 6: Run tests and security grep**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
rg -n -i "verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False" 后端 tests
```

Expected: all tests pass; grep returns no unsafe project match.

- [ ] **Step 7: Commit backend hardening**

```powershell
git add -- 后端 tests
git commit -m "security: redact backend failures and enforce TLS"
```

### Task 6: Define The Electron Credential Semantics

**Files:**
- Create: `electron/credentialConfig.js`
- Create: `electron/credentialConfig.test.js`

- [ ] **Step 1: Write failing credential-policy tests**

Test the four canonical fields, environment-over-store precedence, all-or-none OCR credentials, independent Spark password, unknown-field rejection, no input mutation, and status summaries that contain booleans/source names but no values. Use synthetic values only.

```javascript
const resolved = resolveCredentialEnvironment(
  { IFLYTEK_APP_ID: 'env-app' },
  { IFLYTEK_APP_ID: 'stored-app', IFLYTEK_API_KEY: 'stored-key', IFLYTEK_API_SECRET: 'stored-secret' },
);
assert.equal(resolved.IFLYTEK_APP_ID, 'env-app');
assert.equal(resolved.IFLYTEK_API_KEY, 'stored-key');
assert.doesNotMatch(JSON.stringify(summarizeCredentialStatus(resolved)), /stored-key/);
```

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/credentialConfig.test.js
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the pure policy module**

Export `CREDENTIAL_FIELDS`, `validateCredentialPatch`, `resolveCredentialEnvironment`, `summarizeCredentialStatus`, and `getSensitiveValues`. Treat blank strings as absent, reject unknown keys, copy all inputs before normalization, require the OCR trio together, and return new frozen objects. `getSensitiveValues` returns only non-empty values for redaction.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
node --test electron/credentialConfig.test.js
git add -- electron/credentialConfig.js electron/credentialConfig.test.js
git commit -m "security: define desktop credential policy"
```

### Task 7: Encrypt Credentials With Electron SafeStorage

**Files:**
- Create: `electron/credentialStore.js`
- Create: `electron/credentialStore.test.js`

- [ ] **Step 1: Write failing encrypted-store tests**

Cover encrypted round trip, no plaintext sentinel on disk, atomic overwrite, clear, corrupt ciphertext, unsupported schema version, and no plaintext fallback when `safeStorage.isEncryptionAvailable()` is false.

```javascript
const store = createCredentialStore({ safeStorage, userDataPath, fsImpl });
await store.save({ IFLYTEK_APP_ID: 'test-app', IFLYTEK_API_KEY: 'test-key', IFLYTEK_API_SECRET: 'test-secret' });
assert.equal((await store.load()).IFLYTEK_APP_ID, 'test-app');
assert.doesNotMatch(fs.readFileSync(store.filePath, 'utf8'), /test-secret/);
```

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/credentialStore.test.js
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the encrypted store**

`createCredentialStore({ safeStorage, userDataPath, fsImpl })` exposes `filePath`, `load`, `save`, and `clear`. Serialize `{schemaVersion: 1, credentials}` once, encrypt the whole JSON with `safeStorage.encryptString()`, store only base64 ciphertext, write a unique same-directory temporary file with restrictive user permissions, then atomically rename. Throw typed `CredentialEncryptionUnavailableError` or `CredentialStoreCorruptError`; never delete corrupt data silently.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
node --test electron/credentialStore.test.js
git add -- electron/credentialStore.js electron/credentialStore.test.js
git commit -m "security: encrypt credentials with safeStorage"
```

### Task 8: Persist Only Non-Sensitive Onboarding Preferences

**Files:**
- Create: `electron/preferencesStore.js`
- Create: `electron/preferencesStore.test.js`

- [ ] **Step 1: Write the failing preference contract**

Assert the store accepts only `{onboardingComplete: boolean}`, rejects credential-shaped/unknown keys, defaults to `false`, survives a round trip, and recovers from a missing file without creating one.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/preferencesStore.test.js
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement, verify, and commit**

```powershell
node --test electron/preferencesStore.test.js
git add -- electron/preferencesStore.js electron/preferencesStore.test.js
git commit -m "feat: persist non-sensitive onboarding state"
```

Expected: the implementation stores only the versioned boolean preference and the focused test passes.

### Task 9: Authenticate Backend Health And Redact Streaming Logs

**Files:**
- Create: `electron/logRedactor.js`
- Create: `electron/logRedactor.test.js`
- Modify: `electron/backendLauncher.js`
- Modify: `electron/backendLauncher.test.js`
- Modify: `后端/app.py`
- Modify: `tests/test_flask_app_contract.py`

- [ ] **Step 1: Write failing redaction and launch-token tests**

Cover full-value, multiple-value, cross-chunk, and final-flush redaction. Extend launcher/Flask tests for a random `XUNFEI_LAUNCH_TOKEN`, the `X-Xunfei-Launch-Token` request header, 401 on mismatch, valid JSON health, non-200 responses, timeout, and child early exit.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/logRedactor.test.js electron/backendLauncher.test.js
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_flask_app_contract.py" -v
```

Expected: missing redactor and launch-token assertion failures.

- [ ] **Step 3: Implement the streaming redactor**

`createStreamingRedactor(values)` exposes `write(chunk)` and `flush()`. Normalize non-empty values by descending length, retain a suffix of `maxSecretLength - 1` characters between writes, replace complete matches with `[REDACTED]`, and never return buffered raw content from errors.

- [ ] **Step 4: Authenticate the desktop health channel**

Generate a new random token for each child process, inject it only into the child environment, and send it only in the local health header. Flask requires the header only when the environment token exists. `waitForHealth` must terminate immediately on child `error`/`exit`, require status 200 and the expected JSON schema, and never include raw response text in its error.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
node --test electron/logRedactor.test.js electron/backendLauncher.test.js
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_flask_app_contract.py" -v
git add -- electron/logRedactor.js electron/logRedactor.test.js electron/backendLauncher.js electron/backendLauncher.test.js 后端/app.py tests/test_flask_app_contract.py
git commit -m "security: authenticate health checks and redact logs"
```

### Task 10: Add The First-Run Settings And Application Controller

**Files:**
- Create: `electron/settingsController.js`
- Create: `electron/settingsController.test.js`
- Create: `electron/settings-preload.js`
- Create: `electron/settings/index.html`
- Create: `electron/settings/renderer.js`
- Create: `electron/settings/styles.css`
- Create: `electron/appController.js`
- Create: `electron/appController.test.js`
- Modify: `electron/main.js`

- [ ] **Step 1: Write failing controller tests**

Cover IPC status without values, save/clear/local-mode actions, environment precedence, first-run settings before backend spawn, controlled restart after saving, DPAPI failure, and single-instance behavior.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/settingsController.test.js electron/appController.test.js
```

Expected: module-not-found failures.

- [ ] **Step 3: Implement the least-privilege settings surface**

Use a dedicated local window with `contextIsolation: true`, `nodeIntegration: false`, sandboxing, a strict CSP, and a preload exposing only `getStatus`, `save`, `clear`, and `continueLocal`. Never return stored values. Reject navigation/new windows and partial OCR credentials. Saving or clearing triggers a controlled backend restart through an injected callback.

- [ ] **Step 4: Extract and wire the application controller**

Move ready, single-instance, first-run, backend start/stop/restart, and window lifecycle out of `main.js` into injectable `appController.js`. The controller resolves environment-over-store credentials, passes them only to `buildBackendLaunchConfig`, pipes stdout/stderr through the streaming redactor, and waits for explicit save or local-only continuation before first spawn.

- [ ] **Step 5: Run integration tests and commit**

```powershell
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
git add -- electron
git commit -m "feat: add secure first-run credential settings"
```

Expected: all Electron/Python tests pass and no synthetic secret appears in output.

### Task 11: Enforce A Source-Only Packaging Boundary

**Files:**
- Create: `electron/packagingPolicy.js`
- Create: `electron/packagingPolicy.test.js`
- Create: `electron/packageConfig.test.js`
- Modify: `electron/backendLauncher.js`
- Modify: `electron/backendLauncher.test.js`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `.gitignore`
- Modify: `.gitattributes`

- [ ] **Step 1: Write failing package-policy tests**

Assert that root/nested `.env` files are fatal, `.env.example` is allowed, synthetic secret values are detected without being echoed, package metadata contains no `.env` resource, settings files are included, tests are excluded, and build targets include `nsis` and `zip`.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/packagingPolicy.test.js electron/packageConfig.test.js electron/backendLauncher.test.js
```

Expected: failures because current `package.json` packages `.env` and the policy module does not exist.

- [ ] **Step 3: Implement package preflight and metadata**

Make tracked or staged `.env`, `dist/`, `runtime/`, executable, or archive inputs fail preflight. Update `.gitignore` for `.env`, `.env.*` with an explicit `!.env.example`, `dist/`, `runtime/`, installers, archives, logs, coverage, and local build staging. Remove obsolete LFS rules from `.gitattributes`.

Update `package.json` to version `1.1.0`, pin `electron` to `43.1.0` and `electron-builder` to `26.15.3`, remove the `.env` resource, include settings assets, and add scripts for tests/preflight/artifact scanning. Keep `private: true` to prevent accidental npm publication. Leave the current license field unchanged until the rights audit in the governance plan authorizes Apache-2.0.

- [ ] **Step 4: Update the lockfile without creating a tag**

```powershell
npm install --package-lock-only
```

Expected: `package-lock.json` matches package version and exact dependency constraints.

- [ ] **Step 5: Run package and full baseline tests**

```powershell
npm run verify:packaging-context
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: all commands pass with no tracked forbidden build input.

- [ ] **Step 6: Commit the source-only boundary**

```powershell
git add -- .gitignore .gitattributes package.json package-lock.json electron
git commit -m "build: enforce source-only packaging inputs"
```

### Task 12: Review And Verify The Security Phase

**Files:** All files changed in Tasks 4-11.

- [ ] **Step 1: Run complete local verification**

```powershell
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run verify:packaging-context
gitleaks dir . --redact --exit-code 1
git diff origin/dev...HEAD --check
```

Expected: every command exits `0`; baseline minimum is 8 existing Node tests and 63 existing Python tests plus all newly added security tests.

- [ ] **Step 2: Request specification compliance review**

Provide the approved design, this plan, base SHA, and head SHA to a fresh reviewer. Fix every missing requirement or unapproved extra, then request re-review until approved.

- [ ] **Step 3: Request code quality and security review**

Review typed configuration, IPC exposure, DPAPI failure behavior, log redaction, child environment, TLS enforcement, package scanning, and tests. Fix all Critical and Important findings and rerun Step 1.

- [ ] **Step 4: Record the clean phase boundary**

```powershell
git status -sb
git log --oneline --decorate -8
```

Expected: clean worktree on `agent/oss-readiness` with reviewed, focused commits. Continue with `2026-07-12-open-source-governance-ci-release.md`.
