@echo off
rem Save all your words, topics, scores and writing to the backup folder:
rem double-click this file. To move MyVocab to another computer, copy the
rem backup folder and the .env file along with it.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Start MyVocab once with run.bat first, then make a backup.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tools\local_db.py backup
if errorlevel 1 ( pause & exit /b 1 )
explorer backup
echo.
echo Done. Your backup is in the folder that just opened.
pause
