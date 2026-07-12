# Impact, Codex Application, And Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the reviewed `v1.1.0` project safely, record only externally verifiable impact, and produce a complete fact-based Codex for Open Source application without exposing personal account data.

**Architecture:** Repository evidence is generated from structured GitHub API responses and kept distinct from opt-in adoption reports; raw asset-download events are never presented as users or monthly downloads. Legitimate review branches flow through `agent/oss-readiness -> dev -> main`, a manual cloud preflight exercises the exact release build without publication, and only an immutable tag on `main` may create a private release. The repository becomes public only after history, Actions logs, release artifacts, security settings, and profile visibility are independently verified.

**Tech Stack:** Node.js 24 native `fetch`, Node test runner, GitHub REST API, GitHub CLI, GitHub Actions, Gitleaks, PowerShell, Markdown, GitHub issue forms, GitHub Releases.

---

### Task 1: Enforce The Inherited Safety And Authority Gates

**Files:** None.

- [ ] **Step 1: Enter the execution worktree with required skills**

Before implementation, use `superpowers:using-git-worktrees`. Use `superpowers:test-driven-development` for every behavior change, and use `github:yeet` only when Task 5 authorizes commit/push/PR publication.

Expected: implementation occurs in the cleaned `agent/oss-readiness` worktree produced by the security plan, not in the pre-rewrite checkout.

- [ ] **Step 2: Verify GitHub CLI and owner authority**

```powershell
gh --version
gh auth status
gh api user --jq .login
gh repo view mili-xi/xun_fei --json visibility,defaultBranchRef,viewerPermission `
  --jq '{visibility: .visibility, default: .defaultBranchRef.name, permission: .viewerPermission}'
```

Expected: every command exits `0`, login is `mili-xi`, permission is `ADMIN`, and visibility is `PRIVATE`. The current machine did not have a usable `gh` during planning; if it is still missing or unauthenticated, stop and ask the owner to install/authenticate it. Do not substitute unauthenticated write automation.

- [ ] **Step 3: Reconfirm credential rotation and clean remote history**

Obtain an explicit owner confirmation that every historical iFlyTek credential and alias has been revoked or rotated. Then run:

```powershell
$heads = gh api repos/mili-xi/xun_fei/git/matching-refs/heads/ --paginate | ConvertFrom-Json
$headNames = @($heads | ForEach-Object { $_.ref -replace '^refs/heads/', '' } | Sort-Object)
if (Compare-Object @('dev', 'main') $headNames) { throw 'Unexpected remote branch set.' }
$tags = gh api repos/mili-xi/xun_fei/git/matching-refs/tags/ --paginate | ConvertFrom-Json
if (@($tags).Count -ne 0) { throw 'No tag may predate the clean v1.1.0 release.' }
gitleaks git . --redact --exit-code 1
```

Expected: only `main` and `dev`, no tags, and no Gitleaks finding. Confirmation records credential names/status only, never values.

- [ ] **Step 4: Verify predecessor phase evidence**

```powershell
npm run verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run build:release
gh release list --repo mili-xi/xun_fei --limit 100
```

Expected: all local verification passes and no legacy `1.0.1` release exists. If GitHub Secret Scanning returns 403/404 while private, do not treat it as zero alerts; the owner must inspect the repository Security page before any visibility change.

### Task 2: Define Honest Impact Evidence And Voluntary Adoption Reporting

**Files:**
- Create: `docs/impact.md`
- Create: `.github/ISSUE_TEMPLATE/adoption_report.yml`
- Create: `electron/impactContract.test.js`
- Modify: `.github/ISSUE_TEMPLATE/config.yml`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Write the failing impact contract**

Use `yaml.parse()` in `electron/impactContract.test.js`. Assert `impact.md` contains sections for evidence policy, GitHub repository/release metrics, opt-in adoption reports, downstream references, maintenance evidence, and case studies. Assert exactly one generated block delimited by:

```markdown
<!-- release-metrics:start -->
<!-- release-metrics:end -->
```

Parse the issue form and assert it requests version, installation method, real use case, an optional public reference URL, and optional permission to quote/link the report. Require a confirmation that the public issue contains no credentials, resumes, recordings, email addresses, or other personal data. Reject file-upload fields and any required permission-to-publicize checkbox.

- [ ] **Step 2: Verify RED**

```powershell
node --test electron/impactContract.test.js
```

Expected: failure because the impact document and adoption form do not exist.

- [ ] **Step 3: Write the evidence policy and empty-state record**

`docs/impact.md` must state all of the following:

- every item has a public source URL and UTC capture date;
- GitHub asset `download_count` values are cumulative events, not unique users, installations, external adopters, or monthly downloads;
- maintainer smoke-test/self-downloads remain inside GitHub's raw counter and are never classified as external adoption;
- external adoption requires an unsolicited public issue, downstream link, or published case study;
- an adoption issue is linked or quoted from `impact.md` only when its optional citation permission is checked; otherwise the report remains public on GitHub but is not curated into project evidence;
- no demo/self-authored adoption issue will be created;
- an empty category says `None recorded` rather than implying missing data is positive evidence.

The initial generated block says the first public snapshot is not yet available because the repository remains private for remediation. This is a factual state, not unfinished content.

- [ ] **Step 4: Add the opt-in issue form and public links**

Create `adoption_report.yml` with a public-data warning at the top. Make the usage-context and version fields required; keep public URL and citation permission optional. Link the form and `docs/impact.md` from both READMEs and the issue-template chooser. Do not create an adoption issue during implementation.

- [ ] **Step 5: Verify GREEN and commit**

```powershell
node --test electron/impactContract.test.js
git add -- docs/impact.md .github/ISSUE_TEMPLATE README.md README.zh-CN.md electron/impactContract.test.js
git commit -m "docs: define verifiable project impact evidence"
```

### Task 3: Collect Release Metrics From Structured GitHub Responses

**Files:**
- Create: `scripts/releaseMetrics.js`
- Create: `scripts/releaseMetrics.test.js`
- Create: `scripts/refreshReleaseMetrics.js`
- Modify: `package.json`
- Modify: `package-lock.json`

- [ ] **Step 1: Write failing pure transformation tests**

Export `collectRepositoryEvidence`, `normalizeEvidence`, and `renderMetricsMarkdown` from `releaseMetrics.js`. With injected fake `fetch`, test repository counts, paginated releases, exclusion of drafts/unpublished releases, stable tag/asset sorting, non-negative integer validation, zero releases, per-asset counts/digests/URLs, and separate binary/supporting-asset totals. Assert `monthlyDownloads` remains `null` because one cumulative snapshot cannot prove a monthly count.

```javascript
const evidence = normalizeEvidence({
  repository: { full_name: 'mili-xi/xun_fei', stargazers_count: 0, forks_count: 0, open_issues_count: 0 },
  releases: [{ tag_name: 'v1.1.0', draft: false, published_at: '2026-07-12T00:00:00Z', assets: [
    { name: 'app.zip', download_count: 2, browser_download_url: 'https://github.com/example/app.zip', digest: 'sha256:test' },
  ] }],
  capturedAt: '2026-07-12T01:00:00Z',
});
assert.equal(evidence.binaryAssetDownloadEvents, 2);
assert.equal(evidence.monthlyDownloads, null);
```

- [ ] **Step 2: Verify RED**

```powershell
node --test scripts/releaseMetrics.test.js
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement the GitHub evidence collector**

