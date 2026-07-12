# Third-Party Notices

This document records major third-party components used by Xunfei Job Assistant. Exact release inventories should be generated as SBOM files during release builds.

| Component | Use | License family |
| --- | --- | --- |
| Electron | Desktop shell | MIT |
| electron-builder | Windows packaging | MIT |
| Flask | Local backend server | BSD |
| requests | HTTP client | Apache-2.0 |
| websocket-client | WebSocket client | Apache-2.0 |
| Python | Embedded runtime for Windows releases | PSF License |
| NSIS | Windows installer | zlib/libpng |
| 7-Zip | Archive extraction during build | LGPL / BSD / unRAR restriction notice |
| ffmpeg | Optional audio processing runtime | Build-dependent; release builds must preserve the selected build license |

ffmpeg is a separately licensed bundled program when included in release artifacts. Release notes and SBOMs must identify the exact ffmpeg build, source, and license.
