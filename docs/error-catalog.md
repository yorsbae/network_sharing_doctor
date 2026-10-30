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

## Daftar error 0x: Printer Sharing

Perlakuan di aplikasi: setiap kode di bawah ini berupa **petunjuk berkeyakinan rendah** (aturan hanya-kode, baca-saja, tanpa aksi perbaikan).
Kode saja tidak pernah menjadi diagnosis; scan dengan kode itu tetap memeriksa bukti yang sebenarnya.
"0x000007e" dan "0x000007f" pada daftar sumber dibaca sebagai 0x0000007E dan 0x0000007F.

| Kode | Nama / penyebab | Aturan |
|---|---|---|
| 0x0000011B | Windows gagal terhubung ke shared printer, sering berkaitan dengan RPC dan keamanan printer | PRN-11B-001 |
| 0x00000709 | Operation could not be completed. Masalah koneksi atau konfigurasi default printer | PRN-709-001 |
| 0x00000040 | The specified network name is no longer available | PRN-40-001 |
| 0x0000007C | Windows tidak dapat menghubungkan printer melalui jaringan | PRN-7C-001 |
| 0x00000BCB | Windows cannot connect to the printer. Sering berkaitan dengan driver | PRN-BCB-001 |
| 0x00000002 | The system cannot find the file specified | PRN-02-001 |
| 0x00000005 | Access is denied. Masalah permission atau hak akses | PRN-ACCESS-001, GEN-HINT-001 |
| 0x0000000A | The environment is incorrect | PRN-0A-001 |
| 0x00000006 | The handle is invalid | GEN-HINT-003 |
| 0x00000057 | The parameter is incorrect | PRN-57-001 |
| 0x0000007E | The specified module could not be found | PRN-7E-001 |
| 0x0000007F | The specified procedure could not be found | PRN-7F-001 |
| 0x00000035 | The network path was not found | PRN-35-001 |
| 0x00000043 | The network name cannot be found | PRN-43-001 |
| 0x0000003A | The specified server cannot perform the requested operation | PRN-3A-001 |

## Daftar error 0x: Folder sharing

| Kode | Keterangan | Kemungkinan penyebab | Aturan |
|---|---|---|---|
| 0x80070035 | The network path was not found | Network Discovery / koneksi LAN | GEN-HINT-002, NET-NAME-001, NET-SMB-001 |
| 0x80004005 | Unspecified error | Permission, SMB, atau konfigurasi jaringan | FLD-UNSPEC-001 |
| 0x80070005 | Access is denied | Hak akses folder | FLD-ACCESS-001, GEN-HINT-001 |
| 0x80070043 | The network name cannot be found | Nama folder sharing salah | FLD-NOSHARE-001 (berbasis bukti; tanpa petunjuk hanya-kode) |
| 0x80070032 | The request is not supported | Protokol SMB tidak kompatibel | FLD-32-001 |
| 0x80070079 | The semaphore timeout period has expired | Koneksi jaringan timeout | FLD-79-001 |
| 0x80070020 | The process cannot access the file | File sedang digunakan proses lain | FLD-20-001 |
| 0x80070021 | The process cannot access the file because another process has locked a portion of the file | File terkunci | FLD-21-001 |
| 0x80070003 | The system cannot find the path specified | Path folder tidak ditemukan | FLD-03-001 |
| 0x80070002 | The system cannot find the file specified | File atau resource tidak ditemukan | FLD-02-001 |
| 0x80070006 | The handle is invalid | Handle tidak valid | FLD-06-001 |
| 0x80070057 | The parameter is incorrect | Parameter atau konfigurasi salah | FLD-57-001 |
| 0x80070015 | The device is not ready | Resource jaringan tidak siap | FLD-15-001 |

## Master list: popup error printer

Referensi dokumentasi. Pesan tanpa kode 0x (kategori 1 sampai 6, 8, dan 9) **belum menjadi aturan**: skema aturan mewajibkan
kode error atau kondisi bukti, sehingga pesan tanpa kode tidak dapat menghasilkan temuan. Kategori 7 memetakan pesan ke aturan di atas.

### 1. Ink & Cartridge Error

| No. | Popup error message |
|---|---|
| 1 | Ink has run out. |
| 2 | The ink cartridge cannot be recognized. |
| 3 | The ink cartridge is not installed correctly. |
| 4 | The installed ink cartridge is not compatible. |
| 5 | Ink system failure. |
| 6 | The printer cannot detect the ink level. |
| 7 | Ink leakage has been detected. |
| 8 | Ink supply system error. |
| 9 | The ink tube is blocked. |
| 10 | The ink tank is empty. |
| 11 | Ink overflow detected. |
| 12 | The ink cartridge is damaged. |
| 13 | Low ink warning. |
| 14 | Incorrect ink cartridge installed. |

### 2. Paper & Feeding Error

