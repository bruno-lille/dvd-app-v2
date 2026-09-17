@echo off
setlocal
chcp 65001 >nul

:: ============================================================
:: DVD APP V2
:: DEPLOY LOCAL AVEC APP.PY
::
:: Workflow :
:: app_dev.py -> app.py -> test local
:: ============================================================

:: Se placer a la racine de DVD_APP_V2
cd /d "%~dp0.."

echo.
echo ============================================================
echo                 DVD APP V2 - BUILD LOCAL
echo ============================================================
echo.

:: ------------------------------------------------------------
:: 1 - Verification de app_dev.py
:: ------------------------------------------------------------
if not exist "app_dev.py" (
    echo [ERREUR] app_dev.py est introuvable.
    echo.
    pause
    exit /b 1
)

echo [OK] app_dev.py trouve.

:: ------------------------------------------------------------
:: 2 - Horodatage
:: ------------------------------------------------------------
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set timestamp=%%i

:: ------------------------------------------------------------
:: 3 - Creation du dossier de sauvegarde
:: ------------------------------------------------------------
if not exist "local_backups" mkdir "local_backups"

:: ------------------------------------------------------------
:: 4 - Sauvegarde de app_dev.py
:: ------------------------------------------------------------
copy /Y "app_dev.py" "local_backups\%timestamp%_app_dev.py" >nul

if errorlevel 1 (
    echo [ERREUR] Sauvegarde de app_dev.py impossible.
    pause
    exit /b 1
)

echo [OK] Sauvegarde app_dev.py creee.

:: ------------------------------------------------------------
:: 5 - Copie app_dev.py -> app.py
:: ------------------------------------------------------------
copy /Y "app_dev.py" "app.py" >nul

if errorlevel 1 (
    echo [ERREUR] Creation de app.py impossible.
    pause
    exit /b 1
)

echo [OK] app.py cree.

:: ------------------------------------------------------------
:: 6 - Injection du BUILD
:: ------------------------------------------------------------
powershell -NoProfile -Command "(Get-Content -Raw 'app.py') -replace 'APP_BUILD = ""DEV_BUILD""', 'APP_BUILD = ""%timestamp%""' | Set-Content -Encoding UTF8 'app.py'"

if errorlevel 1 (
    echo [ERREUR] Mise a jour de APP_BUILD impossible.
    pause
    exit /b 1
)

echo [OK] APP_BUILD = %timestamp%

:: ------------------------------------------------------------
:: 7 - Sauvegarde de app.py
:: ------------------------------------------------------------
copy /Y "app.py" "local_backups\%timestamp%_app.py" >nul

if errorlevel 1 (
    echo [ERREUR] Sauvegarde de app.py impossible.
    pause
    exit /b 1
)

echo [OK] Sauvegarde app.py creee.

:: ------------------------------------------------------------
:: FIN
:: ------------------------------------------------------------
echo.
echo ============================================================
echo                    BUILD V2 TERMINE
echo ============================================================
echo.
echo app_dev.py -> app.py
echo BUILD       -> %timestamp%
echo.
echo Vous pouvez maintenant lancer :
echo scripts\appV2.bat
echo.
pause
