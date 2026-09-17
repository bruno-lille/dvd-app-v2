@echo off
setlocal
chcp 65001 >nul

:: ============================================================
:: DVD APP V2
:: COPIE VERS APP.PY - AVEC PUSH
::
:: Workflow :
:: app_dev.py -> app.py -> test local -> validation
:: -> GitHub
::
:: IMPORTANT :
:: collection.db n'existe pas encore.
:: Elle sera creee par Codex lors de la construction de V2.
::
:: ATTENTION :
:: La commande "git add ." est volontairement COMMENTEE.
:: Elle devra etre definie et mise en place lorsque la structure
:: V2 et la gestion de collection.db seront validees.
::
:: Ce script NE pousse donc rien tant que cette etape n'est pas
:: explicitement mise en place.
:: ============================================================

cd /d "%~dp0.."

echo.
echo ============================================================
echo          DVD APP V2 - COPIE VERS APP.PY + PUSH
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
:: 3 - Sauvegarde locale
:: ------------------------------------------------------------
if not exist "local_backups" mkdir "local_backups"

copy /Y "app_dev.py" "local_backups\%timestamp%_app_dev.py" >nul

if errorlevel 1 (
    echo [ERREUR] Sauvegarde de app_dev.py impossible.
    echo.
    pause
    exit /b 1
)

echo [OK] Sauvegarde de app_dev.py creee.

:: ------------------------------------------------------------
:: 4 - Creation de app.py
:: ------------------------------------------------------------
copy /Y "app_dev.py" "app.py" >nul

if errorlevel 1 (
    echo [ERREUR] Creation de app.py impossible.
    echo.
    pause
    exit /b 1
)

echo [OK] app.py cree.

:: ------------------------------------------------------------
:: 5 - Injection du BUILD
:: ------------------------------------------------------------
powershell -NoProfile -Command "(Get-Content -Raw 'app.py') -replace 'APP_BUILD = ""DEV_BUILD""', 'APP_BUILD = ""%timestamp%""' | Set-Content -Encoding UTF8 'app.py'"

if errorlevel 1 (
    echo [ERREUR] Mise a jour de APP_BUILD impossible.
    echo.
    pause
    exit /b 1
)

echo [OK] APP_BUILD = %timestamp%

:: ------------------------------------------------------------
:: 6 - Sauvegarde de app.py
:: ------------------------------------------------------------
copy /Y "app.py" "local_backups\%timestamp%_app.py" >nul

if errorlevel 1 (
    echo [ERREUR] Sauvegarde de app.py impossible.
    echo.
    pause
    exit /b 1
)

echo [OK] Sauvegarde de app.py creee.

:: ------------------------------------------------------------
:: 7 - Verification Git
:: ------------------------------------------------------------
git rev-parse --is-inside-work-tree >nul 2>&1

if errorlevel 1 (
    echo [ERREUR] Ce dossier n'est pas un depot Git.
    echo.
    pause
    exit /b 1
)

echo [OK] Depot Git detecte.

:: ------------------------------------------------------------
:: 8 - Verification du remote
:: ------------------------------------------------------------
for /f "delims=" %%i in ('git remote get-url origin 2^>nul') do set REMOTE_URL=%%i

echo [INFO] Remote :
echo %REMOTE_URL%
echo.

:: ------------------------------------------------------------
:: 9 - Synchronisation GitHub
:: ------------------------------------------------------------
echo [INFO] Synchronisation avec GitHub...
git pull --rebase origin main

if errorlevel 1 (
    echo.
    echo [ERREUR] git pull --rebase a echoue.
    echo Aucun push n'est effectue.
    echo.
    pause
    exit /b 1
)

echo [OK] Depot local synchronise.

:: ------------------------------------------------------------
:: 10 - GIT ADD : A METTRE EN PLACE
:: ------------------------------------------------------------
echo.
echo ============================================================
echo                    GIT ADD A METTRE EN PLACE
echo ============================================================
echo.
echo La commande git add est volontairement desactivee.
echo.
echo collection.db n'existe pas encore.
echo Codex doit d'abord creer la structure V2 et definir
echo precisement quels fichiers doivent etre suivis par Git.
echo.
echo IMPORTANT :
echo Ne pas utiliser "git add ." aveuglement avant validation.
echo La gestion de collection.db doit etre definie.
echo.
echo A FAIRE PLUS TARD :
echo - definir les fichiers a ajouter
echo - definir le traitement de collection.db
echo - mettre en place la commande git add adaptee
echo - puis activer le commit et le push
echo.
echo ============================================================
echo.

:: ------------------------------------------------------------
:: 11 - Commandes volontairement desactivees
:: ------------------------------------------------------------
:: git add .
:: git commit -m "DVD APP V2 - %timestamp%"
:: git push origin main

echo [INFO] Aucun git add effectue.
echo [INFO] Aucun commit effectue.
echo [INFO] Aucun push effectue.
echo.
echo Le script s'arrete volontairement ici.
echo.
pause
