@echo off
setlocal
set "BACKEND_ROOT=%~dp0"
set "VENV_PYTHON=%BACKEND_ROOT%.venv\Scripts\python.exe"

if /I "%~1"=="--bootstrap" (
  shift
  where python >nul 2>nul
  if errorlevel 1 goto :python_missing
  if not exist "%VENV_PYTHON%" python -m venv "%BACKEND_ROOT%.venv"
  if errorlevel 1 goto :command_failed
  "%VENV_PYTHON%" -m pip install --upgrade pip
  if errorlevel 1 goto :command_failed
  "%VENV_PYTHON%" -m pip install -r "%BACKEND_ROOT%requirements.txt"
  if errorlevel 1 goto :command_failed
)

if not exist "%VENV_PYTHON%" (
  echo backend\.venv is missing. Run test.cmd --bootstrap once. 1>&2
  exit /b 1
)

pushd "%BACKEND_ROOT%"
"%VENV_PYTHON%" -m pytest %*
set "TEST_EXIT=%errorlevel%"
popd
exit /b %TEST_EXIT%

:python_missing
echo Python 3.11+ is required. Install it, then rerun test.cmd --bootstrap. 1>&2
exit /b 1

:command_failed
exit /b 1
