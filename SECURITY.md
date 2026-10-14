# SECURITY — Network Sharing Doctor

Status: draf Fase 0/1. Dokumen ini bukan pengganti threat model formal (masih tugas terbuka di `progres.md`).

## Jaminan desain (Fase 1) dan cara memverifikasinya
| Jaminan | Mekanisme | Tes |
|---|---|---|
| Tidak mengubah sistem | Adapter hanya mengenal 11 operasi baca-saja; operasi lain → `unsupported`. `EXECUTION_AVAILABLE=False` | `test_security`, `test_scenarios.assertReadOnly`, `test_all_read_ops_have_no_mutating_cmdlets` |
| Tanpa injeksi perintah | Skrip PowerShell konstan; parameter divalidasi dan dikirim lewat variabel lingkungan `NSD_P_*`; `shell=False`; timeout; batas output | `test_injection_rejected_before_execution`, `test_params_via_env_not_script` |
| Aturan tidak bisa menjalankan perintah bebas | Aksi hanya dari allowlist bertipe; operasi berbahaya masuk daftar larangan; risiko high/security_sensitive wajib `blocked` | `test_rejections`, `test_bad_files_do_not_load` |
| Tidak melemahkan keamanan | Tidak ada operasi untuk menonaktifkan firewall, mengaktifkan SMB1/guest, memberi Everyone Full Control, dll. | `test_shipped_rules_never_weaken_security` |
| Tidak menyimpan kata sandi | Tidak ada input kredensial; pola rahasia disaring sebelum DB/log/laporan | `test_secrets`, `test_roundtrip_and_audit` |
| Laporan aman dibagikan | Penyamaran default aktif + pratinjau di UI | `test_text_redacted_by_default` |
| DB rusak tidak menghilangkan bukti | Dikarantina ke `*.corrupt-<ts>`, bukan dihapus | `test_corrupt_db_is_quarantined_not_deleted` |
| Integritas aturan terlacak | Digest SHA-256 berkas aturan dicatat di setiap kasus | `test_digest_changes_with_content` |

## Batasan yang diketahui
- Aturan dimuat dari berkas lokal **tanpa tanda tangan**. Siapa pun yang bisa menulis folder `rules/` dapat mengubah saran/teks aturan (aksi tetap dibatasi allowlist). Tanda tangan aturan: Fase 6.
- Folder data portabel di drive jaringan/folder yang dapat ditulis orang lain → aplikasi memperingatkan, tidak memblokir.
- Riwayat lokal menyimpan nama target apa adanya (agar kasus bisa diulang). Penyamaran hanya diterapkan pada ekspor/laporan.
- Nama share dengan karakter `& % ' ; ( ) [ ] { } ~ # @ , = + ^ !` ditolak di Fase 1 (trade-off keamanan; mis. "R&D").
- Konten pesan error Windows di bukti bisa memuat nama/jalur; tersaring hanya oleh penyamaran saat ekspor.
- Eksekusi perbaikan, elevasi UAC, snapshot/rollback: **belum ada** (Fase 2).

## Melaporkan celah
Buka isu privat kepada pemelihara proyek; jangan menyertakan laporan yang tidak disamarkan.