Use Node 24 native `fetch` against `https://api.github.com/repos/{owner}/{repo}` and paginated `/releases?per_page=100&page=N`. Send `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, and a descriptive `User-Agent`. Use `GITHUB_TOKEN` only when present, never accept it as a CLI argument, and never include request headers/body in an error. Validate response status/schema before normalization.

Only published non-draft releases contribute. Preserve each asset's `name`, `browser_download_url`, `download_count`, and `digest`; GitHub-generated source archives are not release assets and are not counted. Sum `.exe` and `.zip` assets as binary download events while reporting SBOM/checksum downloads separately.

- [ ] **Step 4: Implement fail-closed Markdown refresh**

`refreshReleaseMetrics.js` accepts `--repository mili-xi/xun_fei --document docs/impact.md`. It fetches and renders completely in memory, requires exactly one start/end marker in the correct order, writes a same-directory temporary file, and atomically renames only after all validation succeeds. Tests use a temporary document to prove API failure, invalid JSON, schema failure, missing/duplicate markers, and negative counts leave the original bytes unchanged.

- [ ] **Step 5: Wire the command and verify GREEN**

Add:

```json
{
  "scripts": {
    "metrics:release": "node scripts/refreshReleaseMetrics.js --repository mili-xi/xun_fei --document docs/impact.md"
  }
}
```

Run and commit without contacting GitHub yet:

```powershell
node --test scripts/releaseMetrics.test.js
git add -- scripts package.json package-lock.json
git commit -m "feat: collect verifiable GitHub release metrics"
```

### Task 4: Create Bilingual, Length-Checked Codex Application Material

**Files:**
- Create: `docs/CODEX_FOR_OSS_APPLICATION.md`
- Modify: `tests/test_repository_contract.py`

- [ ] **Step 1: Write a failing application-document contract**

Extract six answer blocks using stable HTML comments for Chinese/English `qualification`, `api-credits`, and `additional-notes`. Assert each normalized answer is 1-500 Unicode code points, contains no template marker, private email, organization ID, fabricated adoption phrase, or unsupported affiliation claim. Assert the document links the repository, `docs/impact.md`, releases, CI, security policy, contribution history, issues, and pull requests.

- [ ] **Step 2: Verify RED**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
```

Expected: failure because the application document does not exist.

- [ ] **Step 3: Add the complete Chinese answers**

Use these reviewed answers inside the tested blocks:

**Qualification (210 characters during planning):**

```text
我是该仓库的主要维护者，负责绝大多数源码提交以及安全修复、PR 评审、Issue 分类和版本发布。项目为中文用户提供本地优先的 Windows 开源求职助手，涵盖简历分析、职位匹配、模拟面试和语音交互，并提供可审计的 BYOK 凭据隔离与可复现发布方案。申请依据是其对中文本地 AI 求职工具生态的可复用价值；当前真实 stars、Release 资产下载和采用报告见 impact 文档，维护者测试下载不计作外部采用。
```

**API credits use (154 characters during planning):**

```text
额度只用于维护 mili-xi/xun_fei：辅助审查 PR、分类 Issue、生成回归测试、分析安全与依赖风险、维护 CI 和发布自动化、生成变更日志及发布说明。不会用于托管或共享讯飞凭据，不会处理未经授权的真实简历或录音，也不会转售额度。所有自动生成的变更必须通过测试、秘密扫描和维护者人工审查后合并。
```