| No. | Popup error message |
|---|---|
| 15 | A paper jam has occurred. |
| 16 | Paper is jammed inside the printer. |
| 17 | Remove the jammed paper. |
| 18 | The printer cannot feed paper. |
| 19 | Paper feed error. |
| 20 | No paper loaded. |
| 21 | Paper size mismatch. |
| 22 | Paper type mismatch. |
| 23 | Multiple sheets of paper have been fed. |
| 24 | Paper is not loaded correctly. |
| 25 | Foreign object detected inside the printer. |
| 26 | The paper tray is not installed correctly. |
| 27 | Paper cassette is empty. |
| 28 | Paper pickup roller error. |
| 29 | Paper sensor error. |

### 3. Printhead & Print Quality Error

| No. | Popup error message |
|---|---|
| 30 | Print head error. |
| 31 | Printhead temperature error. |
| 32 | Printhead is not detected. |
| 33 | Printhead cleaning failed. |
| 34 | Printhead nozzle is clogged. |
| 35 | Print quality is poor. |
| 36 | Printing is faded or incomplete. |
| 37 | Incorrect color output. |
| 38 | Blank pages are being printed. |
| 39 | Printhead alignment failed. |
| 40 | Printhead maintenance required. |

### 4. Mechanical & Hardware Error

| No. | Popup error message |
|---|---|
| 41 | Printer hardware error has occurred. |
| 42 | The printer carriage cannot move. |
| 43 | Carriage movement error. |
| 44 | The printer cover is open. |
| 45 | Foreign object detected. |
| 46 | Abnormal printer noise detected. |
| 47 | Printer motor error. |
| 48 | Roller mechanism error. |
| 49 | Encoder strip error. |
| 50 | Scanner error has occurred. |
| 51 | Printer mechanism is blocked. |
| 52 | Printer requires servicing. |

### 5. Waste Ink & Maintenance Error

| No. | Popup error message |
|---|---|
| 53 | Ink pad is at the end of its service life. |
| 54 | The printer's ink pads are nearing the end of their service life. |
| 55 | Waste ink absorber is full. |
| 56 | Maintenance box is full. |
| 57 | Waste ink counter overflow. |
| 58 | Ink purge system error. |
| 59 | Printer maintenance required. |
| 60 | Cleaning cycle failed. |
| 61 | The printer requires maintenance reset. |

### 6. Connection & Communication Error

| No. | Popup error message |
|---|---|
| 62 | Printer is offline. |
| 63 | Printer not responding. |
| 64 | Communication error. |
| 65 | Cannot communicate with the printer. |
| 66 | The printer is not detected. |
| 67 | Unable to connect to the printer. |
| 68 | USB device not recognized. |
| 69 | Network printer connection failed. |
| 70 | The printer driver is unavailable. |
| 71 | Printer connection interrupted. |
| 72 | The printer is busy. |

### 7. Windows & Printer Sharing Error

| No. | Kode | Popup / error message | Aturan |
|---|---|---|---|
| 73 | 0x0000011B | Windows cannot connect to the printer. | PRN-11B-001 |
| 74 | 0x00000709 | Operation could not be completed. | PRN-709-001 |
| 75 | 0x00000BCB | Windows cannot connect to the printer. | PRN-BCB-001 |
| 76 | 0x00000005 | Access is denied. | PRN-ACCESS-001, GEN-HINT-001 |
| 77 | 0x00000002 | The system cannot find the file specified. | PRN-02-001 |
| 78 | 0x0000007C | Printer connection error. | PRN-7C-001 |
| 79 | 0x80070035 | The network path was not found. | GEN-HINT-002 |
| 80 | 0x80004005 | Unspecified error. | FLD-UNSPEC-001 |
| 81 | 0x80070005 | Access is denied. | FLD-ACCESS-001, GEN-HINT-001 |
| 82 | 0x80070043 | The network name cannot be found. | FLD-NOSHARE-001 |
| 83 | 0x80070032 | The request is not supported. | FLD-32-001 |
| 84 | 0x00000057 | The parameter is incorrect. | PRN-57-001 |

### 8. Print Spooler & Print Queue Error

| No. | Popup error message |
|---|---|
| 85 | Print Spooler service is not running. |
| 86 | The print spooler service has stopped unexpectedly. |
| 87 | Error printing document. |
| 88 | Print job failed. |
| 89 | Unable to delete print job. |
| 90 | The document failed to print. |
| 91 | Print queue is blocked. |
| 92 | The printer cannot complete the print job. |
| 93 | Printer driver installation failed. |
| 94 | Print processor does not exist. |

### 9. Power, Firmware & Electronics Error

| No. | Popup error message |
|---|---|
| 95 | Printer power error. |
| 96 | Printer firmware error. |
| 97 | Printer internal error. |
| 98 | Mainboard communication error. |
| 99 | Printer overheating. |
| 100 | Power supply failure. |
| 101 | Printer has stopped working unexpectedly. |
| 102 | Printer initialization failed. |
| 103 | Control panel error. |
| 104 | Printer system error. |
