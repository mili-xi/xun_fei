# Codex for Open Source Readiness Design

**Date:** 2026-07-12
**Repository:** `mili-xi/xun_fei`
**Status:** Approved

## Context

`xun_fei` is a working Windows desktop job-search assistant with a Flask backend, an Electron shell, browser-based frontend assets, local tests, and an existing packaging flow. The public repository has 31 commits, with `mili-xi` responsible for most of the visible development and two other contributors represented in the history.

The repository is not currently ready for an OpenAI Codex for Open Source application. Its present branch and history contain credential-bearing configuration and packaged artifacts, it has no root open-source license, and it has no public release, CI, issue, pull-request, or verified adoption record. OpenAI evaluates active open-source maintenance, meaningful usage or ecosystem importance, and evidence such as review, triage, and release work. This design improves the repository honestly; it does not manufacture usage or community activity and cannot guarantee program acceptance.

## Goals

1. Contain and remove all credential-bearing files and artifacts from the repository and its reachable history.
2. Preserve legitimate source-code history, authorship, and contributor attribution while removing unsafe paths.
3. Convert the repository into a source-first Apache-2.0 open-source project with clear governance and contribution processes.
4. Replace bundled maintainer credentials with user-controlled configuration that lives outside the application bundle.
5. Add repeatable CI, security scanning, and a release pipeline that produces clean Windows artifacts.
6. Publish an honest impact record and a fact-based Codex for Open Source application draft.

## Non-Goals

- Buying or fabricating stars, downloads, issues, pull requests, contributors, deployments, or testimonials.
- Claiming affiliation with iFlytek or OpenAI.
- Operating a hosted credential proxy or shared paid API service.
- Adding unrelated product features solely to make the repository look larger.
- Guaranteeing acceptance into Codex for Open Source.

## 1. Incident Containment And History Cleanup

Before the repository is public again, the owner must make it private and revoke or rotate every credential that has ever appeared in `.env` or a packaged artifact. Rotation is mandatory because deleting Git objects cannot invalidate copies already fetched by third parties.

A full mirror will be filtered in place across all branches and tags. The cleanup removes:

- every `.env` file except a verified empty `.env.example`;
- `dist/` and all packaged EXE, ZIP, unpacked application, and embedded configuration artifacts;
- `runtime/` and vendored Python/ffmpeg distributions;
- obsolete LFS objects and references associated with removed release artifacts.

The filter preserves source commits, commit authors, commit timestamps, and contributor attribution. After filtering, all rewritten refs are scanned for secrets before any force-push. Only `main` and `dev` remain active: `main` is the stable release branch and `dev` is the integration branch. The stale `xun_fei_backed` and `xun_fei_front` branches are removed after their source history is confirmed to be represented in the cleaned refs.

The repository remains private until all of the following are true:

- credential rotation is confirmed by the owner;
- the current tree and rewritten history pass secret scanning;
- no tracked archive or executable contains application credentials;
- source and release builds pass their test suites;
- GitHub secret scanning has no unresolved repository findings.

## 2. Source-First Repository Structure

The Git repository contains only maintainable source, tests, documentation, and deterministic build definitions:

