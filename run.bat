@echo off
rem Start MyVocab on Windows: double-click this file or the MyVocab icon.
rem The first time, use install.bat instead: it does the same, and also shows
rem the setup page. If Python 3.12 is missing, it is installed first. run.py
rem does the rest. Keep this window open while you study; close it to stop.
cd /d "%~dp0"
title MyVocab

call :find_python
if defined PY goto start
echo [MyVocab] Python 3.12 is not on this computer yet, so it is being installed now (about 2 minutes).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\get_python.ps1"
call :find_python
if defined PY goto start
echo.
echo Python could not be installed automatically. Install it yourself from
echo https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo (tick "Add python.exe to PATH"), then double-click install.bat again.
pause
exit /b 1

:start
%PY% run.py %*
if errorlevel 1 pause
exit /b

rem The database package needs Python 3.12 or 3.11. Newer ones have no build of it yet.
rem A Python that was installed just now is not on this window's PATH yet, so its folder is checked too.
:find_python
set "PY="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PY exit /b
py -3.12 -c "" >nul 2>&1 && set "PY=py -3.12"
if defined PY exit /b
py -3.11 -c "" >nul 2>&1 && set "PY=py -3.11"
if defined PY exit /b
python -c "import sys; sys.exit(sys.version_info[:2] not in ((3, 11), (3, 12)))" >nul 2>&1 && set "PY=python"
exit /b
