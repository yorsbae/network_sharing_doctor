# Network Sharing Doctor (NSD) — Vision.md

**Versi dokumen:** 0.2 (dirapikan dari draf 0.1)
**Status proyek:** lihat [`progres.md`](progres.md)

Dokumen ini menyatukan dua bagian yang sebelumnya tercampur dalam satu file:

- **Bagian A — Visi Produk** (Bahasa Indonesia): masalah, tujuan, prinsip, fitur, UX, keterbatasan Windows.
- **Bagian B — Technical Design** (English): arsitektur, rule engine, kebijakan otomatisasi, snapshot/rollback, model data, pengujian, roadmap.
- **Bagian C — Keputusan implementasi sementara**: jawaban atas "Pertanyaan yang Masih Perlu Diputuskan" (A.13) yang diambil agar pengembangan Fase 1 dapat berjalan. Keputusan ini boleh diubah; setiap perubahan dicatat di `progres.md`.

Jika Bagian A dan Bagian B berbeda, **prinsip keselamatan yang lebih ketat yang berlaku**.

---

## Bagian A — Visi Produk
### 1. Ringkasan Proyek

**Network Sharing Doctor** adalah aplikasi utilitas Windows untuk membantu menyiapkan, memeriksa, memperbaiki, dan memelihara koneksi **printer sharing** serta **folder sharing** di jaringan lokal (LAN).

Aplikasi dirancang agar mudah dipakai oleh pengguna nonteknis maupun administrator. Tujuannya bukan sekadar melakukan ping atau memastikan PC server hidup, tetapi memeriksa rangkaian konfigurasi Windows yang diperlukan agar client benar-benar dapat terhubung ke printer atau folder yang dibagikan.

Satu aplikasi yang sama dapat dijalankan pada komputer dengan peran **Server** atau **Client**. Peran ditentukan secara eksplisit di konfigurasi; keduanya bukan aplikasi yang berbeda.

### 2. Masalah yang Ingin Diselesaikan

Masalah umum pada Windows sharing yang ingin dibantu oleh aplikasi:

- Client tidak dapat menemukan komputer server di jaringan.
- Server ditemukan atau ping berhasil, tetapi koneksi printer/folder sharing tetap gagal.
- Printer terlihat di jaringan, tetapi gagal ditambahkan atau dihubungkan.
- Windows menampilkan kode kesalahan koneksi seperti `0x00000006`, `0x00000016`, atau kode `0x...` lain yang ditemui pada proses sharing.
- Printer sudah terhubung, tetapi pekerjaan cetak gagal atau pengaturan printer di client tidak sesuai.
- Ukuran kertas khusus tidak tersedia atau tidak bisa dipilih dari aplikasi client.
- Pengaturan Network Discovery, File and Printer Sharing, firewall, layanan Windows, izin akses, nama komputer, jalur UNC, driver, atau konfigurasi sharing tidak konsisten.
- Folder sharing tidak bisa dibuka karena masalah nama host, jalur share, izin, kredensial, firewall, atau layanan jaringan.
- Pengguna harus mencoba banyak langkah manual yang sulit diingat dan rawan salah.

**Prinsip penting:** ping berhasil hanya membuktikan bahwa perangkat dapat dijangkau melalui ICMP. Itu tidak membuktikan bahwa SMB, RPC, spooler, printer sharing, autentikasi, driver, atau izin akses berfungsi.

### 3. Tujuan Produk

1. Mempermudah konfigurasi awal server dan client untuk printer serta folder sharing.
2. Menemukan penyebab kegagalan melalui pemeriksaan berurutan, bukan hanya mengandalkan ping.
3. Menyediakan perbaikan otomatis untuk masalah yang penyebab dan langkah perbaikannya sudah diketahui.
4. Menjelaskan hasil pemeriksaan dan perubahan dengan bahasa yang mudah dipahami.
5. Menghindari perubahan konfigurasi yang tidak relevan, berisiko, atau tidak dapat dipulihkan.
6. Memisahkan konfigurasi server dan client agar target koneksi serta printer yang dipakai tidak tertukar.
7. Menjadi fondasi yang dapat diperluas dengan pemeriksaan, aturan perbaikan, dan kode kesalahan baru.

### 4. Prinsip dan Keputusan Arsitektur

#### 4.1 Satu aplikasi, peran terpisah

- Aplikasi yang sama dapat berjalan sebagai **Server**, **Client**, atau menyediakan mode pemeriksaan sesuai kebutuhan.
- Peran komputer harus dipilih atau ditetapkan secara eksplisit.
- Pengaturan khusus server tidak boleh otomatis dianggap sebagai pengaturan client, dan sebaliknya.
- Status, tindakan, dan hasil pemeriksaan harus menunjukkan komputer mana yang sedang diperiksa.

#### 4.2 Client menentukan target koneksi

Client harus memiliki target server yang eksplisit, misalnya nama komputer atau alamat IP, serta nama share yang ingin digunakan.

- Sediakan pilihan penemuan server secara **manual dan otomatis** (`manual_auto`).
- Pengguna dapat memasukkan atau memilih target secara manual.
- Penemuan otomatis membantu menemukan kandidat, tetapi tidak boleh diam-diam mengganti target yang telah dipilih.
- Tampilkan identitas target sebelum melakukan perbaikan atau menyambungkan printer/folder.
- Hindari salah koneksi ketika ada beberapa server atau beberapa printer dengan nama serupa.

#### 4.3 Pemilihan printer di sisi server menggunakan Registry

- Server menjadi tempat untuk memilih printer Windows yang benar-benar terpasang/terhubung dan akan dibagikan.
- Informasi pilihan printer disimpan atau dibaca melalui **Windows Registry** sesuai rancangan implementasi.
- Aplikasi harus memvalidasi pilihan terhadap printer yang benar-benar terdaftar di Windows; Registry tidak boleh menjadi satu-satunya bukti bahwa printer masih tersedia.
- Tampilkan nama printer, status, driver, dan nama share yang relevan sebelum menerapkan konfigurasi.
- Jangan mengubah printer default atau share lain tanpa persetujuan yang sesuai.

#### 4.4 Ukuran kertas diatur dari sisi client

- Pengguna client perlu dapat mengatur atau menambahkan ukuran kertas khusus dari client, tanpa harus selalu melakukan perubahan langsung di komputer server.
- Contoh kebutuhan: ukuran kertas khusus seperti **210 × 330 mm**.
- Aplikasi harus memeriksa kemampuan driver dan jenis koneksi printer yang digunakan, lalu menjelaskan apakah ukuran kertas dapat ditambahkan di client atau bergantung pada driver/server.
- Jangan menjanjikan bahwa semua driver atau semua model printer mendukung ukuran kertas khusus dari client.
- Jangan mengubah konfigurasi global server hanya untuk memenuhi kebutuhan satu client tanpa konfirmasi.

