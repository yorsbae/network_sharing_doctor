@echo off
rem Pasang autostart monitor saat login (hak terbatas, tanpa admin). Butuh NSD.exe.
setlocal
set "HERE=%~dp0"
set "EXE=%HERE%NSD.exe"
if not exist "%EXE%" set "EXE=%HERE%..\dist\NSD\NSD.exe"
if not exist "%EXE%" (echo NSD.exe tidak ditemukan. Jalankan scripts\build_windows.ps1 dahulu. & pause & exit /b 1)
"%EXE%" autostart install --mode logon-user %*
"%EXE%" autostart status
pause
