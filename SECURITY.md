# SECURITY — Network Sharing Doctor

Status: draf Fase 0/1. Dokumen ini bukan pengganti threat model formal (masih tugas terbuka di `progres.md`).

## Jaminan desain (Fase 1) dan cara memverifikasinya
| Jaminan | Mekanisme | Tes |
|---|---|---|
| Scan tidak mengubah sistem | `run()` hanya mengenal 11 operasi baca-saja; operasi lain → `unsupported`. Perubahan hanya lewat `apply()` (lihat Fase 2 di bawah) | `test_security`, `test_scenarios.assertReadOnly`, `test_all_read_ops_have_no_mutating_cmdlets` |
| Tanpa injeksi perintah | Skrip PowerShell konstan; parameter divalidasi dan dikirim lewat variabel lingkungan `NSD_P_*`; `shell=False`; timeout; batas output | `test_injection_rejected_before_execution`, `test_params_via_env_not_script` |
| Aturan tidak bisa menjalankan perintah bebas | Aksi hanya dari allowlist bertipe; operasi berbahaya masuk daftar larangan; risiko high/security_sensitive wajib `blocked` | `test_rejections`, `test_bad_files_do_not_load` |
| Tidak melemahkan keamanan | Tidak ada operasi untuk menonaktifkan firewall, mengaktifkan SMB1/guest, memberi Everyone Full Control, dll. | `test_shipped_rules_never_weaken_security` |
| Tidak menyimpan kata sandi | Tidak ada input kredensial; pola rahasia disaring sebelum DB/log/laporan | `test_secrets`, `test_roundtrip_and_audit` |
| Laporan aman dibagikan | Penyamaran default aktif + pratinjau di UI | `test_text_redacted_by_default` |
| DB rusak tidak menghilangkan bukti | Dikarantina ke `*.corrupt-<ts>`, bukan dihapus | `test_corrupt_db_is_quarantined_not_deleted` |
| Integritas aturan terlacak | Digest SHA-256 berkas aturan dicatat di setiap kasus | `test_digest_changes_with_content` |

## Fase 2 — perbaikan terbatas (satu jenis: `start_service`)
Mati secara default. Semua syarat berikut harus terpenuhi sekaligus; kegagalan salah satunya → **ditolak sebelum ada perubahan** dan dicatat di audit (`repair_refused`):
1. Pengaturan `execution_enabled=true` (diubah eksplisit lewat `nsd settings --set`, tercatat di audit).
2. Persetujuan eksplisit per tindakan (`--confirm`).
3. Aturan diambil dari berkas aturan yang dimuat (bukan dari data DB), lolos gerbang kebijakan (risiko `low`, bukan `blocked`), dan operasinya `start_service` untuk layanan di allowlist.
4. Proses berjalan sebagai administrator (tidak ada bypass UAC, tidak ada penyimpanan kata sandi).
5. Keadaan awal terbaca **dan snapshot tersimpan** sebelum perintah apa pun dijalankan.
Setelah itu: verifikasi ulang (layanan benar-benar Running; tipe startup tidak berubah), pemindaian ulang kasus, dan rollback opsional (hanya Running→Stopped bila awalnya Stopped). Hasil "diterapkan tetapi belum terverifikasi" tidak pernah dilaporkan sebagai sukses. Tipe startup tidak pernah diubah dan `-Force` tidak dipakai. Tes: `tests/unit/test_repair.py`.

## Monitor & autostart (opsional)
- Monitor hanya memanggil operasi baca-saja; adapter-nya dibuat **tanpa izin mutasi apa pun isi pengaturan**; tes memastikan `apply()` tidak pernah dipanggil. Tidak ada perbaikan otomatis.
- Satu instans per folder data (kunci berkas); penghentian lewat SIGTERM/Ctrl+C bersih (diuji di Linux).
- Hanya `status.json` (ringkasan tanpa bukti mentah) dan kasus saat status **berubah** yang disimpan; ada debounce 2 putaran.
- **Mode `boot-system` (SYSTEM) berbahaya bila salah pasang.** Penjagaan: wajib build terpaket di Program Files/Windows (kecuali `--i-understand-risk`), wajib administrator, folder data `ProgramData\NetworkSharingDoctor` dikunci dengan `icacls` berbasis SID (SYSTEM/Admin penuh, Users hanya baca) **sebelum** tugas dibuat; bila ACL gagal, tugas tidak dibuat.
- Mode `logon-user` (default) berjalan dengan hak pengguna yang memasang; Task Scheduler `ONLOGON` memicu pada logon pengguna mana pun, kunci instans mencegah duplikat.
- Task Scheduler/`schtasks`/`icacls` **belum diuji di Windows asli**; hanya pembangunan argumen dan logika penolakan yang diuji. Alternatif tanpa NSD untuk menghidupkan ulang layanan yang mati: tab *Recovery* di Services.msc.

## Pencarian server (halaman Client)
Tombol *Cari server di jaringan* melakukan sambungan TCP biasa ke **port 445 saja**, pada subnet /24 dari alamat IPv4 **pribadi** komputer ini (maksimum 253 alamat), lalu menutupnya. Tidak ada kredensial dikirim, isi share tidak dibaca, dan tidak ada yang diubah. Hanya berjalan saat pengguna menekan tombol (tidak pernah otomatis, tidak oleh monitor) dan bisa dibatalkan. Alamat publik, loopback, dan link-local tidak dipindai; bila tidak ada alamat pribadi, pencarian tidak mengirim apa pun. Nama komputer dicari lewat DNS balik dan hanya dipakai bila lolos `validate_host`.
Catatan: pemindaian port dapat tercatat oleh perangkat keamanan jaringan di organisasi yang ketat. Ini mengubah keputusan Fase 1 ("tanpa penemuan otomatis") atas permintaan pemilik proyek; mulai-nya tetap manual.

## Batasan yang diketahui
- Aturan dimuat dari berkas lokal **tanpa tanda tangan**. Siapa pun yang bisa menulis folder `rules/` dapat mengubah saran/teks aturan (aksi tetap dibatasi allowlist). Tanda tangan aturan: Fase 6.
- Folder data portabel di drive jaringan/folder yang dapat ditulis orang lain → aplikasi memperingatkan, tidak memblokir.
- Riwayat lokal menyimpan nama target apa adanya (agar kasus bisa diulang). Penyamaran hanya diterapkan pada ekspor/laporan.
- Nama share dengan karakter `& % ' ; ( ) [ ] { } ~ # @ , = + ^ !` ditolak di Fase 1 (trade-off keamanan; mis. "R&D").
- Konten pesan error Windows di bukti bisa memuat nama/jalur; tersaring hanya oleh penyamaran saat ekspor.
- Eksekutor baru mendukung `start_service`. Aturan menengah (firewall, profil jaringan, share printer) **ditolak** oleh gerbang kebijakan; snapshot/rollback untuk jenis lain belum ada.
- Tidak ada elevasi mandiri: pengguna harus menjalankan aplikasi sebagai administrator. Helper elevasi terbatas: Fase 6.
- Perilaku `Start-Service`/`Stop-Service` di Windows nyata (layanan dependen, timeout, pesan error) **belum diuji**; lihat `docs/test-matrix.md` #11.

## Melaporkan celah
Buka isu privat kepada pemelihara proyek; jangan menyertakan laporan yang tidak disamarkan.