### 5. Cakupan Fitur

#### 5.1 Dashboard dan pemeriksaan cepat

Dashboard menampilkan status peran komputer, target server/client, konektivitas, printer sharing, folder sharing, dan masalah yang ditemukan.

Status pemeriksaan sebaiknya dibedakan menjadi:
- **Berfungsi** — pengujian yang relevan berhasil.
- **Perlu perhatian** — ada konfigurasi yang tidak ideal tetapi belum tentu menghalangi fungsi.
- **Gagal** — ada pemeriksaan yang terbukti gagal.
- **Belum diperiksa** — belum ada bukti yang cukup.

Hindari indikator hijau hanya berdasarkan ping atau karena nama server ditemukan.

#### 5.2 Wizard konfigurasi Server

- Menampilkan printer lokal yang tersedia.
- Memungkinkan pemilihan printer yang akan dibagikan.
- Memeriksa status printer dan driver.
- Memeriksa nama share serta status sharing.
- Memeriksa layanan Windows yang diperlukan.
- Memeriksa Network Discovery, File and Printer Sharing, firewall, dan konfigurasi jaringan yang relevan.
- Menampilkan jalur akses yang dapat dipakai client, misalnya `\\NAMA-SERVER\NAMA-SHARE`.
- Menyediakan pemeriksaan folder sharing secara terpisah dari printer sharing.
- Memberi peringatan sebelum mengubah pengaturan keamanan atau akses.

#### 5.3 Wizard konfigurasi Client

- Mengatur target server secara manual atau menemukan kandidat secara otomatis.
- Menguji resolusi nama host dan konektivitas.
- Menguji akses ke jalur UNC dan layanan yang diperlukan, bukan hanya ping.
- Menampilkan printer share yang tersedia pada target yang dipilih.
- Membantu menghubungkan printer dan memeriksa status hasilnya.
- Membantu membuka atau memetakan folder share sesuai izin pengguna.
- Memeriksa driver, kredensial, izin, dan kompatibilitas yang relevan.
- Mengelola kebutuhan ukuran kertas khusus di sisi client sejauh didukung driver dan Windows.

#### 5.4 Auto-fix dan diagnosis kode kesalahan

Aplikasi memiliki mesin diagnosis dan perbaikan berbasis aturan (*rule-based diagnostics and repair*).

Alur yang diharapkan:

1. Mengumpulkan konteks: peran komputer, versi Windows, target, jenis share, operasi yang gagal, dan kode kesalahan lengkap.
2. Menjalankan pemeriksaan yang aman dan relevan.
3. Mengelompokkan kemungkinan penyebab berdasarkan bukti.
4. Menampilkan penyebab yang terdeteksi, tingkat keyakinan, dan dampaknya.
5. Menawarkan perbaikan otomatis hanya jika aturan cocok dan tindakan aman.
6. Meminta persetujuan untuk perubahan yang memengaruhi firewall, layanan, kredensial, Registry, driver, atau keamanan.
7. Menyimpan catatan tindakan sebelum dan sesudah perbaikan.
8. Menguji ulang operasi yang sebelumnya gagal.
9. Jika belum berhasil, membatalkan perubahan yang dapat dipulihkan atau memberi instruksi lanjutan yang spesifik.

Kode seperti `0x00000006`, `0x00000016`, dan kode `0x...` lain perlu diperlakukan sebagai petunjuk, bukan diagnosis final. Makna kode dapat bergantung pada API, tahap koneksi, driver, dan konteks operasi. Aplikasi harus merekam pesan kesalahan lengkap serta tahap ketika error terjadi.

Targetnya adalah **mendeteksi dan memperbaiki sebanyak mungkin masalah umum secara otomatis**, bukan mengklaim mampu memperbaiki semua kode `0x...` atau semua kondisi Windows.

#### 5.5 Pemeriksaan berlapis

Diagnosis printer sharing sebaiknya memisahkan lapisan-lapisan berikut:

1. **Target** — nama komputer, alamat IP, dan pilihan server benar.
2. **Jaringan** — konektivitas dasar tersedia.
3. **Resolusi nama** — nama server dapat diresolusikan bila digunakan.
4. **Layanan dan protokol** — layanan/protokol yang diperlukan untuk jenis sharing dapat diakses.
5. **Firewall** — aturan relevan mengizinkan koneksi yang diperlukan.
6. **Sharing** — printer/folder benar-benar dibagikan dan nama share cocok.
7. **Autentikasi dan izin** — akun memiliki hak akses yang diperlukan.
8. **Driver dan spooler** — driver sesuai, Print Spooler berjalan, dan jalur pemasangan printer berfungsi.
9. **Kebijakan Windows** — kebijakan keamanan atau pembaruan Windows tidak menghalangi koneksi.
10. **Operasi akhir** — printer benar-benar bisa dipasang/diakses dan, bila sesuai, pengujian cetak atau akses folder berhasil.

Urutan pemeriksaan dapat berubah berdasarkan gejala. Misalnya, keberhasilan ping tidak boleh membuat pemeriksaan berhenti ketika penambahan printer masih gagal.

#### 5.6 Folder sharing

- Memeriksa jalur UNC seperti `\\SERVER\SHARE`.
- Membedakan masalah server tidak ditemukan, share tidak ada, akses ditolak, kredensial bermasalah, dan SMB tidak dapat dijangkau.
- Memeriksa izin share dan izin filesystem secara terpisah bila hak pemeriksaan mencukupi.
- Tidak mengubah izin menjadi akses luas hanya untuk menghilangkan error.
- Tidak menyimpan atau menampilkan kata sandi dalam log.

#### 5.7 Log dan laporan

- Riwayat diagnosis dan tindakan perbaikan.
- Waktu, komputer, peran, target, kode error, hasil pemeriksaan, serta tindakan yang dilakukan.
- Penyaringan log berdasarkan jenis masalah dan hasil.
- Ekspor laporan teks atau format terstruktur untuk membantu dukungan teknis.
- Rahasiakan kredensial, token, dan informasi sensitif; sediakan opsi untuk menyamarkan nama pengguna atau alamat yang sensitif.

### 6. Keterbatasan Windows yang Harus Diperhitungkan