**Additional notes (156 characters during planning):**

```text
这是独立社区项目，与讯飞或 OpenAI 无隶属或背书关系。历史内嵌凭据已轮换并从所有可达 Git、LFS 和 Release 历史清除；v1.1.0 使用用户自带凭据且发布物经递归扫描。项目只公开可核验的 stars、累计资产下载、采用 Issue 和下游链接，不购买或制造指标，也不把内部测试描述为外部采用。
```

- [ ] **Step 4: Add complete English reference answers**

Use the corresponding reviewed English answers, also under 500 characters:

```text
I am the primary maintainer, responsible for most source commits, security remediation, PR review, issue triage, and releases. This local-first Windows assistant serves Chinese-speaking job seekers with resume analysis, job matching, interview practice, voice interaction, auditable BYOK isolation, and reproducible releases. Current stars, release-asset downloads, and adoption reports are linked in impact.md; maintainer test downloads are not treated as external adoption.
```

```text
Credits will be used only to maintain mili-xi/xun_fei: reviewing PRs, triaging issues, generating regression tests, analyzing security and dependency risks, maintaining CI/release automation, and preparing changelogs and release notes. They will not host shared iFlytek credentials, process unauthorized real resumes or recordings, or be resold. Generated changes must pass tests, secret scanning, and maintainer review.
```

```text
This is an independent community project with no affiliation or endorsement from iFlytek or OpenAI. Historical embedded credentials were rotated and removed from all reachable Git, LFS, and Release history; v1.1.0 uses user-owned credentials and recursively scanned artifacts. The project reports only verifiable stars, cumulative asset downloads, public adoption issues, and downstream links, without manufactured metrics.
```

- [ ] **Step 5: Document private form fields and readiness state**

Link the current official form at `https://openai.com/zh-Hans-CN/form/codex-for-oss/`. Record public values `mili-xi`, repository URL, and role `Primary maintainer`; explain that Codex Security and project API credits are independent choices. If the owner selects API credits, the form requires an OpenAI Organization ID and the tested credits-use answer; otherwise do not provide that private identifier unnecessarily. Legal first/last name, ChatGPT account email, and any Organization ID are entered privately and never committed. Set submission state to `Blocked until the private release and public-verification gates pass`; this is a real state, not a missing field. State that acceptance is not guaranteed.

- [ ] **Step 6: Verify and commit**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_repository_contract.py" -v
git add -- docs/CODEX_FOR_OSS_APPLICATION.md tests/test_repository_contract.py
git commit -m "docs: draft factual Codex for OSS application"
```

### Task 5: Publish The Review Branch And Merge The Reviewed Work To Dev

**Files:** No new source files; GitHub branch, workflow run, and pull request state change.

- [ ] **Step 1: Run final local reviews before any push**

Use `superpowers:requesting-code-review` with the approved design and all three plans. Complete specification review first, then code-quality/security review; fix Critical/Important findings and rerun:

```powershell
npm run verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
gitleaks dir . --redact --exit-code 1
git diff origin/dev...HEAD --check
git status --short
```

Expected: all commands pass and worktree is clean.

- [ ] **Step 2: Use the GitHub publish workflow to open a draft PR**

Invoke `github:yeet`; confirm its scope is exactly `agent/oss-readiness`, commit all reviewed local work intentionally, push that branch, and open a draft PR to `dev`. Equivalent final commands are:

```powershell
git push --set-upstream origin agent/oss-readiness
$prBody = Join-Path $env:TEMP 'xunfei-oss-readiness-pr.md'
@'
## Summary
- removes credential-bearing history and packaged binaries
- adds user-owned encrypted credential configuration
- adds Apache-2.0 governance, CI, security scanning, and verified releases
- adds factual impact and Codex for Open Source application material

## Verification
- [x] Python and Electron tests
- [x] Gitleaks history and worktree scans
- [x] package preflight and recursive release-artifact scan
- [x] specification and code-quality reviews
'@ | Set-Content -Encoding utf8 $prBody
$prUrl = gh pr create --draft --base dev --head agent/oss-readiness `
  --title "security: prepare xun_fei for open-source release" `
  --body-file $prBody
