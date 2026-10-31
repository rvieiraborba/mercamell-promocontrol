@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if %errorlevel%==0 (
 py -3 app.py
 goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
 python app.py
 goto :end
)
echo Python 3 nao encontrado. Instale em https://www.python.org/downloads/windows/
echo Em seguida, execute este arquivo novamente.
:end
pause