@echo off
rem MyVocab setup for Windows: double-click this one file. It downloads MyVocab
rem (or updates it), finds a backup of your words, installs Python if needed,
rem asks for your keys and puts a MyVocab icon on the desktop.
rem The steps are in tools\windows_setup.ps1 on GitHub, so this file never changes.
title MyVocab setup
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; iex (irm 'https://raw.githubusercontent.com/ntuanh/MyVocab/main/tools/windows_setup.ps1')"
if errorlevel 1 (
    echo.
    echo The setup stopped. Check the internet connection and run MyVocab-Setup again.
    pause
)
