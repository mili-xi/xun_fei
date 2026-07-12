@echo off
chcp 65001 >nul
cd /d "%~dp0"

set FLASK_DEBUG=0

if not exist "runtime\python\Lib\site-packages\flask" (
    rem bootstrap requirements.txt for first-run setup
    call setup.bat
    if errorlevel 1 exit /b 1
)

rem backend entry: 后端\app.py
rem default url: http://127.0.0.1:5000/

set PORT=5000
if not "%PORT%"=="" set PORT=%PORT%

start "" /B runtime\python\python.exe -c "import os,sys; os.environ['FLASK_DEBUG']=os.environ.get('FLASK_DEBUG','0'); sys.path[:0]=[os.path.abspath('后端'),os.path.abspath('.')]+sys.path; g={'__file__':os.path.abspath('后端\\app.py'),'__name__':'__main__'}; exec(open('后端\\app.py', encoding='utf-8').read(), g)"

:wait_loop
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:%PORT%/api/health | findstr /C:"\"status\":\"ok\"" >nul
if errorlevel 1 goto wait_loop

start "" "http://127.0.0.1:%PORT%/"
