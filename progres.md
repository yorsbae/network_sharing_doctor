# Progres — Network Sharing Doctor

**Terakhir diperbarui:** 14 Oktober 2026
**Fase aktif:** Fase 1 — MVP diagnostik baca-saja (lihat `vision.md`, Bagian B §14 dan Bagian C)
**Versi kode:** 0.1.0 (belum dirilis) · **Tes:** 94 lulus (`unittest`, ~0,4 dtk; 14 di antaranya butuh PySide6 dan dilewati bila tidak ada) · **Aturan:** 25 valid

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

## Pekerjaan awal Fase 3 — Kertas & Layout di client (vision A.4.4, A.4.5)
Dikerjakan lebih awal dari urutan fase karena murni logika lokal dan tidak mengubah sistem apa pun.
- [x] Model `PaperSize` (mm, divalidasi, disimpan sebagai potret, konversi 1/10 mm untuk DEVMODE dan inci), preset A3/A4/A5/F4 (Folio, 210×330)/Letter/Legal
- [x] `PageLayout`: orientasi, margin, skala, area isi, peringatan margin lebih kecil dari area tak-tercetak printer
- [x] `PaperStore`: ukuran buatan pengguna disimpan **lokal di client** (`paper_sizes.json`), tulis atomik, berkas rusak diabaikan dan **tidak ditimpa**, entri buruk dilewati satu per satu
- [x] `capability.assess()`: menilai 4 jalur (per dokumen, formulir client, antrean lokal, formulir server) dari data driver; data tidak cukup → *Belum diketahui*, tidak pernah diklaim bisa; ukuran di luar rentang driver → *Tidak didukung*
- [x] CLI: `nsd paper list | add | remove | layout`
- [~] UI: halaman *Kertas & Layout* (daftar, tambah/hapus, orientasi/margin/skala, pratinjau halaman). **Dirender offscreen di Linux** dan terlihat benar; belum pernah dilihat di Windows
- [ ] Mengumpulkan kemampuan driver dari Windows (`DeviceCapabilities`: rentang ukuran, dukungan ukuran kustom) → butuh adapter baru + uji di VM Windows
- [ ] Menerapkan ukuran ke printer (jalur per dokumen, formulir client, antrean lokal) — Fase 2 (executor, snapshot, rollback) harus ada dulu
- [ ] Pencetakan nyata dari tampilan print layout (Qt `QPrinter`/`QPageSize` kustom) — belum ada; tidak ada tes cetak sampai disetujui (Bagian C #6, #10)
- [ ] Membuat ukuran terlihat di aplikasi lain (Word/Excel) = formulir Windows, butuh admin

**Jawaban atas "apakah bisa mandiri dari server" (rinci di vision A.4.5):** definisi ukuran dan tampilan layout
**bisa** mandiri. Ukuran itu dipakai printer atau tidak **bergantung driver dan perangkat**, dan pengiriman cetak lewat
share tetap melewati server. Tidak ada yang dari ini terbukti pada driver nyata.

## Print Layout ala ACCURATE Online — popup saat klik Cetak (vision A.4.5)
Maksud "AOL" = **ACCURATE Online**: klik Cetak → muncul popup *Print Layout* (printer, kertas, margin, pratinjau) → Cetak.
- [x] Popup `PrintLayoutDialog`: printer (daftar printer Windows + "Simpan sebagai PDF"), ukuran kertas (bawaan + milik pengguna), tombol **Tambah ukuran…** langsung di popup, orientasi, 4 margin, skala, salinan, **pratinjau langsung per halaman** (◀ ▶)
- [x] Pratinjau dan hasil cetak memakai **satu jalur gambar** (`printing/render.paint_page`) sehingga pratinjau = hasil
- [x] Pilihan terakhir (printer, kertas, orientasi, margin, skala) diingat lokal di client (`print_prefs.json`)
- [x] Tombol **Cetak…** di halaman Diagnosa mencetak laporan (disamarkan sesuai pengaturan); tombol **Cetak halaman uji…** di halaman Kertas & Layout
- [x] Halaman uji: tepi kertas (garis merah), area isi, penggaris sentimeter, info ukuran/margin → untuk memeriksa dengan penggaris apakah printer menerima ukuran apa adanya
- [x] **Terbukti lewat PDF:** ukuran halaman keluaran tepat (F4 210×330 → 209,9×329,8 mm; lanskap menukar sisi; 100×150 mm), paginasi teks, skala, pesan galat (tujuan tak ada/printer tak ada/tak bisa ditulis)
- [x] Konfirmasi sebelum mencetak ke printer fisik; pengaturan tidak valid (mis. margin menghabiskan area isi) menonaktifkan tombol Cetak
- [~] **Mencetak ke printer fisik Windows belum pernah dijalankan.** Hanya jalur PDF yang teruji. Di sandbox tidak ada printer.
- [ ] Mengisi `DriverCaps` dari printer asli (rentang ukuran, dukungan kustom) dan menampilkannya di popup — butuh uji Windows
- [ ] Mendaftarkan ukuran sebagai formulir Windows agar tampil di aplikasi lain (butuh admin, Fase 2)
- [ ] Cetak dokumen selain teks (mis. PDF/gambar), kop, tabel; header/footer, nomor halaman

## Belum terbukti (jangan dipercaya sebelum diuji di Windows)
1. Semua skrip PowerShell di `windows/powershell.py` belum pernah dijalankan di Windows (hanya jalur penolakan & mock).
2. ID grup firewall `@FirewallAPI.dll,-32752` berasal dari ingatan; bila salah → hasil kosong → *Belum diperiksa* (tidak menyesatkan, tetapi tidak berguna).
3. Klasifikasi error UNC (HRESULT/tipe exception/pesan Inggris) belum dicocokkan dengan perilaku Windows nyata; pesan di OS berbahasa lain mungkin tidak cocok (jatuh ke kategori `other`).
4. Pemetaan kode error → petunjuk (0x11B, 0x709, dst.) berasal dari pengetahuan umum, belum direproduksi (vision B §8).
5. UI hanya pernah dirender offscreen di Linux; tampilan di Windows (font, DPI, tema gelap) belum dilihat.
6. Seluruh penilaian jalur kertas (`capability.py`) berdasarkan pengetahuan umum tentang DEVMODE/formulir Windows, belum diuji dengan driver nyata. Khususnya: apakah sambungan printer share memakai formulir lokal client atau daftar formulir server.
7. Perilaku driver V4 vs V3 terhadap ukuran kustom belum diperiksa.
8. **Cetak ke printer fisik** lewat `QPrinter`: apakah `QPageSize` kustom dipetakan Qt ke ukuran kertas kustom (DEVMODE) yang diterima driver tertentu, apakah `setFullPage(True)` + margin sendiri benar di Windows, dan apakah printer menolak/memotong ukuran 210×330 — **semuanya belum diuji**. Halaman uji ada untuk memeriksanya.
9. Font "Courier New" untuk laporan teks dipakai dengan fallback monospace; tampilan di Windows belum dilihat.
10. Pola `lambda` yang menangkap `self` pada sinyal (dipakai di `diagnose_page.py` dan `main_window.py` yang sudah ada) memicu korupsi memori di dialog baru sampai diganti slot biasa (lihat bug). Halaman lama belum diaudit untuk pola serupa.

## Bug yang ditemukan tes dan sudah diperbaiki
- (Print) **Korupsi memori / segfault saat keluar** (`malloc(): unaligned fastbin chunk`) pada `PrintLayoutDialog`: ditemukan karena kode keluar tes bukan 0 walau semua tes "OK". Bisect otomatis (hapus satu baris konstruktor per percobaan) menunjuk dua tombol halaman yang disambung dengan `lambda` yang menangkap `self`; diganti slot biasa (`_prev_page`/`_next_page`), 5/5 keluar bersih. Label tanpa induk di grid margin juga diberi induk eksplisit.
- (Print) Tombol **Cetak…** di halaman Diagnosa memanggil `settings.get(key, default)` padahal API hanya menerima `get(key)` → `TypeError`. Ditemukan lewat uji alur utuh (scan → Cetak → popup → PDF), bukan oleh tes unit; kini ada tes regresi.
- (Kertas) `assess()` awalnya menandai jalur formulir client/antrean lokal *Perlu admin* (dianggap bisa) walau rentang driver tidak diketahui → diperbaiki jadi *Belum diketahui*; tes `test_unknown_caps_never_claimed_available`.
- (Kertas) nama preset "F4 / Folio" ditolak validator nama pada kode yang sama (`/`) → diganti "F4 (Folio)".
- (Kertas) logika pengecekan rentang awalnya berbelit dan salah arah → ditulis ulang orientasi-agnostik (sisi pendek vs pendek).
- Kunci bukti `smb1` (mengandung angka) ditolak regex skema → regex diperbaiki.
- Nama share mengizinkan `' ; \` & %` dsb. → diperketat (pertahanan berlapis; tidak eksploitabel karena parameter lewat env var).
- `result(..., status=...)` bentrok dengan parameter `status` → pemeriksaan printer diam-diam jadi *internal error* → parameter dijadikan posisional-saja, kunci bukti diganti `printer_status`.

## Keputusan yang saya ambil sendiri (perlu persetujuan Anda)
0. "AOL" = ACCURATE Online (klik Cetak → popup Print Layout). Popup ini dibuat mengikuti alur itu; kemiripan tampilan persisnya dengan ACCURATE tidak diketahui (belum ada tangkapan layar acuan).
1. Fase 1 **tanpa penemuan otomatis** dan **tanpa tes cetak** (Bagian C #5, #6).
2. Nama share dengan `& % ' ; ( ) [ ] { } ~ # @ , = + ^ !` ditolak (mis. "R&D" tidak didukung). Trade-off keamanan; bisa dilonggarkan.
3. UI baru 5 dari 8 menu di visi (Beranda, Diagnosa, Kertas & Layout, Riwayat, Pengaturan). Mode Server/Client sebagai halaman terpisah, "Printer dan Ukuran Kertas", dan "Folder Sharing" menunggu Fase 3–4.
4. Tombol "Perbaiki Otomatis" ada tetapi **dinonaktifkan** dengan penjelasan (Fase 1 baca-saja).
5. Tes memakai `unittest` (stdlib) karena pytest tidak tersedia; tetap kompatibel pytest.
6. Riwayat lokal menyimpan target apa adanya; penyamaran hanya pada ekspor (lihat SECURITY.md).

## Belum dikerjakan dari visi (sesuai urutan fase)
- Pemilihan printer di server via Registry + validasi ke printer Windows asli (A.4.3) — Fase 3
- Ukuran kertas khusus di client: daftar/layout/penilaian sudah ada (lihat atas); pengumpulan kemampuan driver, penerapan ke printer, dan cetak nyata — Fase 3/4
- Penemuan server otomatis (A.4.2) — Fase 3
- Eksekutor perbaikan, UAC, snapshot, verifikasi ulang, rollback (B §11) — Fase 2
- Izin share vs NTFS secara terpisah (A.5.6) — Fase 3
- Penandatanganan aturan/rilis, helper elevasi terbatas — Fase 6

## Langkah berikutnya (urutan disarankan)
0. **Coba cetak nyata di Windows:** buka Kertas & Layout → *Cetak halaman uji…* → pilih printer → ukuran F4 Kantor 210×330 → cetak, lalu ukur dengan penggaris. Catat hasil per driver di `docs/test-matrix.md`.
1. Jalankan `tests/integration_windows` di VM Windows 11, isi `docs/test-matrix.md`, perbaiki skrip/ID yang meleset.
2. Render UI di Windows (termasuk halaman Kertas & Layout); perbaiki masalah tata letak.
2b. Tulis adapter baca-saja `DeviceCapabilities` untuk mengisi `DriverCaps`, uji dengan 2–3 driver nyata (mis. printer laser A4 dan printer dot-matrix/nota) di VM + printer fisik.
3. Reproduksi 3–4 kegagalan nyata (445 diblokir, akses ditolak, Spooler mati, share printer salah) dan simpan sebagai fixture.
4. Baru masuk Fase 2: executor + snapshot + verifikasi untuk **satu** aturan (`PRN-SPOOLER-001`), diuji di VM.

## Log perubahan
- 2026-10-14 (sesi 3) — Popup Print Layout (ala ACCURATE), lapisan cetak `nsd.printing` (pratinjau = hasil), cetak laporan dari Diagnosa, halaman uji, preferensi cetak lokal; dua bug (korupsi memori dialog, `settings.get`) ditemukan & diperbaiki; 94 tes. Cetak ke PDF terbukti; printer fisik belum.
- 2026-10-14 (sesi 2) — Modul `nsd.paper` (model, layout, store lokal, penilaian jalur), CLI `nsd paper`, halaman UI *Kertas & Layout*, vision A.4.5 + Bagian C #9–11; 82 tes. UI dirender offscreen (bukan Windows).
- 2026-10-14 — Perapian `vision.md`; kerangka proyek; fondasi keselamatan; adapter Windows; mesin diagnostik; mesin aturan + 25 aturan; SQLite; laporan; CLI; UI PySide6; 59 tes; dokumen pendukung.
