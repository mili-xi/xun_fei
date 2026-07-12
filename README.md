# 讯飞求职助手

讯飞求职助手是一款面向求职场景的桌面应用，提供简历分析、岗位匹配、模拟面试、语音问答和文本聊天等功能。当前仓库已经整理为可直接安装使用的 Windows 安装包项目，适合小组内部直接分发。

## 下载安装

优先使用已经打包好的桌面版：

- 安装版：[`dist/讯飞求职助手 Setup 1.0.1.exe`](./dist/%E8%AE%AF%E9%A3%9E%E6%B1%82%E8%81%8C%E5%8A%A9%E6%89%8B%20Setup%201.0.1.exe)
- 便携版：[`dist/讯飞求职助手-1.0.1-win-x64-portable.zip`](./dist/%E8%AE%AF%E9%A3%9E%E6%B1%82%E8%81%8C%E5%8A%A9%E6%89%8B-1.0.1-win-x64-portable.zip)

说明：

- `Setup 1.0.1.exe` 适合普通用户，双击安装即可使用。
- `portable.zip` 适合不想安装、希望解压即用的场景。
- 当前安装包已内置运行时、前后端资源和项目当前使用的 `.env` 配置。

### 1.0.1 更新内容

- 修复模拟面试在回答完上一题后，下一题输入框仍然保留旧回答的问题
- 切换到下一题时，会同步清空文字输入框和实时语音识别缓存
- 更新桌面安装包与便携包版本到 `1.0.1`

如果是从 GitHub 克隆整个仓库，请先安装 Git LFS，否则安装包和运行时大文件无法完整拉取：

```bash
git lfs install
git clone https://github.com/mili-xi/xun_fei.git
```

## Windows 安装版使用方法

1. 下载 `dist/讯飞求职助手 Setup 1.0.1.exe`
2. 双击运行安装程序
3. 按向导选择安装目录并完成安装
4. 安装完成后，点击桌面或开始菜单中的“讯飞求职助手”
5. 程序会自动启动本地后端服务，并打开桌面应用界面

首次启动说明：

- 应用会自动检查后端健康状态。
- 如果缺少某些可选能力，程序会弹出提醒，但基础功能仍可继续使用。
- 语音相关功能依赖内置运行时和讯飞配置，首次启动可能稍慢。

## 便携版使用方法

1. 下载 `dist/讯飞求职助手-1.0.1-win-x64-portable.zip`
2. 解压到任意目录
3. 运行解压后的 `讯飞求职助手.exe`

便携版同样已经包含运行所需资源，不需要单独安装 Python、Node.js 或 ffmpeg。

## 主要功能

- 简历图片识别与内容提取
- 简历与岗位 JD 匹配分析
- 模拟面试题生成
- 面试答题记录与反馈报告
- 文本聊天助手
- 语音识别、语音问答、语音播报

## 应用内使用流程

### 1. 简历分析

1. 上传简历图片，或直接粘贴简历文本
2. 输入目标岗位 JD
3. 点击开始分析
4. 查看匹配度、亮点、问题点和优化建议

### 2. 模拟面试

1. 先完成简历分析，或直接输入简历内容
2. 进入模拟面试模块
3. 系统生成面试题
4. 使用文字或语音作答
5. 查看追问、反馈和总结

### 3. 文本聊天

1. 在聊天区域输入问题
2. 可围绕简历优化、岗位准备、面试表达等内容继续追问

### 4. 语音功能

- 语音识别：将录音内容转文字
- 语音问答：语音输入后生成回答
- 语音播报：将回复朗读出来

## 项目结构

```text
xun_fei/
├─ build/                         # 安装器图标与 NSIS 资源
├─ dist/                          # 打包输出目录
│  ├─ 讯飞求职助手 Setup 1.0.1.exe
│  ├─ 讯飞求职助手-1.0.1-win-x64-portable.zip
│  └─ win-unpacked/
├─ electron/                      # Electron 桌面壳
├─ 前端/                          # HTML 前端资源
├─ 后端/                          # Flask 后端
├─ runtime/                       # 内置 Python / ffmpeg 运行时
├─ tests/                         # Python 测试
├─ .env                           # 当前项目配置
├─ package.json                   # Electron 打包配置
└─ README.md
```

## 源码运行方式

如果你不是直接使用安装包，而是要在开发环境中运行源码，可以按下面方式启动。

### Python 依赖安装

```powershell
python -m pip install -r requirements.txt
```

### 启动后端

```powershell
python 后端/app.py
```

默认访问地址：

```text
http://127.0.0.1:5000/
```

兼容入口：

```text
http://127.0.0.1:5000/unified.html
```

### Windows 一键启动

仓库根目录提供：

- `start_windows.bat`
- `启动求职助手.bat`

它们适合本地测试或小组内部快速启动。

## 配置说明

项目根目录使用 `.env` 管理讯飞相关配置，当前桌面安装包也会将该配置一起打进应用。

常用变量示例：

```env
IFLYTEK_APP_ID=你的APPID
IFLYTEK_API_KEY=你的APIKey
IFLYTEK_API_SECRET=你的APISecret
IFLYTEK_SPARK_API_PASSWORD=你的SparkAPIPassword
IFLYTEK_SPARK_MODEL=lite
PORT=5000
FFMPEG_PATH=ffmpeg
```

说明：

- 安装包模式下，一般不需要用户额外安装 ffmpeg。
- 如果以源码模式运行，`FFMPEG_PATH` 需要能正确指向本机 `ffmpeg`。

## 桌面打包

项目已经接入 Electron + electron-builder + NSIS。

常用命令：

```powershell
npm install
npm run test:electron
npm run dist
```

打包产物默认输出到 `dist/` 目录。

## 测试

### Electron 测试

```powershell
npm run test:electron
```

### Python 单元测试

```powershell
runtime\python\python.exe -m unittest discover -s tests
```

## 适合分发给谁

这版仓库更适合下面两种使用方式：

- 小组内部：直接拉仓库或直接拿安装包使用
- 普通使用者：只下载 `Setup 1.0.1.exe`，安装后直接运行

如果后续要对外公开分发，建议把安装包同时发布到 GitHub Releases，用户下载体验会比直接进仓库目录更好。
