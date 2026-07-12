# Architecture

Xunfei Job Assistant is a local desktop application with three main parts:

- Electron main process: owns desktop lifecycle, backend launch, local settings, and release packaging boundaries.
- Renderer/frontend: presents job-search workflows and sends local requests.
- Flask backend: exposes local APIs for resume analysis, interview practice, OCR, LLM, and voice workflows.

Provider credentials are intended to stay in the local user environment or encrypted desktop storage. The backend should receive only the credentials needed for the current local process. Public releases should be built from source-only inputs, staged runtimes, and recursively scanned artifacts.
