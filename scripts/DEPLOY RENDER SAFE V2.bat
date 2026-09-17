@echo off
setlocal
chcp 65001 >nul

:: ============================================================
:: DVD APP V2
:: DEPLOY RENDER SAFE
::
:: Workflow :
:: app_dev.py -> app.py -> test local -> validation
:: -> git commit -> GitHub -> Render
::
:: ATTENTION :
:: - La base V2 est collection.db
:: - Ne jamais remplacer collection.db par une base distante
:: - Le script ne modifie pas la base de données
:: ============================================================

cd /d "%~dp0.."

echo.
echo ============================================================
echo              DVD APP V2 - DEPLOY RENDER SAFE
echo ============================================================
echo.

:: ------------------------------------------------------------
:: 1 - Verification de app.py
:: ------------------------------------------------------------
if not exist "app.py" (
    echo [ERREUR] app.py est introuvable.
    echo.
    echo Lance d'abord :
    echo scripts\DEPLOY LOCAL AVEC APP.PYV2.bat
    echo.
    pause
    exit /b 1
)

echo [OK] app.py trouve.

:: ------------------------------------------------------------
:: 2 - Verification de collection.db
:: ------------------------------------------------------------
if not exist "database\collection.db" (
    echo [ERREUR] database\collection.db est introuvable.
    echo.
    echo Le deploiement est interrompu par securite.
    echo.
    pause
    exit /b 1
)

echo [OK] database\collection.db trouve.

:: ------------------------------------------------------------
:: 3 - Verification Git
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
:: 4 - Verification du remote
:: ------------------------------------------------------------
for /f "delims=" %%i in ('git remote get-url origin 2^>nul') do set REMOTE_URL=%%i

echo [INFO] Remote GitHub :
echo %REMOTE_URL%
echo.

echo ============================================================
echo VERIFICATION AVANT DEPLOIEMENT
echo ============================================================
echo.

:: ------------------------------------------------------------
:: 5 - Protection de collection.db
:: ------------------------------------------------------------
git diff --cached --name-only | findstr /i /x "database/collection.db" >nul
if not errorlevel 1 (
    echo [ERREUR] collection.db est deja staged dans Git.
    echo.
    echo Le deploiement est interrompu par securite.
    echo La base V2 ne doit pas etre envoyee par ce script.
    echo.
    pause
    exit /b 1
)

echo [OK] collection.db n'est pas staged.

:: ------------------------------------------------------------
:: 6 - Recuperation des changements distants
:: ------------------------------------------------------------
echo.
echo [1/4] Synchronisation avec GitHub...
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
:: 7 - Verification finale avant ajout
:: ------------------------------------------------------------
echo.
echo [2/4] Verification des fichiers...

git status --short

echo.
echo ============================================================
echo IMPORTANT
echo ============================================================
echo.
echo Le script va preparer les fichiers modifies pour Git.
echo collection.db reste exclue du deployement.
echo.
echo Si quelque chose semble anormal, ferme cette fenetre.
echo.

pause

:: ------------------------------------------------------------
:: 8 - Ajout des fichiers
:: ------------------------------------------------------------
echo.
echo [3/4] Preparation du commit...

git add .

if errorlevel 1 (
    echo [ERREUR] git add a echoue.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 9 - Verification SECURITE collection.db
:: ------------------------------------------------------------
git diff --cached --name-only | findstr /i /x "database/collection.db" >nul
if not errorlevel 1 (
    echo.
    echo [ERREUR DE SECURITE] collection.db serait envoyee vers GitHub.
    echo.
    git restore --staged "database/collection.db"
    echo [INFO] collection.db a ete retiree du staging.
    echo Aucun push ne sera effectue.
    echo.
    pause
    exit /b 1
)

echo [OK] collection.db protegee.

:: ------------------------------------------------------------
:: 10 - Verification qu'il y a quelque chose a committer
:: ------------------------------------------------------------
git diff --cached --quiet
if not errorlevel 1 (
    echo.
    echo [INFO] Aucun changement a committer.
    echo.
    pause
    exit /b 0
)

echo.
echo Fichiers qui seront committes :
git diff --cached --name-only

echo.
set /p COMMIT_MSG=Message du commit : 

if "%COMMIT_MSG%"=="" set COMMIT_MSG=DVD APP V2 - mise a jour

git commit -m "%COMMIT_MSG%"

if errorlevel 1 (
    echo.
    echo [ERREUR] Le commit a echoue.
    echo Aucun push n'est effectue.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 11 - Push GitHub
:: ------------------------------------------------------------
echo.
echo [4/4] Push vers GitHub...
git push origin main

if errorlevel 1 (
    echo.
    echo [ERREUR] Le push GitHub a echoue.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo                 DEPLOIEMENT V2 TERMINE
echo ============================================================
echo.
echo GitHub a ete mis a jour.
echo Render pourra recuperer cette version selon sa configuration.
echo.
echo Base protegee :
echo database\collection.db
echo.
pause
