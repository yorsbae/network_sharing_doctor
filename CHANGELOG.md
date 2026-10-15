# Changelog

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
