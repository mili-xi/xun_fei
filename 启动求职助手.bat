@echo off
chcp 65001 >nul
cd /d "%~dp0"

title 讯飞求职助手

echo ========================================
echo   讯飞求职助手 v1.0
echo   正在启动服务...
echo ========================================
echo.

:: 检查 Python 运行时
if not exist "runtime\python\python.exe" (
    echo [ERROR] 未找到 Python 运行时
    echo 请先双击 setup.bat 完成初始化
    pause
    exit /b 1
)

:: 首次运行检测
if not exist "runtime\python\Lib\site-packages\flask" (
    echo [INFO] 首次运行，正在初始化...
    call setup.bat
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

:: 检查端口
set PORT=5000
set PORT_SEARCH_ATTEMPTS=20
set /a PORT_SEARCH_COUNT=0

:find_free_port
netstat -ano 2>nul | findstr ":%PORT% " | findstr "LISTENING" >nul
if errorlevel 1 goto port_ready
echo [WARNING] 端口 %PORT% 已被占用，继续查找可用端口...
set /a PORT+=1
set /a PORT_SEARCH_COUNT+=1
if %PORT_SEARCH_COUNT% geq %PORT_SEARCH_ATTEMPTS% (
    echo [ERROR] 连续尝试 %PORT_SEARCH_ATTEMPTS% 个端口后仍未找到可用端口。
    pause
    exit /b 1
)
goto find_free_port

:port_ready
echo [INFO] 使用端口 %PORT%

:: 启动后端
echo [INFO] 启动中...
start "" /B runtime\python\python.exe -c "import sys,os;sys.path[:0]=[os.path.abspath('后端'),os.path.abspath('.')]+sys.path;g={'__file__':os.path.abspath('后端/app.py'),'__name__':'__main__'};exec(open('后端/app.py',encoding='utf-8').read(),g)"

:: 等待服务就绪
:wait_loop
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:%PORT%/api/health | findstr /C:"\"status\":\"ok\"" >nul
if errorlevel 1 goto wait_loop

:: 打开浏览器
start "" "http://127.0.0.1:%PORT%/"

echo.
echo ========================================
echo   服务已启动！访问 http://127.0.0.1:%PORT%/
echo   关闭此窗口将停止服务
echo ========================================
echo.
pause >nul
