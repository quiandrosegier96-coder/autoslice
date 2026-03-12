@echo off
SET PATH=C:\Program Files\nodejs;C:\Users\QUANT\AppData\Local\Programs\Python\Python312;C:\Users\QUANT\AppData\Local\Programs\Python\Python312\Scripts;%PATH%

echo Starting AutoSlice Backend (poort 8000)...
start "AutoSlice Backend" cmd /k "cd /d C:\Users\QUANT\GitHub\AutoSlice_GITPPORN\autoslice\backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo Wacht 3 seconden...
timeout /t 3 /nobreak >nul

echo Starting AutoSlice Frontend (poort 3000)...
start "AutoSlice Frontend" cmd /k "cd /d C:\Users\QUANT\GitHub\AutoSlice_GITPPORN\autoslice\frontend && npm run dev -- --hostname 0.0.0.0"

echo.
echo ================================
echo  AutoSlice is publiek bereikbaar
echo  http://178.117.208.226:3000
echo ================================
pause