```text
.
|-- .github/
|   |-- ISSUE_TEMPLATE/
|   |-- workflows/
|   `-- CODEOWNERS
|-- build/                  # icons and installer source assets only
|-- docs/
|   |-- architecture.md
|   |-- impact.md
|   |-- security-model.md
|   `-- CODEX_FOR_OSS_APPLICATION.md
|-- electron/
|-- tests/
|-- 前端/                    # existing browser-based frontend source
|-- 后端/                    # existing Flask backend source
|-- scripts/                # reproducible setup and release checks
|-- .env.example
|-- LICENSE
|-- NOTICE
|-- README.md
|-- README.zh-CN.md
`-- package.json
```

Generated output, downloaded runtimes, local environments, caches, credentials, and installers are ignored. The release workflow stages pinned runtime dependencies in a temporary build directory and never commits them.

## 3. Credential And Configuration Model

Maintainer credentials are never shipped. The backend reads configuration through one typed configuration boundary. The supported precedence is:

1. process environment variables for development and automation;
2. a per-user application configuration stored under Electron's `userData` directory;
3. documented non-secret defaults from `.env.example`.

The desktop application provides a first-run settings flow for users to supply their own iFlytek credentials. Sensitive values are encrypted with Electron `safeStorage` before being written to the user profile. Electron passes decrypted values only to the locally launched backend process through its environment. The frontend never receives raw credentials, logs redact secret fields, and error messages name a missing variable without printing its value.

The build fails if a real `.env` file is present in the packaging context or if the final artifact contains forbidden credential paths. The release workflow also extracts the produced installer/portable archive into a temporary directory and checks that no `.env` or known secret variable value is embedded.

## 4. Open-Source Governance

The project's original code is licensed under Apache License 2.0. Third-party software remains under its own licenses and is documented in `NOTICE` and a third-party dependency inventory. Contributor history is retained, `mili-xi` is identified as the primary maintainer, and no unsupported maintainer role is assigned to another contributor.

The repository adds:

- `CONTRIBUTING.md` with development setup, testing, commit, and pull-request expectations;
- `SECURITY.md` with private vulnerability reporting and response expectations;
- `CODE_OF_CONDUCT.md` based on Contributor Covenant;
- `GOVERNANCE.md` describing decision making, maintainer responsibilities, and releases;
- `CHANGELOG.md` following Keep a Changelog;
- issue forms for bugs, features, and voluntary adoption reports;
- a pull-request template and `CODEOWNERS` for review ownership;
- Dependabot configuration and contribution/license provenance checks.

The repository description and README state that the project is an independent community project that integrates with iFlytek APIs and is not affiliated with or endorsed by iFlytek.

## 5. CI, Security, And Release Engineering

Pull-request and branch CI runs the existing Python and Electron tests, static checks, configuration-contract tests, a credential-packaging regression test, and secret scanning. CodeQL covers Python and JavaScript. Dependency review runs on pull requests, and Dependabot proposes dependency updates.

The tag-driven Windows release workflow:

1. checks out source without historical artifacts;
2. installs pinned Node and Python toolchains;
3. downloads pinned ffmpeg/runtime inputs and verifies their checksums;
4. runs all tests and static checks;
5. builds the Electron installer and portable archive;
6. extracts and scans artifacts for forbidden credentials and paths;
7. generates SHA-256 checksums, an SBOM, and release notes;
8. publishes artifacts only from a `v*` tag on `main`.

The first clean public release is `v1.1.0`. Old `1.0.1` artifacts are revoked and are not republished. Because no signing certificate is currently available, documentation promises checksums but does not claim that binaries are code-signed.

## 6. Public Positioning And Impact Evidence

The project is positioned as an open-source, local-first desktop job-search assistant for Chinese-speaking users. The primary public value is a reusable implementation of resume analysis, job-description matching, interview practice, voice interaction, and user-controlled AI-provider credentials on Windows.

The README provides a real screenshot or demonstration, a short install path, source setup, architecture, security model, contribution links, current limitations, and CI/release/license badges. English and Simplified Chinese documentation share the same factual claims.

GitHub Releases is the only binary download channel so that download counts are externally verifiable. `docs/impact.md` records only verifiable evidence: release downloads, public adopter reports, downstream references, maintenance events, and published case studies. An opt-in adoption issue form lets schools, teams, and individuals report usage without adding product telemetry. Empty evidence remains explicitly empty until real users report it.

## 7. Codex For Open Source Application Material

`docs/CODEX_FOR_OSS_APPLICATION.md` contains concise Chinese and English drafts for the application fields. It documents:

- `mili-xi` as primary maintainer and the repository permissions/commit evidence supporting that role;
- the project's audience, technical scope, and ecosystem rationale;
- current public adoption metrics without embellishment;
- concrete Codex use cases: pull-request review, issue triage, regression-test generation, security review, release automation, and changelog preparation;
- direct links to releases, CI, security policy, contribution history, issues, pull requests, and impact evidence.

The repository can be submitted after the technical readiness gates pass, but the application document warns that acceptance odds improve after genuine release downloads, adopter reports, or downstream use become visible. It never presents a newly created issue, self-download, or internal test as external adoption.

## 8. Testing Strategy

Behavior changes use red-green-refactor development:

- configuration tests prove secrets come from supported user/environment sources and are redacted from errors;
- Electron tests prove credentials are stored outside application resources and passed only to the child backend process;
- packaging tests fail when `.env`, secret values, or forbidden directories appear in build output;
- CI tests verify source builds do not depend on tracked `runtime/` or `dist/` content;
- documentation checks verify required community and application evidence files exist and contain no placeholder claims;
- a final full-history secret scan runs before rewritten refs are pushed.

## 9. Rollout Sequence

1. Owner makes the repository private and rotates all historical credentials.
2. Create a local mirror and preserve a temporary, access-restricted recovery copy until cleanup is verified.
3. Filter history and LFS objects, scan all rewritten refs, and force-push the clean private repository.
4. Implement credential/configuration changes with tests.
5. Add license, governance, documentation, CI, and release automation.
6. Open a review branch and run full code/security review.
7. Merge into `main`, tag `v1.1.0`, and publish a clean GitHub Release.
8. Verify public repository pages, release artifacts, and download links before making the repository public.
9. Refresh factual metrics and finalize the Codex for Open Source application draft.

## Success Criteria

- No rewritten branch, tag, release, or current artifact contains a project credential or credential-bearing file. Any cached or unreachable historical object is rendered harmless by credential rotation, with a GitHub purge request used where necessary.
- All historical credentials are revoked or rotated outside GitHub.
- The current repository has an Apache-2.0 license and complete community/security documentation.
- CI and security workflows pass on `main` and on the release tag.
- `v1.1.0` installs and starts without a maintainer-owned credential and contains no `.env`.
- The public README, impact record, and application draft contain only verifiable claims.
- The project is technically ready for submission, with any remaining acceptance risk explicitly attributed to genuine adoption rather than repository quality or safety defects.
