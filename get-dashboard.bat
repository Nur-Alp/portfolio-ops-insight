@echo off
REM Share this file with a non-technical Windows user. Double-clicking it
REM downloads the dashboard into Downloads and starts the existing launcher.
setlocal

set "REPO_URL=https://github.com/Nur-Alp/portfolio-ops-insight.git"
set "ARCHIVE_URL=https://github.com/Nur-Alp/portfolio-ops-insight/archive/refs/heads/main.zip"
set "TARGET=%USERPROFILE%\Downloads\portfolio-operations-dashboard"

if not exist "%USERPROFILE%\Downloads" mkdir "%USERPROFILE%\Downloads"

if exist "%TARGET%\.git" goto update
if exist "%TARGET%\start-dashboard.bat" goto start
if exist "%TARGET%" goto bad_target

where git >nul 2>nul
if not errorlevel 1 goto clone

echo Git was not found. Downloading a repository archive instead...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $tmp=Join-Path $env:TEMP ('portfolio-dashboard-'+[guid]::NewGuid()); New-Item -ItemType Directory -Path $tmp | Out-Null; try { $zip=Join-Path $tmp 'dashboard.zip'; Invoke-WebRequest -UseBasicParsing -Uri $env:ARCHIVE_URL -OutFile $zip; Expand-Archive -LiteralPath $zip -DestinationPath $tmp; $dir=Get-ChildItem -LiteralPath $tmp -Directory | Where-Object { $_.Name -like 'portfolio-ops-insight-*' } | Select-Object -First 1; if (-not $dir) { throw 'The downloaded archive had an unexpected structure.' }; Move-Item -LiteralPath $dir.FullName -Destination $env:TARGET } finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }"
if errorlevel 1 goto failed
goto start

:clone
echo Downloading the dashboard into Downloads...
git clone --depth 1 "%REPO_URL%" "%TARGET%"
if errorlevel 1 goto failed
goto start

:update
echo An existing dashboard was found. Updating it...
git -C "%TARGET%" pull --ff-only
if errorlevel 1 goto failed
goto start

:bad_target
echo %TARGET% already exists but is not a Git checkout.
echo Rename or remove that folder, then run this file again.
goto failed

:start
if not exist "%TARGET%\start-dashboard.bat" goto failed
echo Starting the dashboard...
call "%TARGET%\start-dashboard.bat"
exit /b %errorlevel%

:failed
echo.
echo Dashboard setup failed. Check the messages above and try again.
pause
exit /b 1
