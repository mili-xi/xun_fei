# Security Model

## Trust Boundaries

The user controls local credentials and personal job-search data. The project maintainer does not provide a hosted credential proxy and does not need access to real resumes or recordings for normal development.

Electron launches a local backend process. The backend talks to configured providers only when the user supplies credentials. Release builds must not include `.env` files, maintainer credentials, generated installers from history, or private personal data.

## BYOK Limits

BYOK protects maintainer credentials from redistribution, but it does not make provider usage free or anonymous. Users remain responsible for their own provider accounts, quotas, and data-sharing choices.

## Incident Handling

If a credential is exposed, rotate or revoke it first, then remove the exposure path and verify history, release artifacts, Actions logs, and local documentation. Public reports must not include secret values.
