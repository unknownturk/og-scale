@echo off
rem Startet OG Scale zum Ausprobieren auf dem eigenen Rechner (Windows).
rem Testbetrieb: Platzhalter-Bilder und nachgestellte Handys, es kostet nichts
rem und postet nichts. Braucht Python 3.11+, Node 20+ und ffmpeg.
cd /d "%~dp0"
for %%T in (python node npm ffmpeg) do (
  where %%T >nul 2>nul || (echo Es fehlt: %%T. Bitte zuerst installieren. & pause & exit /b 1)
)
echo Richte das Backend ein ...
if not exist backend\.venv\Scripts\pip.exe python -m venv backend\.venv
backend\.venv\Scripts\pip install -q -r backend\requirements.txt || (pause & exit /b 1)
echo Richte das Frontend ein ...
pushd frontend
call npm install --no-audit --no-fund --silent || (pause & exit /b 1)
popd
set BACKEND_API_KEY=demo-geheimnis
set MEDIA_PROVIDER=fake
set DEMO_SEED=1
set ALI_TICK_SECONDS=10
start "OG Scale Backend" /d backend cmd /k ".venv\Scripts\python -m uvicorn app.main:app --port 8000 --log-level warning"
set BACKEND_URL=http://localhost:8000
set APP_PASSWORD=demo
set AUTH_SECRET=nur-fuer-die-demo-0123456789
start "OG Scale Frontend" /d frontend cmd /k "npm run dev -- -p 3000"
echo.
echo   OG Scale laeuft gleich unter  http://localhost:3000   (Passwort: demo)
echo   Zum Beenden die beiden neuen Fenster schliessen.
timeout /t 8 >nul
start http://localhost:3000
