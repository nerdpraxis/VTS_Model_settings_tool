@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=py"
where py >nul 2>nul || set "PY=python"

if not exist "venv\" (
  echo [1/4] Creating Python venv in .\venv
  %PY% -3.11 -m venv venv 2>nul
  if errorlevel 1 %PY% -m venv venv
  if errorlevel 1 (
    echo Failed to create venv. Install Python 3.11+ and ensure it is on PATH.
    exit /b 1
  )
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
  echo Could not activate venv\Scripts\activate.bat
  exit /b 1
)

echo [2/4] pip install runtime + PyInstaller
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 exit /b 1
pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [3/4] PyInstaller (onefile, windowed GUI, entry main.py)
pyinstaller --noconfirm --clean --windowed --onefile ^
  --name VTSModelSettingsTool ^
  --hidden-import vts_mst.tree_diff ^
  --hidden-import vts_mst.diff_core ^
  --hidden-import vts_mst.parameter_extract ^
  --hidden-import vts_mst.parameter_compare ^
  --hidden-import vts_mst.parameter_copy_planner ^
  --hidden-import vts_mst.parameter_copy_wizard ^
  main.py
if errorlevel 1 exit /b 1

echo.
echo [4/4] Done. Executable:
echo   %CD%\dist\VTSModelSettingsTool.exe
echo Copy config.ini.example to config.ini next to the EXE if needed, or run once to create defaults — see README.md.
endlocal
exit /b 0
