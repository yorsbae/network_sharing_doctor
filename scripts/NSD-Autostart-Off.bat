@echo off
setlocal
set "HERE=%~dp0"
set "EXE=%HERE%NSD.exe"
if not exist "%EXE%" set "EXE=%HERE%..\dist\NSD\NSD.exe"
if not exist "%EXE%" (echo NSD.exe tidak ditemukan. & pause & exit /b 1)
"%EXE%" autostart uninstall
pause
