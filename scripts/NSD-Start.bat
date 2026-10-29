@echo off
rem Klik ganda: pasang autostart (sekali) + nyalakan monitor (server) + buka GUI (client).
rem Prioritas: NSD.exe di folder ini / ..\dist\NSD (build terpaket). Cadangan: Python + sumber.
setlocal
set "HERE=%~dp0"
if exist "%HERE%NSD.exe" (start "" "%HERE%NSD.exe" start %* & exit /b 0)
if exist "%HERE%..\dist\NSD\NSD.exe" (start "" "%HERE%..\dist\NSD\NSD.exe" start %* & exit /b 0)
set "PYTHONPATH=%HERE%..\src"
where pythonw >nul 2>&1
if %errorlevel%==0 (start "" pythonw -m nsd start %* & exit /b 0)
where python >nul 2>&1
if %errorlevel%==0 (start "" python -m nsd start %* & exit /b 0)
echo NSD.exe maupun Python tidak ditemukan. Jalankan scripts\build_windows.ps1 atau pasang Python 3.10+.
pause
exit /b 1
