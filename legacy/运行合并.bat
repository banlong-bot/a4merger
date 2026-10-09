@echo off
rem ------------------------------------------------------------------
rem  Double-click launcher for merge_to_a4_wps.py (WPS based merger).
rem  Keep this file ASCII-only: cmd.exe reads .bat with the console
rem  code page, and all Chinese messages are printed by Python itself.
rem ------------------------------------------------------------------
setlocal
set "HERE=%~dp0"
set "PY="

for %%D in (
  "%LOCALAPPDATA%\Programs\Python\Python313"
  "%LOCALAPPDATA%\Programs\Python\Python312"
  "%LOCALAPPDATA%\Programs\Python\Python311"
  "%LOCALAPPDATA%\Programs\Python\Python310"
  "%ProgramFiles%\Python313"
  "%ProgramFiles%\Python312"
  "C:\Python313"
  "C:\Python312"
) do (
  if not defined PY if exist "%%~D\python.exe" set "PY=%%~D\python.exe"
)

if not defined PY (
  for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY (
      "%%~P" -c "import sys" >nul 2>nul && set "PY=%%~P"
    )
  )
)

if not defined PY (
  echo.
  echo   Python not found. Please install Python 3 first.
  echo   ^(No usable python.exe on this computer^)
  echo.
  pause
  exit /b 1
)

set "PYTHONIOENCODING=utf-8"
"%PY%" "%HERE%merge_to_a4_wps.py" %*
echo.
pause
