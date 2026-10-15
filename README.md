# Network Sharing Doctor (NSD)

Diagnosis **baca-saja** untuk masalah printer sharing dan folder sharing di Windows LAN. Fase 1:
tidak mengubah apa pun pada sistem; menjelaskan penyebab berdasarkan bukti dan menyarankan langkah.

- Visi & desain: [`vision.md`](vision.md) · Status: [`progres.md`](progres.md) · Keamanan: [`SECURITY.md`](SECURITY.md)

## Menjalankan
```bash
# Tanpa dependensi (CLI)
PYTHONPATH=src python -m nsd scan --role client --type folder --host SERVER01 --share Data --error 0x80070035
PYTHONPATH=src python -m nsd scan --host SERVER01 --share EPSON --type printer --json --out laporan.json
PYTHONPATH=src python -m nsd history | rules-validate | clear-history | settings

# GUI (butuh PySide6)
pip install -e ".[gui]" && python -m nsd
```
Di non-Windows, pemeriksaan khusus Windows ditandai **Belum diperiksa**; pemeriksaan jaringan (DNS, TCP) tetap berjalan.
Kode keluar `scan`: 0 = tidak ada pemeriksaan gagal, 1 = ada yang gagal, 2 = input tidak valid.

## Perbaikan (Fase 2, opsional, mati secara default)
```bash
nsd scan --type printer --host SERVER01 --share EPSON            # menghasilkan ID kasus
nsd repair --case <id> --rule PRN-SPOOLER-001                    # hanya menampilkan rencana
nsd settings --set execution_enabled=true                        # aktifkan eksplisit
nsd repair --case <id> --rule PRN-SPOOLER-001 --confirm          # snapshot → terapkan → verifikasi → scan ulang (sebagai Administrator)
nsd rollback --case <id> --action <n> --confirm
```
Saat ini hanya `start_service` (Spooler/Workstation/Server) yang didukung. Lihat SECURITY.md.

## Monitor latar belakang & autostart (opsional, baca-saja)
```bash
nsd monitor --host localhost --type both --interval 300         # jalan terus; status di <data>/status.json
nsd monitor --status | --once                                    # lihat status terakhir / satu putaran
nsd autostart install --mode logon-user --share DATA             # jalan saat logon (aman, default)
nsd autostart install --mode boot-system                         # jalan saat boot sebagai SYSTEM (admin + Program Files)
nsd autostart status | uninstall
```
Ini bukan "server" yang dibutuhkan agar sharing bekerja: berbagi printer/folder sudah autostart bawaan Windows. Monitor hanya memantau dan mencatat perubahan; autostart butuh build terpaket (`NSD.exe`).

## Tes
```bash
PYTHONPATH=src:. python -m unittest discover -s tests -t . -p 'test_*.py'
# Di VM Windows (menjalankan PowerShell asli; tes yang MENGUBAH layanan butuh NSD_RUN_MUTATING=1, VM lab saja):
python -m unittest tests.integration_windows.test_real_windows -v
```

## Prinsip
Diagnosis dulu, perubahan kemudian · kode error = petunjuk, bukan diagnosis · *belum diperiksa* ≠ *gagal* ·
tidak pernah mematikan firewall / mengaktifkan SMB1 / guest · laporan disamarkan secara default.
