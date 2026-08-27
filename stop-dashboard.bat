@echo off
REM Double-click this file to stop the OSIP dashboard.
cd /d "%~dp0"

set PYTHON=
where py >nul 2>nul && set PYTHON=py -3
if "%PYTHON%"=="" (
  where python >nul 2>nul && set PYTHON=python
)

if "%PYTHON%"=="" (
  echo Python was not found on this computer.
  pause
  exit /b 1
)

%PYTHON% scripts\launch.py stop
if errorlevel 1 (
  echo.
  echo Something went wrong. See the messages above for details.
  pause
  exit /b 1
)
exit /b 0
