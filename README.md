# Xunfei Job Assistant

Xunfei Job Assistant is an independent, local-first Windows desktop assistant for Chinese-speaking job seekers. It helps with resume analysis, job description matching, interview practice, text chat, and optional voice/OCR workflows.

This repository is being prepared for public open-source release. It does not ship maintainer-owned iFlytek or OpenAI credentials. Users bring and control their own provider credentials.

## Status

- License: Apache-2.0 for original project source.
- Maintainer: [@mili-xi](https://github.com/mili-xi).
- Public release target: `v1.1.0` through GitHub Releases after history cleanup, CI, and artifact verification are complete.
- Current limitation: the repository must remain private until historical credential and binary-removal gates are verified.

## Features

- Resume text/image analysis for job-search preparation.
- Job description matching and improvement suggestions.
- Interview question generation and answer feedback.
- Text chat for job-search and interview preparation.
- Optional OCR, speech recognition, voice Q&A, and text-to-speech when user-owned provider credentials are configured.

## Privacy And Credentials

The application is designed around BYOK: bring your own keys. Credentials should be supplied through local environment variables or the secure desktop settings flow once the `v1.1.0` security work lands. Credentials, resumes, recordings, generated binaries, and local logs must not be committed.

The project is not affiliated with or endorsed by iFlytek or OpenAI. Product and company names are trademarks of their respective owners.

## Install

Public downloads will be published on the repository's GitHub Releases page after the verified `v1.1.0` release is complete. Do not use tracked `dist/` files or historical local installer links as public releases.

Release artifacts will include checksums and SBOM files. Windows binaries are not code-signed unless a future release explicitly states otherwise.

## Development

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

Run tests:

```powershell
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run verify:packaging-context
```

Run the app from source:

```powershell
npm start
```

## Configuration

Use `.env.example` only as a reference for supported environment variable names. The production application must not load committed `.env` files or package them into release artifacts.

Common variables:

```env
IFLYTEK_APP_ID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=
IFLYTEK_SPARK_API_PASSWORD=
SPARK_URL=https://spark-api-open.xf-yun.com/v1/chat/completions
SPARK_WS_URL=wss://spark-api.xf-yun.com/v3.1/chat
OCR_URL=https://cbm01.cn-huabei-1.xf-yun.com/v1/private/se75ocrbm
PORT=5000
FFMPEG_PATH=ffmpeg
```

## Project Evidence

Open-source readiness, impact policy, and Codex for Open Source application material are tracked in:

- [Impact evidence](docs/impact.md)
- [Security model](docs/security-model.md)
- [Architecture](docs/architecture.md)
- [Codex for OSS application draft](docs/CODEX_FOR_OSS_APPLICATION.md)

The impact document reports only externally verifiable facts. Maintainer smoke tests and self-downloads are not described as external adoption.

## Contributing And Security

Read [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and [SECURITY.md](SECURITY.md) before opening issues or pull requests. Please never include credentials, resumes, recordings, private emails, or other personal data in public reports.