1. **Printer sharing bergantung pada driver.** Fitur, ukuran kertas, dan preferensi cetak dapat berbeda antara driver server dan client.
2. **Custom paper size tidak selalu dapat dipaksakan dari client.** Sebagian driver menyimpan formulir atau preferensi pada server, sebagian memungkinkan pengaturan lokal, dan sebagian membatasi ukuran yang didukung perangkat.
3. **Ping bukan tes sharing.** ICMP bisa berhasil meskipun SMB/RPC atau proses pemasangan printer gagal.
4. **Windows dapat membatasi instalasi driver.** Kebijakan keamanan, hak administrator, Point and Print, pembaruan, serta versi Windows dapat memengaruhi pemasangan.
5. **Perubahan keamanan harus hati-hati.** Menonaktifkan firewall, mengaktifkan guest access, mengaktifkan SMB versi lama, atau melonggarkan autentikasi secara luas bukan perbaikan default.
6. **Tidak semua error punya satu penyebab.** Kode yang sama bisa muncul pada tahap dan kondisi berbeda.
7. **Hak akses aplikasi terbatas.** Pemeriksaan tertentu membutuhkan hak administrator. Jika hak tidak tersedia, aplikasi harus menyatakan batasan dan tidak berpura-pura telah memperbaiki masalah.
8. **Perubahan tertentu memerlukan restart layanan, sesi baru, atau restart komputer.** Aplikasi perlu menjelaskan konsekuensi sebelum tindakan dijalankan.

### 7. Keamanan dan Kepercayaan

- Jalankan pemeriksaan baca-saja terlebih dahulu sebelum melakukan perubahan.
- Terapkan prinsip hak akses minimum.
- Jangan menonaktifkan firewall atau proteksi keamanan secara menyeluruh sebagai solusi otomatis.
- Jangan mengaktifkan SMB1 atau guest access sebagai solusi umum.
- Jangan mengubah kebijakan Point and Print atau kebijakan keamanan tanpa penjelasan, persetujuan, dan aturan yang tervalidasi.
- Jangan menghapus driver, koneksi printer, kredensial, atau share secara otomatis tanpa konfirmasi.
- Catat perubahan dan sediakan pemulihan sejauh perubahan dapat dibalik.
- Bedakan dengan jelas antara **terdeteksi**, **disarankan**, **disetujui**, **diterapkan**, dan **berhasil diverifikasi**.
- Aplikasi tidak boleh mengklaim perbaikan berhasil sebelum pengujian ulang mendukung klaim tersebut.

### 8. Pengalaman Pengguna (UI/UX)

Antarmuka harus sederhana, berbahasa Indonesia, dan berorientasi pada tindakan.

Menu utama yang disarankan:
- **Beranda**
- **Mode Server**
- **Mode Client**
- **Perbaiki Masalah**
- **Printer dan Ukuran Kertas**
- **Folder Sharing**
- **Riwayat dan Laporan**
- **Pengaturan**

Untuk setiap masalah, tampilkan:
- Apa yang gagal.
- Target komputer dan jenis koneksi yang diperiksa.
- Kode serta pesan error lengkap jika tersedia.
- Hasil pemeriksaan yang menjadi bukti.
- Kemungkinan penyebab.
- Tombol **Periksa Ulang** dan **Perbaiki Otomatis** jika layak.
- Risiko atau dampak tindakan.
- Hasil pengujian setelah perbaikan.

Jangan menampilkan daftar panjang kode error tanpa penjelasan atau langsung menjalankan banyak perubahan tanpa memberi tahu pengguna.

### 9. Rancangan Teknis Tingkat Tinggi

Implementasi ditujukan untuk Windows dan jaringan lokal. Pilihan bahasa, framework UI, penyimpanan konfigurasi, serta mekanisme elevasi administrator dapat diputuskan pada tahap desain teknis.

Komponen logis:
- **UI** — wizard, status, hasil diagnosis, dan persetujuan tindakan.
- **Role Manager** — membedakan mode Server dan Client.
- **Target Discovery** — penemuan manual dan otomatis.
- **Windows Diagnostics** — pemeriksaan jaringan, layanan, printer, share, izin, dan driver.
- **Rule Engine** — mencocokkan gejala, bukti, kode error, dan langkah diagnosis.
- **Repair Executor** — menjalankan tindakan yang disetujui dengan validasi hak akses.
- **Printer Configuration** — pemilihan printer server melalui Registry dengan validasi ke keadaan Windows aktual.
- **Client Paper Settings** — pemeriksaan dan pengaturan ukuran kertas yang didukung di sisi client.
- **Logging and Recovery** — merekam hasil, perubahan, dan opsi pemulihan.

Aturan diagnosis dan tindakan perbaikan sebaiknya terpisah dari antarmuka agar dapat diuji dan diperluas. Setiap aturan harus memuat kondisi pemicu, pemeriksaan konfirmasi, tindakan, kebutuhan hak administrator, tingkat risiko, langkah pemulihan, dan tes verifikasi.

### 10. Tahapan Pengembangan

#### Tahap 1 — Diagnosis baca-saja
- Memilih peran Server/Client.
- Menetapkan target client secara manual.
- Menjalankan penemuan otomatis sebagai bantuan.
- Memeriksa jaringan, resolusi nama, printer, share, layanan, dan error.
- Menyediakan laporan diagnosis tanpa mengubah konfigurasi.

#### Tahap 2 — Perbaikan dasar yang aman
- Memperbaiki konfigurasi sederhana yang terdeteksi jelas.
- Memeriksa dan membantu mengaktifkan fitur sharing yang diperlukan.
- Memeriksa layanan Windows dan status printer.
- Meminta persetujuan untuk perubahan yang berdampak.
- Menjalankan tes ulang dan mencatat hasil.

#### Tahap 3 — Alur printer server/client
- Pemilihan printer di server melalui Registry dengan validasi.
- Validasi nama share dan jalur target.
- Bantuan pemasangan printer di client.
- Diagnosis kegagalan koneksi walaupun ping berhasil.
- Pemeriksaan kompatibilitas driver dan ukuran kertas khusus.

#### Tahap 4 — Folder sharing dan diagnosis lanjutan
- Diagnosis SMB, jalur UNC, autentikasi, dan izin.
- Penambahan aturan error berdasarkan bukti kasus nyata.
- Laporan, ekspor, dan riwayat perbaikan.

#### Tahap 5 — Penguatan dan pemeliharaan
- Uji pada beberapa versi Windows dan konfigurasi jaringan.
- Uji hak akses biasa versus administrator.
- Uji kegagalan dan pemulihan.
- Dokumentasi aturan perbaikan dan batasannya.
- Penambahan aturan baru secara terkontrol, berdasarkan log yang sudah disamarkan.

### 11. Kriteria Keberhasilan

Produk dianggap bermanfaat apabila:

- Pengguna dapat membedakan masalah server tidak ditemukan dari masalah koneksi sharing.
- Kegagalan tetap terdiagnosis ketika ping berhasil tetapi printer/folder tidak bisa diakses.
- Target server dan printer yang dipilih terlihat jelas sehingga risiko salah koneksi berkurang.
- Aplikasi menjelaskan penyebab berdasarkan hasil tes, bukan sekadar menebak dari kode error.
- Perbaikan otomatis aman, dapat diaudit, dan selalu diverifikasi ulang.
- Pengaturan ukuran kertas di client ditangani sesuai kemampuan driver, dengan keterbatasan yang dijelaskan.
- Kasus yang tidak bisa diperbaiki otomatis menghasilkan langkah diagnosis lanjutan yang spesifik dan laporan yang berguna.

