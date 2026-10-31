# Changelog

## Belum dirilis: alur Server dan Client
- Menu baru **Server**: daftar kesiapan (Print Spooler, layanan Server, profil jaringan, firewall, printer dibagikan) dengan langkah manual untuk yang belum siap, alamat `\\NAMA\Printer` yang bisa disalin untuk client, dan "Salin petunjuk untuk client". Menyatakan bahwa tidak ada program server yang perlu dijalankan.
- Menu baru **Client**: tiga langkah (pilih server, pilih printer atau folder, periksa koneksi). Pencarian server di jaringan lokal (hanya port 445, /24 pribadi, hanya saat diklik, bisa dibatalkan), daftar printer yang dibagikan server, ingat server terakhir, dan "Periksa koneksi" langsung menjalankan scan terisi.
- Dashboard: panel "Mulai di sini" untuk memilih peran komputer; pilihan tersimpan dan menyinkronkan Pengaturan. Kartu statistik jadi dua kolom saat sempit (teks tidak lagi terpotong).
- Scan printer: tombol "Cari server…", host `localhost` terisi otomatis untuk peran Server dan dibersihkan saat kembali ke Client.
- Halaman Dashboard, Server, dan Client bisa digulir; jarak menu sidebar dirapatkan agar 10 menu muat di tinggi 600. Pintasan Ctrl+1 sampai Ctrl+9 dan Ctrl+0.
- README menjelaskan alur Server dan Client; istilah "server side" pada alur satu klik diganti "monitor latar belakang" agar tidak menyesatkan.
- Tes: `tests/unit/test_server_client_flow.py` dan `tests/ui/test_server_client_pages.py` (termasuk tes tanpa overflow horizontal pada 980x600).

## Belum dirilis: katalog error printer dan folder sharing
- 21 aturan petunjuk baru (hanya-kode, baca-saja, keyakinan rendah) untuk kode 0x Printer Sharing (0x00000040, 0x0000007C, 0x00000BCB, 0x00000002, 0x0000000A, 0x00000057, 0x0000007E, 0x0000007F, 0x00000035, 0x00000043, 0x0000003A) dan folder sharing (0x80004005, 0x80070032, 0x80070079, 0x80070020, 0x80070021, 0x80070003, 0x80070002, 0x80070006, 0x80070057, 0x80070015). Total aturan 46.
- `docs/error-catalog.md`: tabel kode printer dan folder beserta aturannya, dan master list 104 popup error printer (referensi; pesan tanpa kode 0x belum menjadi aturan).
- Tes baru memastikan tiap kode di daftar punya entri katalog dan tetap berupa petunjuk keyakinan rendah.

## Belum dirilis: perbaikan otomatis di UI dan halaman Kode error
- Merek UI kembali ke Network Sharing Doctor.
- Scan printer > "Perbaiki otomatis…": pratinjau, persetujuan, penerapan lewat `RepairExecutor` (snapshot, verifikasi, audit), tombol "Kembalikan perubahan", lalu scan ulang otomatis. Sakelar di Pengaturan; tombol di dialog untuk mengaktifkan dan menjalankan ulang sebagai administrator (UAC standar).
- Yang didukung otomatis tetap hanya menyalakan layanan Windows yang berhenti (Print Spooler, Workstation, Server). Temuan lain tampil sebagai langkah manual dengan alasan.
- Halaman Kode error: cari kode 0x... atau kata kunci dari katalog aturan, lalu "Periksa dengan kode ini".
- Perbaikan: kode ditulis `0X11B` (X besar) kini dikenali.

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
