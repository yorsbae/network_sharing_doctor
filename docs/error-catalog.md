# Katalog error (backlog awal — bukan peta kode→perbaikan)

| Kode | Perlakuan di aplikasi | Aturan |
|---|---|---|
| 0x0000011B | Petunjuk (rendah); tidak ada override registry | PRN-11B-001 |
| 0x00000709 | Petunjuk (rendah) | PRN-709-001 |
| 0x00000005 / 0x80070005 | Boost bukti akses ditolak; petunjuk bila tanpa bukti | FLD-ACCESS-001, PRN-ACCESS-001, GEN-HINT-001 |
| 0x80070035 / 0x800704CF | Boost DNS/445; petunjuk bila tanpa bukti | NET-NAME-001, NET-SMB-001, GEN-HINT-002 |
| 0x80070043 | Boost share tidak ada | FLD-NOSHARE-001 |
| 0x8007052E | Boost logon gagal | FLD-LOGON-001 |
| 0x000006BA | Boost RPC tidak tersedia | PRN-RPC-001 |
| 0x00000006 / 0x00000016 | Hanya petunjuk; makna bergantung konteks | GEN-HINT-003 |

Makna tiap kode **belum dikonfirmasi** terhadap reproduksi nyata (lihat `docs/test-matrix.md` #8).