### 12. Di Luar Cakupan Awal

- Menjamin perbaikan semua error Windows atau semua kode `0x...`.
- Mem-bypass autentikasi, hak akses, atau kebijakan keamanan organisasi.
- Memaksa semua driver mendukung ukuran kertas khusus.
- Mengaktifkan protokol lama atau melemahkan keamanan secara otomatis.
- Mengelola print server enterprise berskala besar atau layanan cloud sebagai fitur awal.
- Melakukan perubahan tersembunyi tanpa persetujuan atau pencatatan.

### 13. Pertanyaan yang Masih Perlu Diputuskan

Pertanyaan berikut ditunda sampai rancangan teknis dibahas bersama:

1. Versi Windows minimum yang akan didukung.
2. Bentuk aplikasi: portable tanpa instalasi, installer, atau keduanya.
3. Apakah fitur tertentu berjalan sebagai proses biasa dan meminta elevasi hanya saat diperlukan, atau memakai komponen layanan terpisah.
4. Metode penyimpanan konfigurasi dan log.
5. Batas penemuan otomatis: subnet lokal saja atau daftar rentang jaringan yang dapat ditentukan pengguna.
6. Jenis tes cetak yang aman untuk validasi koneksi.
7. Kebijakan retensi log dan penyamaran informasi sensitif.
8. Daftar kode error prioritas berdasarkan kasus nyata yang paling sering muncul.

---

**Ringkasan keputusan saat ini**
- Satu aplikasi dapat digunakan di komputer server maupun client.
- Peran PC dipisahkan secara eksplisit.
- Client mengatur target koneksi.
- Penemuan server mendukung cara manual dan otomatis.
- Pemilihan printer yang dibagikan dilakukan di server, menggunakan Registry dengan validasi.
- Pengaturan ukuran kertas menjadi kebutuhan sisi client, dengan batasan driver/Windows yang harus dijelaskan.
- Diagnosis tidak berhenti pada ping; aplikasi harus memeriksa jalur koneksi sharing yang sebenarnya.
- Auto-fix menggunakan aturan yang teruji, persetujuan sesuai risiko, pencatatan, dan verifikasi ulang.
- Tidak ada klaim bahwa semua error `0x...` pasti dapat diperbaiki otomatis.

---

## Bagian B — Technical Design

**Version:** 0.1 --- Draft\
**Target:** Windows 10/11 and compatible Windows Server editions\
**Packaging:** Portable Windows application\
**Primary language:** Python\
**UI:** PySide6\
**Local storage:** SQLite + JSON configuration\
**Purpose:** Diagnose and repair Windows network printer and folder
sharing issues with safe, policy-controlled automation.

------------------------------------------------------------------------

### 1. Product vision

Network Sharing Doctor is a portable Windows troubleshooting utility
that identifies why a shared printer or folder is inaccessible, selects
a cause-specific repair, executes only authorized actions, and verifies
the result.

The product optimizes for: 1. **Correctness:** diagnose before changing
settings. 2. **Safety:** least privilege, explicit policies, and
reversible changes where possible. 3. **Transparency:** explain the
cause, planned changes, and result in plain language. 4.
**Repeatability:** use versioned rules and structured diagnostics rather
than a pile of generic commands. 5. **Portability:** no separate
database server or mandatory installation. 6. **Evidence:** log checks,
actions, exit codes, and verification results.

#### Non-goals

-   Guaranteeing every Windows error can be repaired automatically.
-   Bypassing organizational Group Policy, domain policy, endpoint
    security, or administrator restrictions.
-   Automatically weakening security (for example, enabling SMB1,
    allowing unauthenticated guest access, or disabling the firewall)
    merely to make sharing work.
-   Replacing vendor printer drivers or repairing hardware physically.
-   Acting as an unapproved remote administration or persistence tool.

### 2. Supported scope

#### Initial targets

-   Windows 10 and Windows 11, subject to the actual servicing/support
    status of the installed edition.
-   Windows Server versions that support the relevant PowerShell
    cmdlets, services, SMB features, and printer APIs. Validate each
    supported server release during implementation; do not assume all
    client and server versions behave identically.

#### Sharing scenarios

-   Client accesses a shared folder using `\\\\HOST\\Share`.
-   Client connects to a shared printer using `\\\\HOST\\PrinterShare`.
-   Host computer publishes a folder or printer.
-   Local network discovery and name-resolution failures.
-   Printer queue, Print Spooler, and connection/driver issues.
-   Share permissions, NTFS permissions, and authentication diagnostics.

#### Not automatically assumed

-   Workgroup versus Active Directory domain.
-   Static versus DHCP IP addressing.
-   Third-party antivirus/firewall products.
-   Printer vendor/model, driver architecture, or print server role.
-   Permission to change network profiles or organization-managed
    settings.

The application must detect or ask for these details when they affect
the proposed repair.

### 3. Product behavior and automation policy

Automation has three policy levels, selectable by an authorized
administrator:

1.  **Diagnose only** --- perform read-only checks.
2.  **Safe automatic repair** --- restart an appropriate service, clear
    a known recoverable queue condition after confirmation/policy,
    refresh name-resolution tests, or repair an application-owned
    setting when a clear rollback exists.
3.  **Administrator-approved advanced repair** --- apply an explicitly
    defined change to firewall rules, sharing settings, permissions,
    printer connection, or other machine configuration after presenting
    the impact and rollback status.

Even in maximum-automation mode: - Every rule must declare its
prerequisites, risk level, affected scope, verification, and rollback
behavior. - High-impact or security-reducing actions must remain blocked
by default. - Never disable Windows Firewall wholesale. - Never enable
SMB1 as a generic fix. - Never enable insecure guest SMB access as a
generic fix. - Never weaken Point and Print security or silently install
an untrusted driver. - Never grant `Everyone: Full Control` or
recursively rewrite permissions as a generic fix. - Never reset all
network settings or delete all printer drivers as the first-line
repair. - Respect Group Policy and managed-device controls. Report when
policy blocks a change instead of fighting policy. - Require
user-supplied credentials when credentials are needed; never collect or
store plaintext passwords in logs.

### 4. Architecture

Use a layered architecture with a small privileged execution boundary.

