# Matriks uji & validasi yang masih harus dilakukan di Windows

Semua butir di bawah **belum dijalankan** (sandbox pengembangan tidak punya Windows). Isi kolom hasil saat diuji.

| # | Yang divalidasi | Cara | Windows | Hasil |
|---|---|---|---|---|
| 1 | Seluruh skrip di `windows/powershell.py` berjalan & mengeluarkan JSON valid | `tests/integration_windows` | 10 / 11 | — |
| 2 | ID grup firewall `@FirewallAPI.dll,-32752` = "File and Printer Sharing" (juga di OS non-Inggris) | `test_firewall_group_id_is_valid` | 10 / 11 | — |
| 3 | Klasifikasi `test_unc`: access denied, share tidak ada, host tidak ada, logon gagal, konflik kredensial | 2 VM, workgroup | 11 | — |
| 4 | `Get-Printer -ComputerName` pada server nyata: akses ditolak vs RPC tidak tersedia | 2 VM + printer virtual | 11 | — |
| 5 | Hak non-admin: operasi mana yang gagal (`Get-SmbServerConfiguration`, event log) dan pesannya | akun standar | 11 | — |
| 6 | Domain vs workgroup, profil Publik/Privat | VM domain | 11 | — |
| 7 | Windows Server (2019/2022/2025): kompatibilitas cmdlet | VM Server | Server | — |
| 8 | Kode error (0x11B, 0x709, 0x5, 0x35, 0x43): reproduksi & konfirmasi aturan | lab LAN | 10/11 | — |
| 9 | Build PyInstaller berjalan di VM bersih tanpa Python, akun standar, jalur non-ASCII | `scripts/build_windows.ps1` | 11 | — |
| 10 | UI PySide6 dirender dan alur scan→ekspor berfungsi | manual | 11 | — |
| 11 | Alur perbaikan nyata PRN-SPOOLER-001 (stop → repair → verifikasi → rollback → pulihkan), hak admin vs non-admin, Spooler Disabled | `NSD_RUN_MUTATING=1`, VM LAB saja, sebagai Administrator | 11 | — |
| 12 | `repair --confirm` ditolak bila bukan admin / eksekusi nonaktif, tanpa efek samping | CLI di VM | 11 | — |
| 13 | `nsd autostart install` mode logon-user: tugas terbuat, jalan saat logon, instans tunggal | VM, akun standar | 11 | — |
| 14 | `autostart install --mode boot-system` dari Program Files: tugas terbuat, `icacls` benar (SID, bukan nama lokal), jalan saat boot tanpa login, akun standar tidak bisa menulis folder data | VM, admin | 11 (juga lokal non-Inggris) | — |
| 15 | Penolakan mode boot-system dari folder pengguna; `status`/`uninstall` | VM | 11 | — |
| 16 | Monitor jalan berhari-hari: memori stabil, interval, pemulihan saat jaringan putus | VM lab | 11 | — |
| 17 | Halaman Server: `Get-Service LanmanServer`, nama komputer (`os_info`), printer dibagikan, alamat IP lokal sesuai jaringan aktif (Wi-Fi/LAN, VPN, banyak adapter) | 2 VM, printer virtual | 11 | — |
| 18 | Halaman Client: *Cari server di jaringan* menemukan VM server (port 445, nama lewat DNS balik/NetBIOS), perilaku saat DNS balik lambat, dan tidak mengganggu jaringan | 2 VM satu subnet | 11 | — |
| 19 | Halaman Client: *Lihat printer di server* membedakan server mati, nama salah, akses ditolak, RPC tidak tersedia; alamat `\\SERVER\Printer` dari Win+R memasang printer | 2 VM | 11 | — |
| 20 | Tampilan Dashboard/Server/Client pada 980x600 dan DPI 125%/150% (tidak terpotong/meluap) | manual | 11 | — |
