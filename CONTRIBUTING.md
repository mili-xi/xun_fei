# Contributing

Thanks for helping improve Xunfei Job Assistant.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

## Checks

```powershell
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run verify:packaging-context
```

Use short feature branches such as `fix/health-check` or `docs/security-model`. Pull requests should describe the user-visible behavior, tests run, and any security/privacy impact.

Never commit credentials, resumes, recordings, generated installers, archives, local logs, or private personal data. If a secret is committed by mistake, rotate it first, then report the incident privately through the security process.