``` text
┌─────────────────────────────────────────────────────────────┐
│ PySide6 UI                                                   │
│ Dashboard | Diagnose | Repair Plan | History | Settings      │
└──────────────────────────────┬──────────────────────────────┘
                               │ typed requests/results
┌──────────────────────────────▼──────────────────────────────┐
│ Application service layer                                    │
│ Scan orchestration | case/session management | policy checks │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
┌───────────────▼──────────────┐  ┌─────▼─────────────────────┐
│ Diagnostic engine            │  │ Rule engine                │
│ Network, SMB, share, printer │  │ match → prerequisites      │
│ services, permissions, logs  │  │ risk → plan → execute      │
└───────────────┬──────────────┘  └─────┬─────────────────────┘
                │                       │
┌───────────────▼───────────────────────▼─────────────────────┐
│ Windows adapter layer                                        │
│ PowerShell/cmdlets | Win32 APIs | Service Control | Print API│
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ State & audit                                                 │
│ SQLite case history | JSON rule/config | snapshots | logs    │
└─────────────────────────────────────────────────────────────┘

Optional later: signed, narrow-scope elevated helper process.
```

#### Important design decision

Do not make the GUI run arbitrary shell strings. Build commands from
fixed, typed operations and validated parameters. Avoid `shell=True`;
use subprocess argument lists, explicit timeouts, output capture, and
allowlisted PowerShell scripts/cmdlets.

#### Privilege model

-   UI starts unelevated where practical.
-   Read-only diagnostics run without elevation whenever Windows
    permits.
-   When a repair needs elevation, request UAC elevation for a narrowly
    scoped operation or relaunch the application elevated after
    explaining why.
-   Do not store an administrator password or attempt to bypass UAC.
-   In a later hardened version, use a signed helper executable with a
    strict operation allowlist and validated request schema. The helper
    must reject arbitrary commands, paths, registry keys, and scripts.

### 5. Recommended technology stack

  -----------------------------------------------------------------------
  Area                    Choice                  Reason
  ----------------------- ----------------------- -----------------------
  Runtime                 Python 3.12 or another  Broad Windows
                          tested supported Python ecosystem; pin exact
                          release                 version in build
                                                  pipeline

  Desktop UI              PySide6                 Good native desktop UI
                                                  and layouts

  Packaging               PyInstaller `--onedir`  Easier troubleshooting
                          first; consider         and fewer
                          one-file only after     extraction/startup
                          testing                 complications

  Local database          SQLite                  No database server,
                                                  suitable for local case
                                                  history

  Configuration/rules     Versioned JSON or YAML  Reviewable rule
                                                  definitions; validate
                                                  with a schema

  Windows operations      PowerShell cmdlets,     Use supported Windows
                          Windows APIs,           interfaces where
                          service/print APIs      possible

  Tests                   pytest + mocked adapter Test rules without
                          tests + Windows VM      changing real PCs
                          integration tests       

  Logging                 Python `logging`,       Auditability and
                          rotating files,         bounded log size
                          structured JSON event   
                          records                 

  Installer/updates       Optional signed package Trust and controlled
                          later                   updates
  -----------------------------------------------------------------------

Pin dependencies and verify the packaged build on clean Windows virtual
machines. Do not promise one binary works on every Windows Server
edition until compatibility tests exist.

### 6. Suggested project structure

``` text
network-sharing-doctor/
├── README.md
├── vision.md
├── SECURITY.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements-lock.txt
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── supported-windows.md
│   ├── error-catalog.md
│   ├── rule-authoring.md
│   ├── test-matrix.md
│   └── troubleshooting.md
├── assets/
│   ├── icons/
│   └── styles/
├── rules/
│   ├── network.json
│   ├── smb-folder.json
│   ├── printer.json
│   └── security-baseline.json
├── scripts/
│   └── build_windows.ps1
├── src/
│   └── nsd/
│       ├── __init__.py
│       ├── main.py
│       ├── app_config.py
│       ├── bootstrap.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── dashboard_page.py
│       │   ├── diagnose_page.py
│       │   ├── repair_plan_page.py
│       │   ├── history_page.py
│       │   ├── settings_page.py
│       │   └── widgets/
│       ├── application/
│       │   ├── scan_service.py
│       │   ├── repair_service.py
│       │   ├── case_service.py
│       │   └── policy_service.py
│       ├── diagnostics/
│       │   ├── network.py
│       │   ├── name_resolution.py
│       │   ├── smb.py
│       │   ├── share_permissions.py
│       │   ├── printer.py
│       │   ├── spooler.py
│       │   └── windows_events.py
│       ├── rules/
│       │   ├── loader.py
│       │   ├── matcher.py
│       │   ├── planner.py
│       │   └── schema.py
│       ├── repairs/
│       │   ├── base.py
│       │   ├── service_repairs.py
│       │   ├── network_repairs.py
│       │   ├── smb_repairs.py
│       │   ├── printer_repairs.py
│       │   └── rollback.py
│       ├── windows/
│       │   ├── powershell.py
│       │   ├── privilege.py
│       │   ├── services.py
│       │   ├── firewall.py
│       │   ├── registry.py
│       │   ├── shares.py
│       │   └── print_api.py
│       ├── storage/
│       │   ├── database.py
│       │   ├── repositories.py
│       │   └── migrations/
│       └── security/
│           ├── redaction.py
│           ├── audit.py
│           └── allowlist.py
├── tests/
│   ├── unit/
│   ├── rules/
│   ├── integration_windows/
│   └── fixtures/
└── build/
```

Keep user data outside the application directory when possible, for
example under `%LOCALAPPDATA%\\NetworkSharingDoctor\\`. Portable mode
can instead use a clearly chosen `data/` directory beside the
executable, but must warn if that directory is writable by untrusted
users or located on a shared network drive.

### 7. Diagnostic workflow

1.  **Collect context:** local OS/version/build, role (client/host),
    workgroup/domain status where accessible, network profile, target
    hostname/IP, target share/printer, and exact error code/message.
2.  **Read-only scan:** link status, route/reachability, DNS resolution,
    relevant TCP connectivity, SMB client/server state, services, share
    existence, permissions, printer queue and spooler, recent relevant
    event logs.
3.  **Build evidence:** each check returns `pass`, `fail`, `warning`, or
    `unknown`, plus a short explanation and evidence reference.
4.  **Rank likely causes:** do not map an error code to one cause
    without supporting checks.
5.  **Create repair plan:** proposed actions, impact, required
    privilege, reboot requirement, rollback coverage, and verification
    steps.
6.  **Policy gate:** reject blocked actions; request consent for actions
    requiring it.
7.  **Snapshot:** save current values for each mutable setting before
    changing it.
8.  **Execute one action at a time:** bounded timeout, captured output,
    clear result.
9.  **Verify:** repeat the failed check and perform a real access test
    when possible.
10. **Rollback or escalate:** rollback if verification fails and
    rollback is safe; otherwise stop and explain what needs a
    technician.
11. **Generate report:** summary, cause, actions, outcomes,
    verification, and any remaining risks.

