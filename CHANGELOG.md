# Changelog

## 0.1.0 (belum dirilis) — Fase 1
- Diagnostik baca-saja: target, DNS, TCP 445/135, UNC folder, printer share, layanan, profil jaringan, firewall, SMB, event.
- Mesin aturan: skema tervalidasi, loader dengan digest, matcher berbasis bukti, 25 aturan awal.
- Gerbang kebijakan; tidak ada perubahan sistem yang dapat dijalankan.
- SQLite riwayat + audit; laporan teks/JSON disamarkan secara default.
- CLI dan UI PySide6 (UI belum diuji render).
- Kertas & Layout (awal Fase 3): ukuran kertas khusus tersimpan lokal di client, tata letak halaman + pratinjau, penilaian jalur ukuran kustom berbasis kemampuan driver (belum diuji di Windows), CLI `nsd paper`.
- Popup Print Layout (printer, kertas, margin, skala, salinan, pratinjau) dari tombol Cetak; cetak laporan diagnosis; halaman uji berpenggaris; "Simpan sebagai PDF"; preferensi cetak diingat lokal. Cetak ke printer fisik Windows belum diuji.
