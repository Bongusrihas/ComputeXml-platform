@echo off
setlocal

set ROOT=%~dp0
set ENGINE_RELEASE=%ROOT%cpp_engine\build\Release\engine.exe
set ENGINE_DEBUG=%ROOT%cpp_engine\build\engine.exe
set ENGINE_RELEASE_WIN32=%ROOT%cpp_engine\build_win32\Release\engine.exe
set ENGINE_DEBUG_WIN32=%ROOT%cpp_engine\build_win32\engine.exe
set ENGINE_PATH=%ENGINE_RELEASE%

if not exist "%ENGINE_PATH%" (
  set ENGINE_PATH=%ENGINE_DEBUG%
)

if not exist "%ENGINE_PATH%" (
  set ENGINE_PATH=%ENGINE_RELEASE_WIN32%
)

if not exist "%ENGINE_PATH%" (
  set ENGINE_PATH=%ENGINE_DEBUG_WIN32%
)

echo Starting local Computex services from %ROOT%
echo Make sure MongoDB is running on mongodb://localhost:27017/

echo [1/2] Python Service
start "Computex Python" cmd /k "cd /d %ROOT%python_service && if not exist .venv py -3.13 -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && set CPLUS_ENGINE_PATH=%ENGINE_PATH% && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [2/2] Backend + Frontend
start "Computex Backend" cmd /k "cd /d %ROOT%backend && npm install && node src/server.js"

timeout /t 3 >nul
start "" http://localhost:4000

echo Browser opened at http://localhost:4000
endlocal