### 8. Error catalogue and rule-engine design

The hexadecimal code alone is not enough to choose a repair. Error
meanings can vary by API, operation, Windows version, and context. Store
the exact operation, error message, host/client role, and evidence.

#### Initial diagnostic catalogue

  --------------------------------------------------------------------------------------------------------
  Error / symptom              First checks           Candidate response        Automation policy
  ---------------------------- ---------------------- ------------------------- --------------------------
  `0x0000011B` when connecting OS updates/builds,     Identify the documented   Do not blindly add
  to shared printer            print server/client    cause for the affected    registry overrides or
                               context, RPC-related   builds; offer a supported weaken RPC security
                               events and policy      update/configuration path 

  `0x00000709` printer         Printer share path,    Repair a stale connection Safe cleanup only when the
  operation failed             existing connection,   or correct the selected   exact connection is
                               default printer state, printer when evidence     identified
                               spooler, driver and    supports it               
                               event logs                                       

  `0x00000005` / Access Denied User identity, share   Explain the specific      No broad
                               ACL, NTFS ACL,         missing permission; apply `Everyone: Full Control`
                               effective access,      least-privilege ACL       changes
                               admin/domain policy    change only if approved   

  `0x80070035` / network path  Host resolution,       Correct host/path or      Do not enable obsolete
  not found                    reachability, route,   network/name-resolution   protocols as a shortcut
                               target share name, SMB issue when proven         
                               connectivity                                     

  `0x80004005` / unspecified   Capture exact          Select a cause-specific   Never run a generic "reset
  failure                      operation; inspect     rule only after narrowing everything" action
                               authentication, SMB,   the cause                 
                               firewall and event                               
                               evidence                                         

  `0x80070043` / network name  Share name, host       Correct the share path or Snapshot service/config
  not found                    availability, server   restore the relevant      state first
                               service and published  sharing service if        
                               shares                 stopped                   

  Credentials repeatedly       Host identity,         Guide the user to         Never log passwords or
  requested                    credential target,     authenticate with the     silently change accounts
                               account state,         intended account; remove  
                               clock/domain, SMB      only a proven stale       
                               authentication logs    credential if approved    

  Folder opens but write fails Share permissions and  Explain whether share or  Avoid recursive permission
                               NTFS permissions;      NTFS permission blocks    rewrites
                               inherited ACLs;        the operation             
                               disk/volume state                                

  Host not visible in Network  Network profile,       Test direct UNC/IP access Visibility is not proof
  view                         discovery services,    first; adjust discovery   that sharing itself is
                               firewall rules, name   only if required and      broken
                               resolution             allowed                   

  Printer offline or queue     Printer                Restart relevant service  Do not clear every user's
  stuck                        reachability/status,   or clear only the         jobs by default
                               port, queue, spooler,  affected job/queue after  
                               driver events          policy permits            

  Printer share                Driver package,        Recommend trusted signed  Never silently install an
  connection/driver failure    architecture, Point    driver or supported       untrusted driver or weaken
                               and Print policy,      deployment method         Point and Print
                               print server events                              

  SMB                          SMB client/server      Identify mismatch and     Do not enable SMB1 or
  negotiation/authentication   configuration,         recommend a supported     insecure guest access
  failure                      dialect/security       compatible configuration  automatically
                               policy,                                          
                               signing/encryption                               
                               requirements, event                              
                               logs                                             

  Firewall blocks access       Active profile,        Add or enable the         Never disable the firewall
                               effective rules,       narrowest applicable      globally
                               target port and        built-in sharing rule     
                               listener               only when evidence        
                                                      supports it               

  Relevant service stopped     Service status,        Start the service if      Do not force startup-type
                               dependencies, startup  needed and allowed;       changes against managed
                               policy and event logs  preserve original startup policy
                                                      type                      

  Name works by IP but not     DNS/NetBIOS/LLMNR      Fix the appropriate       Do not permanently
  hostname                     policy, suffix, hosts  name-resolution source    hard-code IPs without
                               configuration, DNS                               documenting the trade-off
                               records                                          
  --------------------------------------------------------------------------------------------------------

Treat this table as a starting backlog, not a definitive code-to-fix
map. Confirm each code's meaning against the actual Windows API/event
source and a reproducible test case before shipping a repair rule.

#### Rule schema

Each rule should contain: - `id`, `version`, `title`, `description` -
`symptoms` and `error_codes` - `conditions` and `required_evidence` -
`os_constraints` - `risk`: `read_only`, `low`, `medium`, `high`,
`security_sensitive` - `requires_admin` - `auto_policy`:
`always_read_only`, `auto_if_approved`, `requires_confirmation`,
`blocked` - `actions`: typed operation identifiers and validated
parameters - `snapshot_keys` - `verification` - `rollback` -
`failure_message` and `escalation` - `references` to vendor
documentation and internal tests

Example conceptual rule:

``` json
{
  "id": "PRN-SPOOLER-001",
  "version": 1,
  "title": "Print Spooler is stopped",
  "risk": "low",
  "requires_admin": true,
  "auto_policy": "auto_if_approved",
  "conditions": [
    "target_is_local_printer_or_print_host",
    "spooler_service_is_stopped"
  ],
  "actions": [
    {
      "operation": "start_service",
      "service_name": "Spooler"
    }
  ],
  "verification": [
    "spooler_service_is_running",
    "repeat_original_printer_test"
  ],
  "rollback": {
    "type": "restore_service_state_if_safe"
  }
}
```

This is an illustrative schema. Production rules must be validated,
allowlisted, tested on each supported Windows family, and should not
permit arbitrary command execution.

#### Rule execution pseudocode

``` python
def diagnose_and_repair(case, policy, adapters):
    evidence = adapters.diagnostics.collect(case)
    candidates = rule_engine.match(evidence)

    plan = rule_engine.build_plan(candidates, evidence, policy)
    plan.validate_allowlist()
    plan.validate_os_constraints()
    plan.validate_privileges()

    for action in plan.actions:
        if not policy.permits(action):
            record_skipped(action, reason="Blocked by policy")
            continue

        snapshot = adapters.state.capture(action.snapshot_keys)
        result = adapters.executor.execute_typed(action)
        record_action(action, snapshot, result)

        if not result.success:
            break

        verification = adapters.diagnostics.verify(action, case)
        if not verification.success:
            rollback_result = adapters.rollback.try_restore(snapshot, action)
            record_verification_and_rollback(verification, rollback_result)
            break

    return build_case_report(evidence, plan, action_log)
```

The implementation must include exception handling, timeouts,
cancellation, transaction boundaries, and safe behavior if the
application closes unexpectedly.

### 9. UI/UX specification

#### Main navigation

-   **Beranda**
-   **Diagnosa**
-   **Perbaikan**
-   **Printer**
-   **Folder**
-   **Riwayat**
-   **Pengaturan**

