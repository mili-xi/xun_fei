@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   讯飞求职助手 - 环境初始化
echo ========================================
echo.

if not exist "runtime\python\python.exe" (
    echo [ERROR] 未找到 Python 运行时，请确认 runtime\python\ 目录完整。
    pause
    exit /b 1
)

echo [1/2] 检测 Python 运行时...
runtime\python\python.exe --version
if errorlevel 1 (
    echo [ERROR] Python 运行时异常
    pause
    exit /b 1
)

echo.
echo [2/2] 安装项目依赖...
runtime\python\python.exe -m pip install -r requirements.txt --no-warn-script-location -q
if errorlevel 1 (
    echo [ERROR] 依赖安装失败，请检查网络连接后重试
    pause
    exit /b 1
)

echo.
echo ========================================
echo   初始化完成！现在可以双击 "启动求职助手.bat" 启动软件
echo ========================================
echo.
pause
