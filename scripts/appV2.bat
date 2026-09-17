@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo DVD APP V2 - LANCEMENT LOCAL
echo ==========================================

REM Se placer a la racine de DVD_APP_V2
cd /d "%~dp0.."

echo.
echo [1/5] Verification de app.py

if not exist "app.py" (
    echo [ERREUR] app.py est introuvable.
    echo.
    echo Lance d'abord la procedure de creation de app.py depuis app_dev.py.
    pause
    exit /b 1
)

echo [OK] app.py trouve.

echo.
echo [2/5] Arret des anciens processus Python

taskkill /F /IM python.exe >nul 2>&1

echo [OK] Anciens processus Python arretes si necessaire.

echo.
echo [3/5] Configuration de l'environnement DEV

set ENV=DEV

echo [OK] ENV=%ENV%

echo.
echo [4/5] Demarrage de app.py

start "DVD APP V2 - SERVEUR" cmd /k python app.py

timeout /t 2 /nobreak >nul

echo.
echo [5/5] Ouverture de l'application

start "" chrome --incognito http://127.0.0.1:5000

echo.
echo ==========================================
echo DVD APP V2 demarree
echo http://127.0.0.1:5000
echo ==========================================
echo.
echo La fenetre du serveur Python reste ouverte
echo pour permettre de voir les messages et erreurs.
echo.
pause
