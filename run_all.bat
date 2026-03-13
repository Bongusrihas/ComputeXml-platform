@echo off
setlocal

set ROOT=%~dp0

echo Starting Computex services from %ROOT%

echo [1/3] Backend
start "Computex Backend" cmd /k "cd /d %ROOT%backend && if not exist node_modules npm install && npm run dev"

echo [2/3] Python Service
start "Computex Python" cmd /k "cd /d %ROOT%python_service && if not exist .venv (py -3.11 -m venv .venv) && call .venv\Scripts\activate && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [3/3] Frontend
start "Computex Frontend" cmd /k "cd /d %ROOT%frontend && if not exist node_modules npm install && npm run dev"

echo All services launched in separate terminals.
endlocal
