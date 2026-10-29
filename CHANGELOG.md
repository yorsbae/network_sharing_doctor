# Changelog

## Belum dirilis: UI baru (mockup Print Test)
- Cangkang baru: sidebar navy dengan ikon, merek "Print Test", status sistem nyata; tema gelap bawaan (terang tersedia), token baru dan chip status bernada.
- Halaman baru: Dashboard (kartu status, hasil terakhir, aksi cepat), Daftar printer (+ dialog detail dan cetak halaman uji), Antrean cetak (baca-saja, muat ulang 10 dtk). Scan printer, Log, dan Pengaturan ditata ulang; Pengaturan punya sakelar autostart monitor.
- "Scan sekarang" di Dashboard langsung memindai komputer ini. Operasi baca-saja baru `list_print_jobs`.
- Pemuatan data lewat thread latar (`run_async`) agar jendela tidak membeku. Tes anti-slop otomatis.

## Belum dirilis: alur satu klik
- Perintah `nsd start` (juga saat `NSD.exe`/`python -m nsd` dijalankan tanpa argumen): pasang autostart sekali (logon-user, idempoten, hanya build terpaket) + nyalakan monitor terlepas dari jendela + buka GUI; instans tunggal untuk monitor dan GUI.
- `scripts/NSD-Start.bat`, `NSD-Autostart-On.bat`, `NSD-Autostart-Off.bat`; `build_windows.ps1` menyalinnya ke `dist\NSD`.
- `nsd gui` tetap membuka GUI saja. Monitor tetap baca-saja. Tes baru: `tests/unit/test_launcher.py`.

## Belum dirilis: antarmuka
- Tema terang/gelap/ikuti sistem (Pengaturan > Tema), satu sumber token warna di `src/nsd/ui/theme.py`; semua pasangan teks lolos WCAG AA dan diuji.
- Menu: Beranda, Diagnosa, Kertas, Riwayat, Pengaturan; pintasan Ctrl+1 sampai Ctrl+5, Ctrl+P untuk cetak.
- Keadaan kosong, memuat, dan galat pada Diagnosa dan Riwayat; hasil diberi label teks selain warna.
- Popup Print Layout (printer, kertas, margin, skala, pratinjau) kembali tersedia: tombol Cetak di Diagnosa, Ctrl+P, dan cetak berkas PDF (`PdfJob`).
- Ukuran kertas khusus di client dapat diisi dalam mm, cm, atau inci; disimpan dalam mm.
- Perbaikan: scan dari GUI gagal karena koneksi SQLite dibuat di thread lain; teks laporan tercetak pucat pada tema gelap; tanda pisah panjang dihapus dari teks aplikasi.

- Monitor latar belakang baca-saja (`nsd monitor`): debounce, status.json atomik, simpan kasus hanya saat berubah, kunci satu instans.
- Autostart via Task Scheduler (`nsd autostart`): mode logon-user / boot-system dengan penjagaan lokasi file dan ACL folder data.

## 0.2.0-dev — Fase 2 (sebagian)
- Eksekutor perbaikan `start_service` dengan snapshot, persetujuan, verifikasi, rollback, dan audit; mati secara default.
- `RealWindowsAdapter.apply()` terpisah dari `run()`; dijaga flag eksekusi + elevasi.
- CLI: `settings`, `repair`, `rollback`; pemindaian ulang otomatis setelah perbaikan terverifikasi.

## 0.1.0 (belum dirilis) — Fase 1
- Diagnostik baca-saja: target, DNS, TCP 445/135, UNC folder, printer share, layanan, profil jaringan, firewall, SMB, event.
- Mesin aturan: skema tervalidasi, loader dengan digest, matcher berbasis bukti, 25 aturan awal.
- Gerbang kebijakan; tidak ada perubahan sistem yang dapat dijalankan.
- SQLite riwayat + audit; laporan teks/JSON disamarkan secara default.
- CLI dan UI PySide6 (UI belum diuji render).
