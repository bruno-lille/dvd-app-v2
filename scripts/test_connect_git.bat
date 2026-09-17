@echo off
title Admin Import / Export

cd /d "%~dp0"

echo Lancement de l'application admin...
echo.

REM 🔥 ouvre le navigateur après 2 secondes
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5001"

REM lance Flask
py -3.11 test_connect_git.py

echo.
echo Appuyez sur une touche pour fermer...
pause > nul