#### Dashboard

Show: - Computer name, Windows edition/build, role (client/host),
current network profile. - Large primary action: **Scan & Diagnosa**. -
Secondary actions: **Periksa Printer**, **Periksa Folder**, **Lihat
Riwayat**. - Recent case status and a clear notice if administrator
rights are needed.

#### Diagnosis page

-   Target type: printer / folder / both.
-   Target computer: hostname or IP.
-   Target path: `\\\\HOST\\Share` or `\\\\HOST\\PrinterShare`.
-   Exact error code/message (optional but encouraged).
-   Scan progress by category.
-   Findings grouped into **Masalah ditemukan**, **Peringatan**, and
    **Lulus**.
-   Explain each finding in simple Indonesian.

#### Repair plan page

For each proposed action show: - What is wrong. - What will change. -
Why the app thinks the action is relevant. - Scope: this user / this
computer / remote host. - Risk and required privilege. - Whether a
snapshot and rollback are available. - Whether restart or reboot may be
required.

Buttons: **Perbaiki yang Diizinkan**, **Pilih Perbaikan**, **Batalkan**.
High-impact actions must not be hidden in a one-click "fix all".

#### Result page

Show: - Fixed / partially fixed / not fixed. - Verification tests passed
and failed. - Changes made and rollback status. - Remaining manual
steps. - Export report (redacted by default).

#### UX rules

-   Use Indonesian by default; allow English in settings.
-   Never show a green "success" result just because a command returned
    exit code 0; run verification.
-   Keep advanced diagnostics available but not in the way of novice
    users.
-   Distinguish **not tested** from **failed**.
-   Offer copy buttons for UNC path, error code, and report ID.
-   Warn before actions that interrupt active printing or sharing.
-   Avoid color as the only way to convey status.

### 10. Administrator rights and security

#### Elevation

-   Detect current token elevation.
-   Run read-only checks at the lowest privilege that works.
-   For a privileged repair, explain the reason before invoking UAC.
-   Do not request credentials inside the app or persist administrator
    passwords.
-   If elevation is declined, continue read-only and list unavailable
    actions.

#### Command execution

-   Use fixed operation identifiers such as `start_service`,
    `get_share_acl`, or `enable_specific_firewall_rule`.
-   Do not expose a free-form PowerShell terminal as the repair engine.
-   Validate hostnames, share names, paths, service names, registry
    locations, and firewall rule identifiers.
-   Use subprocess argument arrays, timeouts, bounded output, and safe
    encoding.
-   Do not trust rules loaded from an unverified remote source.
-   Sign releases and update packages when distribution begins.

#### Remote host behavior

A portable client running as a standard user cannot legitimately modify
another computer merely because it can see that computer on the LAN.
Remote repairs require a supported and authorized mechanism, suitable
credentials/rights, and any required remote-management configuration.
The initial version should diagnose remote hosts and repair the local
machine; remote repair should be a separate, explicit feature with audit
logs.

#### Sensitive information

-   Redact usernames, domain names, IP addresses, file paths, printer
    names, and share names in exported reports by default, with a
    preview before export.
-   Never record passwords, authentication tokens, or full
    credential-store contents.
-   Restrict and rotate logs; offer a clear-history option.
-   Store only the minimum diagnostic evidence needed.

### 11. Snapshot and rollback strategy

Rollback is best-effort, not a universal undo button. Some operations
(for example, clearing a print queue or installing/removing a driver)
may not be fully reversible.

Before every mutation: 1. Record the exact target and current state. 2.
Store a timestamped snapshot in the case record. 3. Mark whether
restoration is supported and tested. 4. Apply one change at a time. 5.
Verify immediately. 6. If verification fails, attempt rollback only when
it is safe and the snapshot is complete. 7. Record rollback outcome and
any manual recovery requirement.

#### Snapshot candidates

-   Service status and startup type.
-   Exact firewall rules changed by the app, including enabled state and
    profile scope.
-   Specific sharing/discovery settings changed by the app.
-   Share and NTFS ACLs for the affected resource, including inheritance
    details where feasible.
-   Printer connection properties and queue state where supported.
-   App-owned configuration and policy changes.

Do not claim that a database snapshot restores Windows configuration.
Windows state restoration must use the relevant supported API/cmdlet and
a validated snapshot. Do not overwrite later administrator changes
during rollback: compare the current state with the value the app set,
and stop if another actor has changed it.

#### Rollback outcomes

-   `restored`
-   `partially_restored`
-   `not_supported`
-   `conflict_detected`
-   `failed`

### 12. Data model

Suggested SQLite tables: - `cases`: ID, start/end time, local OS
metadata, target type, target identifier (redacted where appropriate),
status. - `diagnostic_checks`: case ID, check ID, status, sanitized
evidence, duration. - `repair_plans`: case ID, rule ID/version, risk,
policy decision. - `actions`: case ID, operation, sanitized parameters,
start/end, exit/result code, success. - `snapshots`: case ID, action ID,
snapshot type, encrypted-or-restricted payload, restore support. -
`verification_results`: case ID, test ID, status, evidence. -
`audit_events`: actor context, elevation state, policy decision, action
outcome. - `app_settings`: local policy and preferences.

Keep rules separate from case history. Use schema migrations, database
integrity checks, and bounded retention.

### 13. Testing and acceptance criteria

#### Test layers

1.  **Unit tests:** rule matching, policy gates, parameter validation,
    redaction, rollback decisions.
2.  **Mocked Windows adapter tests:** simulate command outputs and
    exceptions without modifying a real system.
3.  **Windows VM tests:** supported client/server editions; workgroup
    and domain where available.
4.  **End-to-end LAN tests:** two or more disposable VMs, shared folder,
    shared printer test queue or virtual printer, firewall variations,
    and account/permission scenarios.
5.  **Packaging tests:** clean machine, no Python installed, standard
    user, UAC accepted/declined, non-ASCII paths, offline execution.
6.  **Security tests:** command injection, path validation, untrusted
    rule file, malformed database, interrupted repair, log redaction.

#### Acceptance criteria for a repair rule

-   Reproduces a known failure in a controlled test.
-   Correctly identifies the relevant evidence and avoids false matches
    in negative tests.
-   Has documented supported OS constraints.
-   Uses an allowlisted typed action.
-   Has a tested verification step.
-   Has rollback behavior documented and tested, or explicitly says
    rollback is unsupported.
-   Produces a readable report.
-   Does not lower security beyond the approved policy.
-   Re-running the scan is idempotent and does not create duplicate
    changes.

### 14. Realistic implementation roadmap

#### Phase 0 --- Feasibility and safety baseline

-   Confirm target Windows editions/builds.
-   Create threat model and policy matrix.
-   Define the typed Windows adapter interface.
-   Build a disposable VM test lab.
-   Establish the error reproduction format.

