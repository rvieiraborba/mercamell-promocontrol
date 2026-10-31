@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if %errorlevel%==0 (
 py -3 app.py --demo
 goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
 python app.py --demo
 goto :end
)
echo Python 3 nao encontrado.
:end
pause