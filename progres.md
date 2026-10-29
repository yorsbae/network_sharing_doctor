# Progres — Network Sharing Doctor

**Terakhir diperbarui:** 15 Oktober 2026 (monitor & autostart ditambahkan)
**Fase aktif:** Fase 1 (menunggu validasi Windows) + Fase 2 sebagian: satu jenis perbaikan, mati secara default
**Versi kode:** 0.1.0 (belum dirilis) · **Tes:** 104 lulus (`unittest`, ~0,6 dtk) · **Aturan:** 25 valid

## Legenda
`[x]` selesai dan lulus tes otomatis · `[~]` ditulis tetapi **belum bisa diuji di lingkungan ini** · `[ ]` belum dikerjakan

> Sebuah butir hanya `[x]` bila ada tes yang lulus. Perilaku yang bergantung pada Windows asli
> **tidak** dianggap terbukti oleh tes bermock; itu dicatat terpisah di bagian "Belum terbukti".

## Fase 0 — Fondasi keselamatan
- [x] `vision.md` dirapikan: Bagian A (visi produk), B (desain teknis), C (keputusan sementara); sisa skrip Python di file asli dibuang
- [x] Allowlist operasi + validasi host/share/UNC/layanan (`security/allowlist.py`)
- [x] Redaksi data sensitif, token stabil (`security/redaction.py`)
- [x] Adapter Windows baca-saja: tanpa `shell=True`, parameter via env var, timeout, operasi di luar allowlist ditolak (`windows/powershell.py`) — *logika diuji dengan mock*
- [x] Deteksi elevasi (`windows/privilege.py`)
- [x] `SECURITY.md` (jaminan ↔ tes, batasan yang diketahui)
- [ ] Threat model formal dan matriks kebijakan (SECURITY.md baru ringkasan)
- [ ] Lab VM Windows (di luar sandbox)

## Fase 1 — MVP diagnostik baca-saja
### Mesin diagnostik — [x] (dengan adapter palsu)
- [x] 20 pemeriksaan, 10 lapisan: target, DNS, TCP 445/135, UNC folder, printer share remote/lokal, status printer, layanan (Workstation/Server/Spooler/FDResPub), profil jaringan, firewall, SMB klien/server, share lokal, event error cetak, privilese, info OS
- [x] Status 4 nilai; *Belum diperiksa* ≠ *Gagal* (pemeriksaan dependen dilewati sebagai *Belum diperiksa*)
- [x] Pemeriksaan yang rusak tidak menggagalkan scan (jadi `internal.*` → Belum diperiksa)
- [x] Tes cetak/pemasangan printer sengaja tidak dilakukan → `printer.connect_test` selalu *Belum diperiksa*

### Mesin aturan — [x]
- [x] Validator skema (menolak operasi terlarang, risiko tinggi tanpa `blocked`, aksi pengubah tanpa snapshot/verifikasi/rollback)
- [x] Loader + digest SHA-256 (berkas JSON rusak/duplikat/jahat ditolak, sisanya tetap dimuat)
- [x] Matcher: bukti menentukan penyebab; kode error hanya menaikkan keyakinan; kode saja → petunjuk *rendah* yang tersembunyi bila ada temuan berbasis bukti
- [x] 25 aturan awal di `rules/*.json` (jaringan, folder, printer, keamanan)
- [x] Gerbang kebijakan 3 level; **tidak ada eksekusi** (`EXECUTION_AVAILABLE=False`)

### Aplikasi, penyimpanan, antarmuka
- [x] SQLite: kasus, pemeriksaan, rencana, audit, pengaturan; migrasi (`user_version`), cek integritas, karantina DB rusak, retensi
- [x] Layanan scan + laporan teks/JSON (disamarkan default; tag teks selain warna)
- [x] CLI: `scan`, `history`, `rules-validate`, `clear-history` (kode keluar 0/1/2)
- [~] UI PySide6: Beranda, Diagnosa (+ pratinjau ekspor, salin ID), Riwayat, Pengaturan — lolos cek sintaks/impor, **belum pernah dirender** (PySide6 tidak terpasang di sandbox)
- [~] `scripts/build_windows.ps1` (PyInstaller `--onedir`) — belum dijalankan
- [ ] `requirements-lock.txt` dengan versi persis (butuh mesin build; kini `requirements.txt` batas minimum)

### Pengujian
- [x] Unit: allowlist, redaksi, keamanan adapter (injeksi), skema/loader/matcher, kebijakan, penyimpanan, laporan, CLI
- [x] 15 skenario scan penuh dengan adapter/probe palsu (DNS gagal, 445 diblokir tetapi ping OK, akses ditolak vs share tidak ada vs logon gagal, Spooler mati, share printer salah, 0x11B, SMB1/guest, firewall/profil, input berbahaya, dll.)
- [~] `tests/integration_windows/` — ditulis, **dilewati di Linux**; harus dijalankan di VM Windows (lihat `docs/test-matrix.md`)