Remove-Item -LiteralPath $prBody
```

Expected: one legitimate implementation PR; do not create filler issues, comments, reviews, or reactions.

- [ ] **Step 3: Complete the real PR review and checks**

Mark the PR ready only after both review stages and all pull-request workflows pass. Use `gh pr checks --watch`; inspect unresolved threads and fix them. A maintainer self-merge or agent-assisted review is legitimate maintenance work but must never be described as independent community review. The new manual release workflow is not dispatched here because GitHub requires a dispatchable workflow definition on the default branch first.

- [ ] **Step 4: Merge without bypassing checks or changing the reviewed head**

```powershell
$pr = gh pr view $prUrl --json number,headRefOid | ConvertFrom-Json
gh pr ready $pr.number
gh pr checks $pr.number --watch
gh pr merge $pr.number --merge --delete-branch --match-head-commit $pr.headRefOid
```

Expected: the reviewed commit graph and authorship are preserved on `dev`; no `--admin` bypass or squash is used.

### Task 6: Promote Dev Through A Release PR And Verify Main In The Cloud

**Files:** GitHub pull request, default branch, and workflow run state only.

- [ ] **Step 1: Run the first non-publishing cloud preflight from default dev**

After Task 5 merges the workflow definition into the current default branch, run:

```powershell
$startedAt = (Get-Date).ToUniversalTime()
gh workflow run release-windows.yml --ref dev
$deadline = (Get-Date).AddMinutes(2)
do {
  $devRun = gh run list --workflow release-windows.yml --event workflow_dispatch `
    --branch dev --limit 10 --json databaseId,createdAt,status,conclusion | ConvertFrom-Json | `
    Where-Object { [datetime]$_.createdAt -ge $startedAt } | `
    Sort-Object { [datetime]$_.createdAt } -Descending | Select-Object -First 1
  if (-not $devRun) { Start-Sleep -Seconds 2 }
} until ($devRun -or (Get-Date) -ge $deadline)
if (-not $devRun) { throw 'Timed out waiting for the dev preflight run.' }
gh run watch $devRun.databaseId --exit-status
gh run download $devRun.databaseId --dir ..\release-preflight-dev
pwsh -File scripts/verify-release-artifacts.ps1 -Dist ..\release-preflight-dev
```

Expected: build, tests, SBOMs, checksums, and recursive scans pass, and no GitHub Release exists because manual dispatch can never run the publish job.

- [ ] **Step 2: Open the release PR from dev to main**

```powershell
git fetch origin --prune
$releasePrUrl = gh pr create --base main --head dev --title "release: xun_fei v1.1.0" `
  --body "Promotes the reviewed open-source security, governance, CI, release, and application-readiness work to the stable branch."
```

Expected: the diff contains only the reviewed work already merged into `dev`.

- [ ] **Step 3: Require all review and CI gates**

```powershell
$releasePr = gh pr view $releasePrUrl --json number,headRefOid | ConvertFrom-Json
gh pr checks $releasePr.number --watch
```

Resolve every review thread and confirm CI, CodeQL, dependency review, and secret scan succeed. Do not merge if a required check is missing, skipped unexpectedly, or neutral because of a configuration error.

- [ ] **Step 4: Merge the exact reviewed head and make main the public default**

```powershell
gh pr merge $releasePr.number --merge --match-head-commit $releasePr.headRefOid
gh repo edit mili-xi/xun_fei --default-branch main
git fetch origin main dev
$mainSha = git rev-parse origin/main
```

Expected: default branch is `main`, `mainSha` is the release PR merge commit, and `dev` retains the integration history.

- [ ] **Step 5: Run the final non-publishing preflight on main**

```powershell
$startedAt = (Get-Date).ToUniversalTime()
gh workflow run release-windows.yml --ref main
$deadline = (Get-Date).AddMinutes(2)
do {
  $mainRun = gh run list --workflow release-windows.yml --event workflow_dispatch `
    --branch main --limit 10 --json databaseId,createdAt,status,conclusion | ConvertFrom-Json | `
    Where-Object { [datetime]$_.createdAt -ge $startedAt } | `
    Sort-Object { [datetime]$_.createdAt } -Descending | Select-Object -First 1
  if (-not $mainRun) { Start-Sleep -Seconds 2 }
} until ($mainRun -or (Get-Date) -ge $deadline)
if (-not $mainRun) { throw 'Timed out waiting for the main preflight run.' }
gh run watch $mainRun.databaseId --exit-status
gh run download $mainRun.databaseId --dir ..\release-preflight-main
pwsh -File scripts/verify-release-artifacts.ps1 -Dist ..\release-preflight-main
```

Expected: the exact `main` source produces a clean release candidate without creating a release.

- [ ] **Step 6: Obtain the tag authorization**

Show the owner the `mainSha`, successful workflow URL, artifact names, checksums, SBOMs, and scan result. Obtain explicit confirmation to create `v1.1.0`, then persist exactly that approved SHA outside the repository:

```powershell
$approvedShaFile = Resolve-Path '..'
$approvedShaFile = Join-Path $approvedShaFile 'approved-v1.1.0-sha.txt'
$mainSha | Set-Content -Encoding ascii $approvedShaFile
```

No tag is created without this last release-specific confirmation.

### Task 7: Create The Immutable Tag And Verify The Private GitHub Release

**Files:** Git tag, GitHub Actions run, and GitHub Release state only.

- [ ] **Step 1: Prove the tag/release names are unused**

```powershell
git ls-remote --tags origin refs/tags/v1.1.0
gh release view v1.1.0 --repo mili-xi/xun_fei
```

Expected: both lookups report absence. If either exists, stop and investigate; never force or move a release tag.

- [ ] **Step 2: Create and push the annotated tag once**

```powershell
git fetch origin main
$approvedShaFile = Resolve-Path '..\approved-v1.1.0-sha.txt'
$approvedSha = (Get-Content -Raw $approvedShaFile).Trim()
$currentMainSha = git rev-parse origin/main
if ($currentMainSha -ne $approvedSha) { throw 'main advanced after release authorization.' }
git tag -a v1.1.0 $approvedSha -m "Xunfei Job Assistant v1.1.0"
git push origin refs/tags/v1.1.0
```

Expected: a new immutable annotated tag at the approved SHA; never use `git tag -f` or a forced tag push.

- [ ] **Step 3: Monitor publication without changing the tag**

```powershell
$approvedSha = (Get-Content -Raw ..\approved-v1.1.0-sha.txt).Trim()
$deadline = (Get-Date).AddMinutes(2)
do {
  $tagRun = gh run list --workflow release-windows.yml --commit $approvedSha --limit 10 `
    --json databaseId,event,status,conclusion,url,createdAt | ConvertFrom-Json | `
    Where-Object { $_.event -eq 'push' } | `
    Sort-Object { [datetime]$_.createdAt } -Descending | Select-Object -First 1
  if (-not $tagRun) { Start-Sleep -Seconds 2 }
} until ($tagRun -or (Get-Date) -ge $deadline)
if (-not $tagRun) { throw 'Timed out waiting for the tag workflow run.' }
gh run watch $tagRun.databaseId --exit-status
gh release view v1.1.0 --json tagName,isDraft,isPrerelease,assets,url
```

Expected: tag push event, successful run, non-draft/non-prerelease `v1.1.0`, installer, portable ZIP, `SHA256SUMS.txt`, and both SBOMs. A transient job failure may be rerun; a workflow-definition defect stops for owner review and never moves the tag automatically.

- [ ] **Step 4: Independently download and verify every release asset**

```powershell
$releaseDir = Resolve-Path '..'
$releaseDir = Join-Path $releaseDir 'v1.1.0-verification'
New-Item -ItemType Directory -Path $releaseDir -ErrorAction Stop | Out-Null
gh release download v1.1.0 --repo mili-xi/xun_fei --dir $releaseDir
```

Before recursive scanning, preserve and verify the downloaded release manifest:

```powershell
$manifestPath = Join-Path $releaseDir 'SHA256SUMS.txt'
$manifestHashBefore = (Get-FileHash -Algorithm SHA256 $manifestPath).Hash
$releaseRoot = [System.IO.Path]::GetFullPath($releaseDir).TrimEnd('\') + '\'
$manifestEntries = @{}
foreach ($line in Get-Content $manifestPath) {
  if ([string]::IsNullOrWhiteSpace($line)) { continue }
  if ($line -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') { throw "Malformed checksum line." }
  $expectedHash = $Matches[1].ToLowerInvariant()
  $name = $Matches[2].Trim()
  $assetPath = [System.IO.Path]::GetFullPath((Join-Path $releaseDir $name))
  if (-not $assetPath.StartsWith($releaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Checksum path escapes release directory: $name"
  }
  if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) { throw "Missing asset: $name" }
  $actualHash = (Get-FileHash -Algorithm SHA256 $assetPath).Hash.ToLowerInvariant()
  if ($actualHash -ne $expectedHash) { throw "Checksum mismatch: $name" }
  $manifestEntries[$name] = $actualHash
}
$releaseMetadata = gh api repos/mili-xi/xun_fei/releases/tags/v1.1.0 | ConvertFrom-Json
$publishedAssets = @($releaseMetadata.assets | Where-Object { $_.name -ne 'SHA256SUMS.txt' })
if (Compare-Object @($publishedAssets.name | Sort-Object) @($manifestEntries.Keys | Sort-Object)) {
  throw 'Release assets and checksum manifest differ.'
}
foreach ($asset in $publishedAssets) {
  if ($asset.digest -notmatch '^sha256:([0-9a-f]{64})$') { throw "Missing GitHub digest: $($asset.name)" }
  if ($manifestEntries[$asset.name] -ne $Matches[1]) { throw "GitHub digest mismatch: $($asset.name)" }
}
pwsh -File scripts/verify-release-artifacts.ps1 -Dist $releaseDir -ScanOnly
$manifestHashAfter = (Get-FileHash -Algorithm SHA256 $manifestPath).Hash
if ($manifestHashAfter -ne $manifestHashBefore) { throw 'Scan-only mode changed the release manifest.' }
```

Extract the portable ZIP and launch with no credential environment; verify the settings flow appears and no maintainer credential is present. Keep the repository private during this step.

- [ ] **Step 5: Verify tag identity and release scope**

```powershell
$tagCommit = git rev-parse 'v1.1.0^{commit}'
$approvedSha = (Get-Content -Raw ..\approved-v1.1.0-sha.txt).Trim()
if ($tagCommit -ne $approvedSha) { throw 'Release tag does not match approved release SHA.' }
gh release list --repo mili-xi/xun_fei --limit 100
```

Expected: the only formal release is `v1.1.0`; old `1.0.1` binaries remain revoked.

### Task 8: Audit The Visibility Transition And Make The Repository Public

**Files:** GitHub repository settings only.

- [ ] **Step 1: Scan every private Actions log and retained artifact before exposure**

```powershell
$auditRoot = Join-Path $env:TEMP ("xunfei-actions-audit-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $auditRoot -ErrorAction Stop | Out-Null
$runPages = gh api 'repos/mili-xi/xun_fei/actions/runs?per_page=100' --paginate --slurp | ConvertFrom-Json
$runs = @($runPages | ForEach-Object { $_.workflow_runs })
foreach ($run in $runs) {
  if ($run.status -ne 'completed') { throw "Workflow $($run.id) is not complete." }
  $logPath = Join-Path $auditRoot "$($run.id).log"
  gh run view $run.id --log | Set-Content -Encoding utf8 $logPath
  if ($LASTEXITCODE -ne 0) { throw "Unable to audit retained logs for workflow $($run.id)." }

  $artifactPages = gh api "repos/mili-xi/xun_fei/actions/runs/$($run.id)/artifacts?per_page=100" `
    --paginate --slurp | ConvertFrom-Json
  $artifacts = @($artifactPages | ForEach-Object { $_.artifacts } | Where-Object { -not $_.expired })
  if ($artifacts.Count -gt 0) {
    $artifactDir = Join-Path $auditRoot "$($run.id)-artifacts"
    gh run download $run.id --dir $artifactDir
    if ($LASTEXITCODE -ne 0) { throw "Unable to download artifacts for workflow $($run.id)." }
    pwsh -File scripts/verify-release-artifacts.ps1 -Dist $artifactDir -ScanOnly
  }
}
gitleaks dir $auditRoot --redact --exit-code 1
```

Expected: every paginated run with retained logs/artifacts is audited, nested artifact containers pass the recursive scanner, and Gitleaks reports no finding. A download/audit error is a blocker, not an empty result. GitHub can expose historical Actions logs/artifacts after a private-to-public transition, so any finding blocks publication and requires log/artifact deletion plus credential rotation where applicable.

- [ ] **Step 2: Reconfirm all public-safety gates with the owner**

Confirm credential rotation, all-ref rewrite, zero reachable LFS pointers, no legacy release, clean release artifacts, clean Actions history, and no unresolved GitHub Secret Scanning alert. A 403/404 from the alert API requires manual Security-page confirmation and is not success.

Also verify `https://github.com/mili-xi` is publicly visible while logged out. The OpenAI form explicitly requires a public GitHub profile.

Save full definitions for any existing repository ruleset outside the repository so a visibility change cannot silently weaken it:

```powershell
$rulesetSnapshot = Join-Path $env:TEMP 'xunfei-rulesets-before-public.json'
$ruleSummaries = @(gh api repos/mili-xi/xun_fei/rulesets | ConvertFrom-Json)
$fullRules = @($ruleSummaries | ForEach-Object {
  gh api "repos/mili-xi/xun_fei/rulesets/$($_.id)" | ConvertFrom-Json
})
ConvertTo-Json -InputObject @($fullRules) -Depth 20 | Set-Content -Encoding utf8 $rulesetSnapshot
$roundTrip = @(Get-Content -Raw $rulesetSnapshot | ConvertFrom-Json)
if ($roundTrip.Count -ne $fullRules.Count) { throw 'Ruleset snapshot did not round-trip.' }
```

- [ ] **Step 3: Obtain separate visibility authorization and publish**

Fetch and show the current counters without presenting them as impact evidence:

```powershell
gh api repos/mili-xi/xun_fei --jq `
  '{stars: .stargazers_count, watchers: .subscribers_count, forks: .forks_count, visibility: .visibility}'
```

Restate that the earlier public-to-private transition can erase stars/watchers and alter the fork network; making the repository public exposes source, issues, PRs, Actions history/logs, and the private release, allows anyone to fork, and can disable push rulesets until restored. After explicit owner confirmation of those effects, run exactly:

```powershell
gh repo edit mili-xi/xun_fei --visibility public --accept-visibility-change-consequences
```

Expected: the command succeeds once. Do not combine it with tag creation or other writes.

- [ ] **Step 4: Verify anonymously from public GitHub endpoints**

```powershell
$headers = @{
  'User-Agent' = 'xunfei-public-verifier'
  'Accept' = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
}
$repo = Invoke-RestMethod -Headers $headers https://api.github.com/repos/mili-xi/xun_fei
if ($repo.visibility -ne 'public' -or $repo.default_branch -ne 'main') { throw 'Public repository metadata is wrong.' }
if ($repo.license.spdx_id -ne 'Apache-2.0') { throw 'GitHub does not detect Apache-2.0.' }
$release = Invoke-RestMethod -Headers $headers https://api.github.com/repos/mili-xi/xun_fei/releases/tags/v1.1.0
if ($release.draft -or $release.prerelease) { throw 'Release is not final.' }
$assetNames = @($release.assets | Select-Object -ExpandProperty name)
if (-not ($assetNames -match '\.exe$') -or -not ($assetNames -match '\.zip$')) { throw 'Binary release assets are missing.' }
if ('SHA256SUMS.txt' -notin $assetNames) { throw 'Checksum asset is missing.' }
if (@($assetNames | Where-Object { $_ -like '*.cdx.json' }).Count -ne 2) { throw 'Expected two SBOM assets.' }
foreach ($asset in $release.assets) {
  if ($asset.digest -notmatch '^sha256:[0-9a-f]{64}$') { throw "Asset digest missing for $($asset.name)." }
  Invoke-WebRequest -Method Head -MaximumRedirection 5 -Headers $headers $asset.browser_download_url | Out-Null
}
$publicFiles = @(
  'README.md',
  'LICENSE',
  'SECURITY.md',
  '.github/ISSUE_TEMPLATE/adoption_report.yml'
)
foreach ($path in $publicFiles) {
  $rawUrl = "https://raw.githubusercontent.com/mili-xi/xun_fei/main/$path"
  Invoke-WebRequest -Headers $headers $rawUrl | Out-Null
}
```

Expected: anonymous API access, public `main`, GitHub-detected Apache-2.0, readable README/security/adoption files, exact release asset categories/digests, and anonymously downloadable assets.

- [ ] **Step 5: Restore protections that visibility changes can disable**

Enable private vulnerability reporting:

```powershell
gh api --method PUT repos/mili-xi/xun_fei/private-vulnerability-reporting
gh repo edit mili-xi/xun_fei --enable-secret-scanning --enable-secret-scanning-push-protection
if ($LASTEXITCODE -ne 0) { throw 'Unable to enable GitHub secret scanning and push protection.' }
$security = gh api repos/mili-xi/xun_fei | ConvertFrom-Json
if ($security.security_and_analysis.secret_scanning.status -ne 'enabled' -or
    $security.security_and_analysis.secret_scanning_push_protection.status -ne 'enabled') {
  throw 'GitHub security analysis settings are not enabled.'
}
$alertPages = gh api 'repos/mili-xi/xun_fei/secret-scanning/alerts?state=open&per_page=100' `
  --paginate --slurp | ConvertFrom-Json
$openAlertCount = @($alertPages | ForEach-Object { $_ }).Count
if ($openAlertCount -ne 0) { throw "$openAlertCount open secret-scanning alert(s) remain." }
```

Build a branch-protection request from the actual successful release-PR checks. Do not guess contexts:

```powershell
$releasePr = gh pr list --state merged --base main --head dev --limit 1 --json number | ConvertFrom-Json
if (@($releasePr).Count -ne 1) { throw 'Cannot identify the merged dev-to-main release PR.' }
$expectedWorkflows = @('CI', 'CodeQL', 'Dependency Review', 'Secret Scan')
$checks = gh pr checks $releasePr[0].number --json name,workflow,bucket | ConvertFrom-Json
$contexts = @($checks | Where-Object {
  $_.bucket -eq 'pass' -and $_.workflow -in $expectedWorkflows
} | Select-Object -ExpandProperty name -Unique)
if ($contexts.Count -lt 4) { throw 'Expected CI/security checks are missing.' }
$protection = @{
  required_status_checks = @{ strict = $true; contexts = $contexts }
  enforce_admins = $true
  required_pull_request_reviews = @{
    dismiss_stale_reviews = $true
    require_code_owner_reviews = $false
    require_last_push_approval = $false
    required_approving_review_count = 0
  }
  restrictions = $null
  required_linear_history = $false
  allow_force_pushes = $false
  allow_deletions = $false
  block_creations = $false
  required_conversation_resolution = $true
  lock_branch = $false
  allow_fork_syncing = $true
}
$protectionFile = Join-Path $env:TEMP 'xunfei-main-protection.json'
$protection | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $protectionFile
gh api --method PUT repos/mili-xi/xun_fei/branches/main/protection --input $protectionFile
gh api repos/mili-xi/xun_fei/branches/main/protection
Remove-Item -LiteralPath $protectionFile
```

Restore each ruleset from the pre-publication snapshot using only writable fields:

```powershell
$rulesetSnapshot = Join-Path $env:TEMP 'xunfei-rulesets-before-public.json'
if (-not (Test-Path -LiteralPath $rulesetSnapshot)) { throw 'Ruleset snapshot is missing.' }
$priorRules = @(Get-Content -Raw $rulesetSnapshot | ConvertFrom-Json)
$currentRules = @(gh api repos/mili-xi/xun_fei/rulesets | ConvertFrom-Json)
foreach ($prior in $priorRules) {
  $body = [ordered]@{
    name = $prior.name
    target = $prior.target
    enforcement = $prior.enforcement
    bypass_actors = @($prior.bypass_actors)
    conditions = $prior.conditions
    rules = @($prior.rules)
  }
  $bodyFile = Join-Path $env:TEMP ("xunfei-ruleset-$($prior.id).json")
  $body | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 $bodyFile
  $current = $currentRules | Where-Object { $_.id -eq $prior.id }
  if ($current) {
    gh api --method PUT "repos/mili-xi/xun_fei/rulesets/$($prior.id)" --input $bodyFile | Out-Null
  } else {
    gh api --method POST repos/mili-xi/xun_fei/rulesets --input $bodyFile | Out-Null
  }
  Remove-Item -LiteralPath $bodyFile
  $restored = gh api repos/mili-xi/xun_fei/rulesets | ConvertFrom-Json | `
    Where-Object { $_.name -eq $prior.name -and $_.target -eq $prior.target }
  if (-not $restored -or $restored.enforcement -ne $prior.enforcement) {
    throw "Ruleset $($prior.name) was not restored."
  }
}
```

If the snapshot was empty, no synthetic ruleset is created because main branch protection now supplies the required controls.

The commands above report only an alert count, never alert content. API unavailability requires manual Security-page confirmation and blocks progress until confirmed. Delete `$rulesetSnapshot` only after ruleset comparison succeeds.

### Task 9: Refresh Public Evidence And Merge A Factual Metrics PR

**Files:**
- Modify generated block: `docs/impact.md`
- Modify readiness/link snapshot: `docs/CODEX_FOR_OSS_APPLICATION.md`

- [ ] **Step 1: Refresh through the anonymous public API**

Clear `GITHUB_TOKEN` for this external-verifiability run, then execute:

```powershell
git fetch origin main
git switch -c docs/public-impact-snapshot origin/main
$savedToken = $env:GITHUB_TOKEN
$env:GITHUB_TOKEN = $null
try { npm run metrics:release } finally { $env:GITHUB_TOKEN = $savedToken }
node --test scripts/releaseMetrics.test.js electron/impactContract.test.js
```

Expected: `impact.md` contains the UTC snapshot, exact repository counts, release assets and raw cumulative asset-download events. It explicitly reports monthly downloads as unavailable from one GitHub snapshot.

- [ ] **Step 2: Record adoption categories without manufacturing data**

Search public adoption issues and downstream references. Include or link an adoption report in `impact.md` only when its optional citation permission is checked. If no permitted unsolicited report exists, keep `None recorded`. Do not create or ask a collaborator to create a demonstration report; maintainer installs and release smoke tests remain maintenance evidence only.

- [ ] **Step 3: Mark technical submission readiness with exact links**

Change the application document's readiness state only after Tasks 1-8 pass. Link the public `v1.1.0` release, successful Actions runs, `SECURITY.md`, `CONTRIBUTING.md`, commit history, issues, PRs, and `docs/impact.md`. Keep the six tested form answers unchanged unless a factual correction is required; rerun the 500-character contract after any edit.

- [ ] **Step 4: Submit the evidence update through a real PR**

```powershell
git add -- docs/impact.md docs/CODEX_FOR_OSS_APPLICATION.md
git commit -m "docs: record first public release evidence"
git push --set-upstream origin docs/public-impact-snapshot
$evidencePr = gh pr create --base main --head docs/public-impact-snapshot `
  --title "docs: record first public release evidence" `
  --body "Refreshes public GitHub metrics and Codex application links without claiming external adoption."
gh pr checks $evidencePr --watch
$evidence = gh pr view $evidencePr --json number,headRefOid | ConvertFrom-Json
gh pr merge $evidence.number --merge --delete-branch --match-head-commit $evidence.headRefOid
```

Review the generated diff and merge only after checks pass. This PR is a necessary evidence update, not synthetic community activity.

### Task 10: Final Verification, Application Handoff, And Sensitive Recovery Cleanup

**Files:** All public repository and release surfaces; local recovery data from the security plan.

- [ ] **Step 1: Run verification-before-completion**

Use `superpowers:verification-before-completion` and run fresh commands:

```powershell
git fetch origin main dev --tags
git switch main
git pull --ff-only origin main
npm run verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test scripts/releaseMetrics.test.js electron/impactContract.test.js electron/workflowConfig.test.js
gitleaks git . --redact --exit-code 1
git diff origin/main...HEAD --check
$approvedSha = (Get-Content -Raw ..\approved-v1.1.0-sha.txt).Trim()
$tagSha = git rev-parse 'v1.1.0^{commit}'
if ($tagSha -ne $approvedSha) { throw 'Tag no longer identifies the approved release SHA.' }
git merge-base --is-ancestor v1.1.0 origin/main
if ($LASTEXITCODE -ne 0) { throw 'The public main branch no longer descends from v1.1.0.' }
```

Verify anonymous repository/release access, checksums, tag identity against the recorded release SHA, `v1.1.0` ancestry of the evidence-updated `main`, only `main`/`dev`, active main protection, private vulnerability reporting, zero open secret alerts, and public GitHub profile. Record exact failures rather than interpreting unavailable data as success.

- [ ] **Step 2: Perform final application-day refresh**

On the day the owner submits, rerun `npm run metrics:release`, the application length test, and the public-link checks. If the generated block changed, submit and merge another factual evidence PR using Task 9's exact workflow before submitting the form. Review the current official form and Program Terms. The form is rolling review and acceptance is not guaranteed; use current facts even if stars, downloads, adoption reports, or downstream references remain zero.

- [ ] **Step 3: Hand off private form completion to the owner**

The owner manually enters legal first/last name and ChatGPT account email, selects the desired program benefits, and provides an OpenAI Organization ID only when selecting project API credits. The owner reviews the terms and clicks Submit. These personal fields and legal acceptance are never automated or committed. The repository document supplies only the reviewed public answers and links.

- [ ] **Step 4: Delete the restricted historical recovery copy after explicit approval**

Once the owner confirms the clean public repository/release no longer needs rollback, resolve the recovery path and prove it is the exact intended directory under this workspace before recursive deletion:

```powershell
$workspace = (Resolve-Path 'C:\Users\52558\Documents\Codex\2026-07-12\github-plugin-github-openai-curated-remote\work').Path
$recovery = (Resolve-Path (Join-Path $workspace 'xun_fei-recovery.git')).Path
if ((Split-Path $recovery -Parent) -ne $workspace -or (Split-Path $recovery -Leaf) -ne 'xun_fei-recovery.git') {
  throw 'Recovery deletion target is outside the approved workspace.'
}
Remove-Item -LiteralPath $recovery -Recurse -Force
$approvedShaFile = Join-Path $workspace 'approved-v1.1.0-sha.txt'
if (Test-Path -LiteralPath $approvedShaFile) { Remove-Item -LiteralPath $approvedShaFile -Force }
```

Delete temporary Actions logs, downloaded release candidates, and Gitleaks reports with the same resolved-path discipline. Never delete the clean source checkout.

- [ ] **Step 5: Record completion evidence**

Capture final public URLs, release SHA, workflow run IDs, verification command results, actual metrics snapshot, and remaining acceptance risk in the project knowledge base. Do not store credentials, personal form values, or full logs.