**Deliverable:** `vision.md`, `SECURITY.md`, support matrix, and test
plan.

#### Phase 1 --- Portable diagnostic MVP

-   PySide6 shell and Indonesian UI.
-   Read-only network, hostname/IP, service, SMB, share, printer, and
    spooler checks.
-   Exact error input and report export.
-   SQLite case history.
-   No automatic system changes yet.

**Exit criterion:** diagnostics run without elevation where possible and
clearly distinguish failed, passed, and unknown checks.

#### Phase 2 --- Rule engine and safe repairs

-   Versioned rule schema and validator.
-   Policy gates and repair-plan preview.
-   UAC/elevation flow.
-   First low-risk rules, such as starting a stopped relevant service
    when policy permits.
-   Snapshot and verification framework.

**Exit criterion:** every shipped mutation is typed, logged, verified,
and tested on a VM.

#### Phase 3 --- Folder sharing

-   UNC path and name-resolution diagnostics.
-   Share existence and permission inspection.
-   Share/NTFS permission explanation.
-   Narrow, approved permission repair with snapshots where technically
    supported.
-   Authentication guidance without password collection.

**Exit criterion:** common folder-sharing failure cases can be diagnosed
and a subset safely repaired.

#### Phase 4 --- Printer sharing

-   Spooler and queue checks.
-   Shared printer path checks.
-   Driver/Point and Print diagnostics.
-   Supported connection repair and trusted driver guidance.
-   Queue cleanup only for the explicitly selected target and according
    to policy.

**Exit criterion:** common printer-sharing cases are reproducible,
diagnosable, and verified on each claimed OS family.

#### Phase 5 --- Advanced Windows compatibility

-   SMB security/dialect diagnostics.
-   Firewall rule inspection and narrow remediation.
-   Event-log evidence and policy-conflict detection.
-   Additional error rules, tested one by one.
-   Compatibility matrix for Windows Server editions.

**Exit criterion:** no unsupported blanket fixes; unsupported or managed
configurations are clearly reported.

#### Phase 6 --- Release hardening

-   PyInstaller `--onedir` portable package.
-   Dependency pinning and software inventory.
-   Code signing if available.
-   Backup/restore testing, log redaction, and security review.
-   Versioned rule updates and changelog.
-   User documentation and offline mode.

**Exit criterion:** clean-VM acceptance tests pass and every advertised
feature is backed by evidence.

#### Phase 7 --- Optional central management

-   Central dashboard and authenticated agent.
-   Signed, narrow-scope remote jobs.
-   Per-device authorization, audit, timeouts, cancellation, and policy
    management.
-   No remote execution by discovery alone.

This phase is optional and should not block the portable local MVP.

### 15. Definition of done for version 1.0

Version 1.0 is ready when: - The portable package runs on each
explicitly supported Windows version. - It diagnoses both folder and
printer sharing. - It contains a documented, tested initial rule set. -
Every automatic change is authorized, logged, and verified. - Rollback
support and limitations are accurately reported. - Reports redact
sensitive information by default. - No generic repair disables the
firewall, enables SMB1, permits guest access, or broadly weakens printer
security. - The app can explain "not fixed" and produce actionable
evidence rather than falsely claiming success.

### 16. Development priorities

Build in this order:

1.  Read-only diagnostics and test harness.
2.  Evidence model and rule schema.
3.  Policy gate and repair preview.
4.  Snapshots, typed actions, and verification.
5.  Folder rules.
6.  Printer rules.
7.  Packaging, documentation, and compatibility validation.
8.  Optional remote administration.

Do not start with a large list of error-code fixes. Start with a small
set of reproducible failures and build a trustworthy rule engine around
them. Expand the catalogue only when each rule has evidence,
prerequisites, tests, and a safe recovery path.

---

## Bagian C — Keputusan implementasi sementara (v0.1)

Menjawab pertanyaan terbuka di A.13. Status: **sementara**, ditinjau di akhir Fase 1.

| # | Pertanyaan | Keputusan sementara | Alasan |
|---|---|---|---|
| 1 | Versi Windows minimum | Windows 10/11 (edisi yang masih didukung Microsoft). Windows Server: *belum diklaim* sampai lolos uji VM. | B.2 melarang asumsi kompatibilitas Server. |
| 2 | Bentuk aplikasi | Portabel (PyInstaller `--onedir`), tanpa installer. Installer bertanda tangan menyusul. | B.5. |
| 3 | Elevasi | Proses biasa tanpa elevasi; baca-saja berjalan tanpa admin. Elevasi UAC hanya untuk perbaikan (Fase 2). Tidak ada layanan terpisah. | B.4 *Privilege model*. |
| 4 | Penyimpanan | SQLite untuk riwayat kasus; JSON untuk aturan dan pengaturan; log berotasi. Data di `%LOCALAPPDATA%\NetworkSharingDoctor\`, atau `data/` di samping aplikasi bila ada berkas `portable.flag`. | B.6, B.12. |
| 5 | Penemuan otomatis | Fase 1: **hanya target manual**. Penemuan otomatis (subnet lokal saja, tidak mengganti target tanpa persetujuan) masuk Fase 3. | A.4.2; kurangi risiko salah target. |
| 6 | Tes cetak | **Tidak ada tes cetak di Fase 1.** Pemeriksaan "operasi akhir" dilaporkan *Belum diperiksa*, bukan *Gagal*. Opsi: halaman uji bawaan Windows atas persetujuan, Fase 3. | Tes cetak menghabiskan kertas dan mengubah antrean. |
| 7 | Retensi log & penyamaran | Retensi 180 hari / 500 kasus. Ekspor **disamarkan secara default** (host, IP, share, printer, nama pengguna, nama PC) dengan pratinjau sebelum simpan. | B.10. |
| 8 | Kode error prioritas | `0x0000011B`, `0x00000709`, `0x00000005`/`0x80070005`, `0x80070035`, `0x80070043`, `0x00000006`, `0x00000016`. Kode **hanya petunjuk**; penyebab ditetapkan dari bukti pemeriksaan. | A.5.4. |

### Batas Fase 1 (yang sengaja belum ada)

- Tidak ada perubahan sistem apa pun. Aksi pada aturan hanya **disarankan**; status siklus hidup yang dipakai: *terdeteksi → disarankan → disetujui → diterapkan → terverifikasi*. Fase 1 berhenti di *disarankan*.
- Wizard Server/Client penuh, pemilihan printer via Registry, dan ukuran kertas khusus di client (A.4.3, A.4.4) **belum dikerjakan**; dijadwalkan Fase 3–4 setelah mesin aturan dan snapshot terbukti.
- Antarmuka Indonesia saja; opsi bahasa Inggris menyusul.