**Kriteria keluar Fase 1** (vision B §14): "diagnostik berjalan tanpa elevasi bila memungkinkan dan membedakan jelas
gagal / lulus / belum diperiksa". → Logikanya terpenuhi dan teruji dengan mock; **belum terbukti di Windows asli**.
Fase 1 belum boleh dinyatakan selesai sebelum `docs/test-matrix.md` butir 1–6 dan 10 terisi.

## Alur satu klik
- [x] `application/launcher.py` + `nsd start`: urutan autostart → monitor → GUI, instans tunggal, langkah gagal tidak menghentikan langkah lain (8 tes; uji manual headless di Linux: monitor jalan, panggilan kedua memakai ulang)
- [~] `.bat` + build PyInstaller + `schtasks` dari `start` — **belum diuji di Windows asli**; cek: klik ganda NSD.exe, reboot/logon memunculkan proses monitor, klik kedua tidak membuka GUI ganda, `--windowed` tidak memunculkan konsol

## Fase 2 — perbaikan terbatas (sebagian)
- [x] `apply()` terpisah dari `run()`; menolak bila eksekusi nonaktif / bukan admin / operasi di luar `start_service`,`stop_service`; tanpa `-Force`, tanpa ubah tipe startup
- [x] Eksekutor `start_service`: gerbang kebijakan → baca keadaan awal → **snapshot tersimpan dulu** → terapkan → verifikasi (Running, startup tidak berubah) → audit
- [x] Hasil jujur: `verified` / `noop` / `failed` / `applied_unverified` (tidak dihitung sukses) / `refused` (tanpa efek samping)
- [x] Aturan diambil dari berkas aturan, bukan dari DB (DB yang diubah tidak bisa menyisipkan aksi); aturan menengah/tinggi/blocked ditolak gerbang kebijakan
- [x] Rollback (Running→Stopped bila awalnya Stopped), butuh persetujuan; no-op bila sudah Stopped; ditolak untuk kasus/aksi yang salah
- [x] Tabel `actions`, `snapshots`, `verification_results` terpakai; CLI `settings`, `repair`, `rollback`; pemindaian ulang setelah perbaikan terverifikasi
- [~] Tes lab Windows bergerbang `NSD_RUN_MUTATING=1` (`tests/integration_windows`) — ditulis, belum dijalankan
- [ ] Tombol/alur perbaikan di UI (tombol "Perbaiki Otomatis" masih dinonaktifkan; UI belum pernah dirender)
- [ ] Snapshot/aksi untuk firewall, profil jaringan, share printer (kini ditolak gerbang kebijakan karena risiko menengah)
- [ ] Persetujuan interaktif per tindakan di UI (kini lewat `--confirm` di CLI)

