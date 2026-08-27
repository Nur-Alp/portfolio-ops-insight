@echo off
REM Double-click this file to open the OSIP dashboard.
REM First run needs internet access and takes a minute; later runs are fast.
cd /d "%~dp0"

REM Best-effort self-update: only if this is a real git checkout (not a plain
REM folder someone copied), and never fatal - no git, no network, or a
REM diverged local history just means "launch whatever is already here"
REM instead of blocking startup.
if exist ".git" (
  where git >nul 2>nul
  if not errorlevel 1 (
    echo Checking for dashboard updates...
    git pull --ff-only >nul 2>nul
    if errorlevel 1 (
      echo Could not check for updates ^(offline, or local files changed^) - continuing with what's already installed.
    ) else (
      echo Up to date.
    )
  )
)

set PYTHON=
where py >nul 2>nul && set PYTHON=py -3
if "%PYTHON%"=="" (
  where python >nul 2>nul && set PYTHON=python
)

if "%PYTHON%"=="" (
  echo Python was not found on this computer.
  echo Install it from https://www.python.org/downloads/ and run this file again.
  echo IMPORTANT: during install, check "Add python.exe to PATH".
  pause
  exit /b 1
)

%PYTHON% scripts\launch.py start
if errorlevel 1 (
  echo.
  echo Something went wrong. See the messages above for details.
  pause
  exit /b 1
)
exit /b 0
