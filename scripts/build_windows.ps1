# Build portabel (PyInstaller --onedir). Jalankan di Windows dari root proyek.
# Belum diuji; verifikasi hasil pada VM Windows bersih tanpa Python (vision.md B.13, Packaging tests).
$ErrorActionPreference = 'Stop'
python -m pip install -e ".[gui,build]"
python -m pyinstaller --noconfirm --clean --onedir --windowed --name NSD `
  --paths src --add-data "rules;rules" src\nsd\__main__.py
# Peluncur satu klik di samping NSD.exe (klik ganda = autostart + monitor + GUI).
Copy-Item scripts\NSD-Start.bat, scripts\NSD-Autostart-On.bat, scripts\NSD-Autostart-Off.bat dist\NSD\
# Mode portabel (data di folder 'data' di samping exe): buat berkas portable.flag.
# New-Item dist\NSD\portable.flag -ItemType File
Write-Host "Selesai: dist\NSD\NSD.exe (klik ganda) atau dist\NSD\NSD-Start.bat"
