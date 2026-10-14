# Progres — Network Sharing Doctor

**Terakhir diperbarui:** 14 Oktober 2026
**Fase aktif:** Fase 1 — MVP diagnostik baca-saja (lihat `vision.md`, Bagian B §14 dan Bagian C)
**Versi kode:** 0.1.0 (belum dirilis) · **Tes:** 59 lulus (`unittest`, 0,12 dtk) · **Aturan:** 25 valid

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

## Belum terbukti (jangan dipercaya sebelum diuji di Windows)
1. Semua skrip PowerShell di `windows/powershell.py` belum pernah dijalankan di Windows (hanya jalur penolakan & mock).
2. ID grup firewall `@FirewallAPI.dll,-32752` berasal dari ingatan; bila salah → hasil kosong → *Belum diperiksa* (tidak menyesatkan, tetapi tidak berguna).
3. Klasifikasi error UNC (HRESULT/tipe exception/pesan Inggris) belum dicocokkan dengan perilaku Windows nyata; pesan di OS berbahasa lain mungkin tidak cocok (jatuh ke kategori `other`).
4. Pemetaan kode error → petunjuk (0x11B, 0x709, dst.) berasal dari pengetahuan umum, belum direproduksi (vision B §8).
5. UI belum pernah tampil.

## Bug yang ditemukan tes dan sudah diperbaiki
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
- Eksekutor perbaikan, UAC, snapshot, verifikasi ulang, rollback (B §11) — Fase 2
- Izin share vs NTFS secara terpisah (A.5.6) — Fase 3
- Penandatanganan aturan/rilis, helper elevasi terbatas — Fase 6

## Langkah berikutnya (urutan disarankan)
1. Jalankan `tests/integration_windows` di VM Windows 11, isi `docs/test-matrix.md`, perbaiki skrip/ID yang meleset.
2. Render UI di Windows; perbaiki masalah tata letak.
3. Reproduksi 3–4 kegagalan nyata (445 diblokir, akses ditolak, Spooler mati, share printer salah) dan simpan sebagai fixture.
4. Baru masuk Fase 2: executor + snapshot + verifikasi untuk **satu** aturan (`PRN-SPOOLER-001`), diuji di VM.

## Log perubahan
- 2026-10-14 — Perapian `vision.md`; kerangka proyek; fondasi keselamatan; adapter Windows; mesin diagnostik; mesin aturan + 25 aturan; SQLite; laporan; CLI; UI PySide6; 59 tes; dokumen pendukung.
