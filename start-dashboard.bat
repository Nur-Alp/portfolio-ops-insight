@echo off
setlocal EnableDelayedExpansion
REM Double-click this file to open the OSIP dashboard.
REM First run needs internet access and takes a minute; later runs are fast.
cd /d "%~dp0"

REM Persist the launcher's own status messages (which branch of Python
REM detection/install ran, and why) to a plain-text file, in addition to the
REM console - the console window can close before a non-technical user can
REM read or copy an error, and re-running from an already-open Command
REM Prompt (the previous workaround) isn't always practical to ask for. This
REM does NOT capture scripts\launch.py's own live output (that would need a
REM tee/pipe through PowerShell, which is exactly the kind of cmd.exe
REM cleverness that already caused one real, hard-to-spot bug elsewhere in
REM this file) - launch.py's own progress still only appears in the console
REM and in .data\local-dashboard\server.log once it gets that far.
if not exist ".data\local-dashboard" mkdir ".data\local-dashboard" >nul 2>nul
set "LAUNCHER_LOG=%~dp0.data\local-dashboard\launcher.log"
echo. >> "%LAUNCHER_LOG%"
echo === start-dashboard.bat run: %DATE% %TIME% === >> "%LAUNCHER_LOG%"

REM Best-effort self-update: only if this is a real git checkout (not a plain
REM folder someone copied), and never fatal - no git, no network, or a
REM diverged local history just means "launch whatever is already here"
REM instead of blocking startup.
if exist ".git" (
  where git >nul 2>nul
  if not errorlevel 1 (
    echo Checking for dashboard updates...
    echo Checking for dashboard updates... >> "%LAUNCHER_LOG%"
    git pull --ff-only >nul 2>nul
    if errorlevel 1 (
      echo Could not check for updates ^(offline, or local files changed^) - continuing with what's already installed.
      echo Could not check for updates ^(offline, or local files changed^) - continuing with what's already installed. >> "%LAUNCHER_LOG%"
    ) else (
      echo Up to date.
      echo Up to date. >> "%LAUNCHER_LOG%"
    )
  )
)

call :find_working_python

REM Nothing else here needs installing: SQLite (the local database) ships
REM inside Python's own standard library, and the prebuilt frontend\dist\
REM bundle (tracked in this repo) means Node/npm are never required just to
REM run the dashboard. Python itself is the one real prerequisite.
if "%PYTHON%"=="" (
  echo Python was not found on this computer - installing it now ^(one-time, official build only^).
  echo Python was not found on this computer - installing it now ^(one-time, official build only^). >> "%LAUNCHER_LOG%"
  where winget >nul 2>nul
  if not errorlevel 1 (
    REM winget is Microsoft's own package manager, built into Windows 10
    REM ^(2004+^) and Windows 11. Python.Python.3.12 is the official CPython
    REM build from python.org, PSF-licensed - not a third-party repack.
    echo Installing Python via winget ^(this can take a few minutes^)...
    echo Installing Python via winget ^(this can take a few minutes^)... >> "%LAUNCHER_LOG%"
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    echo winget exit code: !errorlevel! >> "%LAUNCHER_LOG%"
  ) else (
    echo winget was not found; downloading the official python.org installer instead...
    echo winget was not found; downloading the official python.org installer instead... >> "%LAUNCHER_LOG%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $exe=Join-Path $env:TEMP 'osip-python-installer.exe'; Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile $exe; Start-Process -FilePath $exe -ArgumentList '/quiet','InstallAllUsers=0','PrependPath=1' -Wait"
    echo python.org installer exit code: !errorlevel! >> "%LAUNCHER_LOG%"
  )
  call :find_working_python
)

if "%PYTHON%"=="" (
  echo Python could not be installed automatically.
  echo Install it yourself from https://www.python.org/downloads/ and run this file again.
  echo IMPORTANT: during install, check "Add python.exe to PATH".
  echo Python could not be installed automatically. See %LAUNCHER_LOG% for what was tried.
  echo Python could not be installed automatically after every fallback. >> "%LAUNCHER_LOG%"
  pause
  exit /b 1
)
echo Using Python: %PYTHON% >> "%LAUNCHER_LOG%"

%PYTHON% scripts\launch.py start
if errorlevel 1 (
  echo.
  echo Something went wrong. See the messages above for details.
  echo scripts\launch.py start exited with code !errorlevel! >> "%LAUNCHER_LOG%"
  pause
  exit /b 1
)
echo scripts\launch.py start succeeded >> "%LAUNCHER_LOG%"
exit /b 0

:find_working_python
REM `where py`/`where python` alone isn't proof Python is usable: modern
REM Windows registers "App Execution Alias" stub executables for python.exe/
REM py.exe (in %LocalAppData%\Microsoft\WindowsApps, alongside winget.exe
REM itself) that `where` happily finds even when no real Python is
REM installed - running the stub just opens the Microsoft Store instead of
REM Python. Actually invoke each candidate and check it really works - and
REM check its version, not just that it runs: a Python that's already on
REM PATH but older than launch.py's own minimum (3.11) must be treated the
REM same as "no Python found" so the winget/python.org auto-install below
REM actually runs instead of silently deferring to launch.py's own version
REM check, which only fails with a manual-install message.
REM
REM The version check itself is a real .py file (scripts\_check_python_
REM version.py), not a `-c "sys.version_info >= (3, 11)"` one-liner: cmd.exe
REM treats `>`/`<` as redirection operators even inside double quotes, which
REM silently corrupted that comparison when passed inline - confirmed by a
REM real Windows CI run where winget successfully installed Python 3.12 at
REM exactly the expected fallback path below, yet the inline-`-c` version of
REM this check still failed to detect it.
REM
REM A PATH change made by an installer that ran during this same script is
REM also invisible to this already-running cmd.exe session (child processes
REM inherit the parent's environment block, not a live re-read of the
REM registry) - `where`/bare invocation can still fail right after a
REM successful install for that reason too, so this also checks the
REM installers' own fixed, well-known locations directly by path.
set PYTHON=
py -3 "%~dp0scripts\_check_python_version.py" >nul 2>nul
if not errorlevel 1 (
  set PYTHON=py -3
  exit /b 0
)
python "%~dp0scripts\_check_python_version.py" >nul 2>nul
if not errorlevel 1 (
  set PYTHON=python
  exit /b 0
)
for %%P in (
  "%LocalAppData%\Programs\Python\Python312\python.exe"
  "%LocalAppData%\Programs\Python\Python311\python.exe"
  "C:\Program Files\Python312\python.exe"
  "C:\Program Files\Python311\python.exe"
) do (
  if exist %%P (
    %%P "%~dp0scripts\_check_python_version.py" >nul 2>nul
    if not errorlevel 1 (
      set PYTHON=%%P
      exit /b 0
    )
  )
)
exit /b 0
