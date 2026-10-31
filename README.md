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

## Tampilan
Menu: Dashboard, Server, Client, Scan printer, Kode error, Daftar printer, Antrean cetak, Kertas, Log, Pengaturan. Arah desain dan pagar anti-slop ada di [`DESIGN.md`](DESIGN.md).

## Server dan client: cara memakainya
**Server** = komputer yang printernya terpasang dan dibagikan. **Client** = komputer lain yang mencetak ke printer itu.
**Tidak ada program server yang harus dijalankan**: Windows sendiri melayani client selama printer dibagikan serta layanan
Print Spooler dan Server berjalan. NSD hanya memeriksa dan memandu. Di Dashboard, klik **Server** atau **Client** sesuai peran komputer itu.

Di komputer **server** (menu Server):
1. Lihat daftar kesiapan: Print Spooler, layanan Server, profil jaringan, firewall File and Printer Sharing, printer dibagikan.
2. Untuk yang berstatus *Berhenti*, *Nonaktif*, atau *Belum dibagikan*, ikuti "Yang bisa dilakukan" di bawahnya, lalu klik **Periksa ulang**.
3. Bila *Siap dipakai client*, klik **Salin alamat** (`\\NAMA-KOMPUTER\NamaPrinter`) atau **Salin petunjuk untuk client** lalu kirim ke pengguna.
4. Komputer server harus menyala dan tersambung ke jaringan saat client mencetak.

Di komputer **client** (menu Client):
1. **Pilih server**: klik *Cari server di jaringan* (memeriksa port 445 di jaringan lokal, hanya saat diklik) atau ketik nama/alamat IP server.
2. **Pilih printer atau folder**: klik *Lihat printer di server* lalu pilih printernya. Untuk folder, ketik nama share dari pemilik server.
3. **Periksa koneksi**: hasilnya muncul di Scan printer dengan penjelasan dan langkah perbaikan. Untuk memasang printer di Windows: tekan Windows + R, tempel alamat `\\SERVER\Printer`, Enter.

Tidak ditemukan saat mencari? Server mati/beda jaringan, atau firewall di server memblokir File and Printer Sharing. Ketik alamat IP server secara manual.
Lewat CLI: `nsd scan --role server --host localhost --type printer` (server) dan `nsd scan --role client --host SERVER01 --share EPSON --type printer` (client).

## Tombol Server: jalankan, autostart, log koneksi/cetak
Menu **Server** punya tiga kontrol baru:
1. **Jalankan server / Hentikan server**: menyalakan `nsd serve` di latar belakang (tanpa jendela, satu instans per folder data).
2. **Jalankan server otomatis saat Windows menyala (saat login)**: memasang/menghapus tugas Task Scheduler untuk `serve` (hanya `NSD.exe` terpaket, tanpa admin).
3. **Aktivitas langsung**: log siapa yang menyambung/terputus dan pekerjaan cetak (masuk antrean, status berubah, selesai, bermasalah). Disimpan di `<data>/activity.jsonl` (dirotasi 1 MB).
Tanpa hak administrator hanya alamat IP yang terlihat (nama komputer/pengguna butuh admin). Semuanya BACA-SAJA.
CLI: `nsd serve [--poll 3] [--interval 300]`, `nsd serve --status`, `nsd serve --stop`, `nsd autostart install --task serve`.
Catatan: "selesai" berarti pekerjaan hilang dari antrean (terkirim ke printer atau dibatalkan); belum diuji di Windows asli.

## Alur satu klik (monitor + autostart + GUI)
Klik ganda `NSD.exe` (atau `NSD-Start.bat`) = `nsd start`:
1. **Autostart** dipasang sekali (Task Scheduler, mode `logon-user`, tanpa admin; hanya build terpaket, idempoten).
2. **Monitor latar belakang**: baca-saja, dinyalakan tanpa jendela (satu instans per folder data). Ini bukan "server" yang dibutuhkan agar sharing bekerja; lihat bagian di atas.
3. **GUI**: dibuka (satu instans; klik kedua tidak membuka jendela baru).
Setelah itu monitor otomatis jalan setiap login. Opsi: `--no-gui` (hanya monitor), `--no-monitor`, `--no-autostart`, `--host/--share/--type/--interval`.
`scripts\NSD-Autostart-On.bat` / `NSD-Autostart-Off.bat` memasang/menghapus autostart secara manual. `build_windows.ps1` menyalin ketiga `.bat` ke `dist\NSD\`.
Belum diuji di Windows asli (lihat progres.md).

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