## Monitor & autostart (opsional, permintaan "seperti PaperCut")
Jawaban desain: sharing tidak butuh NSD berjalan (sudah autostart bawaan Windows). Yang dibuat adalah **monitor baca-saja**, bukan layanan perbaikan.
- [x] `nsd monitor`: putaran periodik, debounce 2 putaran, `status.json` atomik (ringkasan, tanpa bukti mentah), kasus hanya disimpan saat status berubah, audit `monitor_*`, loop tahan error dengan backoff
- [x] Adapter monitor tanpa izin mutasi; tes memastikan `apply()` tak pernah dipanggil
- [x] Kunci satu instans (`monitor.lock`); **diuji sebagai proses nyata di Linux**: instans kedua ditolak (kode 3), SIGTERM berhenti bersih, audit start→baseline→stopped
- [x] `nsd autostart install|uninstall|status`: mode `logon-user` (default) / `boot-system`; penjagaan: hanya build terpaket, boot-system wajib admin + Program Files, ACL folder data via `icacls` (SID) sebelum tugas dibuat, argumen daftar tanpa shell — *logika diuji dengan runner palsu*
- [~] `schtasks`/`icacls` sebenarnya, memicu saat boot/logon, ACL efektif — **belum diuji di Windows** (test-matrix #13–16)
- [ ] Notifikasi (toast/email) saat status memburuk; sengaja belum ada (menjalankan perintah/jaringan keluar menambah permukaan serangan)
- [ ] Halaman status monitor di UI; layanan Windows Service sejati (pywin32/NSSM) — belum diputuskan perlu

## Belum terbukti (jangan dipercaya sebelum diuji di Windows)
0. Perilaku `Start-Service`/`Stop-Service` nyata (layanan dependen, timeout 45 dtk, pesan error, hak admin) — seluruh alur Fase 2 baru diuji dengan adapter palsu.
1. Semua skrip PowerShell di `windows/powershell.py` belum pernah dijalankan di Windows (hanya jalur penolakan & mock).
2. ID grup firewall `@FirewallAPI.dll,-32752` berasal dari ingatan; bila salah → hasil kosong → *Belum diperiksa* (tidak menyesatkan, tetapi tidak berguna).
3. Klasifikasi error UNC (HRESULT/tipe exception/pesan Inggris) belum dicocokkan dengan perilaku Windows nyata; pesan di OS berbahasa lain mungkin tidak cocok (jatuh ke kategori `other`).
4. Pemetaan kode error → petunjuk (0x11B, 0x709, dst.) berasal dari pengetahuan umum, belum direproduksi (vision B §8).
5. UI belum pernah tampil.

## Bug yang ditemukan tes/kerja dan sudah diperbaiki
- (Fase 2) Edit saya pada `powershell.py` memotong dari baris `def run` milik Protocol, bukan kelas nyata, sehingga file rusak; terdeteksi karena jumlah tes turun 59→46. File ditulis ulang utuh; 59 tes asli kembali lulus sebelum melanjutkan.
- Kunci bukti `smb1` (mengandung angka) ditolak regex skema → regex diperbaiki.
- Nama share mengizinkan `' ; \` & %` dsb. → diperketat (pertahanan berlapis; tidak eksploitabel karena parameter lewat env var).
- `result(..., status=...)` bentrok dengan parameter `status` → pemeriksaan printer diam-diam jadi *internal error* → parameter dijadikan posisional-saja, kunci bukti diganti `printer_status`.

## Keputusan yang saya ambil sendiri (perlu persetujuan Anda)
1. Fase 1 **tanpa penemuan otomatis** dan **tanpa tes cetak** (Bagian C #5, #6).
2. Nama share dengan `& % ' ; ( ) [ ] { } ~ # @ , = + ^ !` ditolak (mis. "R&D" tidak didukung). Trade-off keamanan; bisa dilonggarkan.
3. UI baru 4 dari 8 menu di visi (Beranda, Diagnosa, Riwayat, Pengaturan). Mode Server/Client sebagai halaman terpisah, "Printer dan Ukuran Kertas", dan "Folder Sharing" menunggu Fase 3–4.
4. Tombol "Perbaiki Otomatis" ada tetapi **dinonaktifkan** dengan penjelasan (Fase 1 baca-saja).
5. Tes memakai `unittest` (stdlib) karena pytest tidak tersedia; tetap kompatibel pytest.
6. Riwayat lokal menyimpan target apa adanya; penyamaran hanya pada ekspor (lihat SECURITY.md).

## Belum dikerjakan dari visi (sesuai urutan fase)
- Pemilihan printer di server via Registry + validasi ke printer Windows asli (A.4.3) — Fase 3
- Ukuran kertas khusus di client, mis. 210×330 mm (A.4.4) — Fase 3/4
- Penemuan server otomatis (A.4.2) — Fase 3
- Eksekutor untuk operasi selain `start_service`; elevasi UAC mandiri (kini pengguna harus menjalankan sebagai admin) — Fase 2 lanjutan
- Izin share vs NTFS secara terpisah (A.5.6) — Fase 3
- Penandatanganan aturan/rilis, helper elevasi terbatas — Fase 6

## Langkah berikutnya (urutan disarankan)
1. Jalankan `tests/integration_windows` di VM Windows 11, isi `docs/test-matrix.md`, perbaiki skrip/ID yang meleset.
2. Render UI di Windows; perbaiki masalah tata letak.
3. Reproduksi 3–4 kegagalan nyata (445 diblokir, akses ditolak, Spooler mati, share printer salah) dan simpan sebagai fixture.
4. Jalankan `NSD_RUN_MUTATING=1` di VM lab untuk membuktikan alur `PRN-SPOOLER-001` pada Windows asli (butir #11 di test-matrix). Baru setelah itu perluas ke firewall/profil jaringan/share printer, dan hubungkan ke UI.

## Keputusan tambahan (Fase 2, perlu persetujuan Anda)
7. Perbaikan **mati secara default** dan butuh tiga hal sekaligus: `execution_enabled`, `--confirm`, dan administrator. Level kebijakan tetap terkunci "Diagnosis saja" untuk scan.
8. Hanya satu aksi per perbaikan dan hanya risiko `low`; layanan `Disabled` dilaporkan, bukan "diperbaiki" (ubah startup = keputusan administrator).
9. Rollback hanya untuk `start_service` dengan keadaan awal Stopped.

## Keputusan tambahan (monitor, perlu persetujuan Anda)
10. Autostart lewat **Task Scheduler**, bukan Windows Service: tanpa dependensi tambahan, mudah dihapus. Konsekuensi: tidak ada pemulihan otomatis bila proses mati (Task Scheduler tidak memulai ulang proses yang crash secara default).
11. Mode `boot-system` ditolak dari lokasi yang bisa ditulis pengguna (kecuali `--i-understand-risk`) untuk mencegah eskalasi hak akses.
12. Monitor **tidak** melakukan perbaikan otomatis walau `execution_enabled=true`.

## Log perubahan
- 2026-10-14 — Perapian `vision.md`; kerangka proyek; fondasi keselamatan; adapter Windows; mesin diagnostik; mesin aturan + 25 aturan; SQLite; laporan; CLI; UI PySide6; 59 tes; dokumen pendukung.
- 2026-10-15 — Fase 2 (sebagian): `apply()` bergerbang, `RepairExecutor` (snapshot→terapkan→verifikasi→rollback→audit), CLI `settings/repair/rollback`, rescan; 28 tes baru (total 87).
- 2026-10-15 — Monitor latar belakang + autostart Task Scheduler; `ScanService.save()` dipisah dari `run(persist=)`; 17 tes baru (total 104); uji proses nyata (kunci instans, SIGTERM).
