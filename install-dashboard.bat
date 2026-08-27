@echo off
REM Send just this one file to someone to give them the dashboard. Double-click
REM it once to install; after that, use start-dashboard.bat inside the
REM installed folder (it self-updates on every launch - see that file).

set REPO_URL=https://github.com/Nur-Alp/portfolio-ops-insight.git
set TARGET_DIR=%USERPROFILE%\PortfolioOpsInsight-Dashboard

where git >nul 2>nul
if errorlevel 1 (
  echo Git was not found on this computer.
  echo Install it from https://git-scm.com/download/win and run this file again.
  pause
  exit /b 1
)

if exist "%TARGET_DIR%\.git" (
  echo Dashboard already installed at %TARGET_DIR% - starting it...
) else (
  echo Installing the dashboard to %TARGET_DIR% ...
  git clone "%REPO_URL%" "%TARGET_DIR%"
  if errorlevel 1 (
    echo.
    echo Could not download the dashboard. This is a private repository - you need
    echo read access to it first:
    echo   %REPO_URL%
    echo Ask to be added as a collaborator, then run this file again.
    pause
    exit /b 1
  )
)

cd /d "%TARGET_DIR%"
call start-dashboard.bat
exit /b %errorlevel%
