@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Project virtual environment not found at .venv.
    echo Create or select the project's virtual environment in PyCharm first.
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

".venv\Scripts\pyside6-deploy.exe" main.py --mode standalone
if errorlevel 1 exit /b %errorlevel%

echo Build complete. See the dist folder.
