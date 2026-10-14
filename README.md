# Network Sharing Doctor (NSD)

Diagnosis **baca-saja** untuk masalah printer sharing dan folder sharing di Windows LAN. Fase 1:
tidak mengubah apa pun pada sistem; menjelaskan penyebab berdasarkan bukti dan menyarankan langkah.

- Visi & desain: [`vision.md`](vision.md) · Status: [`progres.md`](progres.md) · Keamanan: [`SECURITY.md`](SECURITY.md)

## Menjalankan
```bash
# Tanpa dependensi (CLI)
PYTHONPATH=src python -m nsd scan --role client --type folder --host SERVER01 --share Data --error 0x80070035
PYTHONPATH=src python -m nsd scan --host SERVER01 --share EPSON --type printer --json --out laporan.json
PYTHONPATH=src python -m nsd history | rules-validate | clear-history

# Ukuran kertas khusus di client (lokal, tanpa server)
PYTHONPATH=src python -m nsd paper add --name "F4 Kantor" --width 210 --height 330
PYTHONPATH=src python -m nsd paper list | layout --paper "F4 Kantor" --margin 12 | remove --name "F4 Kantor"

# GUI: Diagnosa → Cetak… membuka popup Print Layout (printer, kertas, margin, pratinjau)
#      Kertas & Layout → Cetak halaman uji… untuk memeriksa ukuran dengan penggaris
# GUI (butuh PySide6)
pip install -e ".[gui]" && python -m nsd
```
Di non-Windows, pemeriksaan khusus Windows ditandai **Belum diperiksa**; pemeriksaan jaringan (DNS, TCP) tetap berjalan.
Kode keluar `scan`: 0 = tidak ada pemeriksaan gagal, 1 = ada yang gagal, 2 = input tidak valid.

## Tes
```bash
PYTHONPATH=src:. python -m unittest discover -s tests -t . -p 'test_*.py'
# Di VM Windows (menjalankan PowerShell asli):
python -m unittest tests.integration_windows.test_real_windows -v
```

## Prinsip
Diagnosis dulu, perubahan kemudian · kode error = petunjuk, bukan diagnosis · *belum diperiksa* ≠ *gagal* ·
tidak pernah mematikan firewall / mengaktifkan SMB1 / guest · laporan disamarkan secara default.
