# 讯飞求职助手

讯飞求职助手是一个独立的、本地优先的 Windows 桌面开源项目，面向中文求职场景，提供简历分析、岗位 JD 匹配、模拟面试、文本问答，以及在用户自行配置凭据后可用的 OCR 和语音能力。

本仓库正在按公开开源项目标准整理。项目不会内置维护者的讯飞或 OpenAI 凭据，用户需要自带并自行管理服务商凭据。

## 当前状态

- 许可：项目原创源码采用 Apache-2.0。
- 维护者：[@mili-xi](https://github.com/mili-xi)。
- 公开发布目标：完成历史清理、CI、安全扫描和产物验证后，通过 GitHub Releases 发布 `v1.1.0`。
- 当前限制：在历史凭据和二进制产物清理完成并验证前，仓库应保持私有。

## 功能

- 简历文本或图片分析。
- 简历与岗位 JD 匹配和优化建议。
- 模拟面试题生成与回答反馈。
- 求职准备文本问答。
- 用户配置自有凭据后，可启用 OCR、语音识别、语音问答和语音播报。

## 隐私与凭据

项目采用 BYOK（Bring Your Own Key）模式。凭据应通过本地环境变量或后续安全桌面设置流程提供。凭据、简历、录音、生成的安装包和本地日志都不应提交到仓库。

本项目是独立社区项目，与讯飞或 OpenAI 没有关联、背书或从属关系。产品名和公司名属于各自权利人。

## 安装

正式公开下载会在完成 `v1.1.0` 验证发布后通过 GitHub Releases 提供。不要把仓库中的历史 `dist/` 文件或本地安装包链接当作公开发布。

发布产物会附带校验和与 SBOM。除非未来版本明确说明，否则 Windows 二进制不会进行代码签名。

## 开发

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

运行测试：

```powershell
npm run test:electron
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run verify:packaging-context
```

从源码启动：

```powershell
npm start
```

## 配置

`.env.example` 只作为环境变量名称参考。生产应用不应读取已提交的 `.env` 文件，也不应把 `.env` 打入发布产物。

常用变量：

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

## 申请与影响证据

开源准备、影响证据和 Codex for Open Source 申请材料记录在：

- [影响证据](docs/impact.md)
- [安全模型](docs/security-model.md)
- [架构说明](docs/architecture.md)
- [Codex for OSS 申请草稿](docs/CODEX_FOR_OSS_APPLICATION.md)

影响证据只记录可公开核验的事实。维护者自测和自下载不会被描述成外部采用。

## 贡献与安全

提交 Issue 或 PR 前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)、[GOVERNANCE.md](GOVERNANCE.md) 和 [SECURITY.md](SECURITY.md)。请不要在公开内容中包含凭据、简历、录音、私人邮箱或其他个人数据。
