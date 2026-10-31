# Arah desain

Alat bantu staf kantor dan administrator saat printer atau cetak bermasalah. Merek produk: Network Sharing Doctor. Mockup (sidebar navy, aksen biru, kartu status, tabel dengan chip) adalah acuan tetap untuk bentuk dan susunan. Bagian yang tidak diatur mockup mengikuti pagar anti-slop di bawah.

## Struktur
Dashboard, Server, Client, Scan printer, Kode error, Daftar printer, Antrean cetak, Kertas, Log, Pengaturan. Sidebar menampilkan status scan terakhir yang nyata, bukan label "Healthy" tetap.
Bahasa antarmuka: Indonesia. Nama menu mengikuti mockup.

## Warna
Navy gelap sebagai bawaan, terang tersedia. Biru (`primary`) hanya untuk tombol utama, menu aktif, dan fokus. Hijau, kuning, merah hanya untuk status dan selalu disertai teks. Semua pasangan teks diuji (WCAG AA) termasuk chip bernada. `hairline` hanya untuk tepi kartu dekoratif; `border` (3:1) untuk kontrol.

## Bentuk
Radius berjenjang: 8 kontrol, 10 ubin dan baris aksi, 12 panel, pil penuh untuk chip. Tanpa bayangan, glow, gradien, atau kaca buram. Tanpa animasi.

## Teks
Sentence case, kata kerja spesifik, nama aksi sama di seluruh alur (Scan sekarang, Mulai scan, Muat ulang). Tanpa huruf kapital semua, tanpa panah di teks, tanpa tanda pisah panjang. Keadaan kosong dan galat menyebut apa yang terjadi dan langkah berikutnya.

## Data
Tidak ada angka atau nama contoh. Kartu dan tabel hanya menampilkan data nyata; bila tidak dapat dibaca (mis. bukan Windows) tertulis "Belum diperiksa" beserta alasannya. Kolom yang nilainya sama di setiap baris tidak ditampilkan.

## Pagar anti-slop (diuji otomatis di `tests/ui`)
Tidak ada gradien, bayangan, `text-transform`, `letter-spacing`, panah, atau tanda pisah panjang di kode UI; kontras chip dan token diuji di kedua tema. Cincin fokus menu hanya muncul saat navigasi keyboard.

## Server dan client
Peran dipilih di Dashboard ("Mulai di sini"), lalu dikerjakan di halamannya sendiri; Scan printer menjadi alat lanjutan.
Setiap halaman berurutan: Server = kesiapan, alamat untuk client, petunjuk siap kirim; Client = pilih server, pilih printer atau folder, periksa koneksi.
Satu tombol utama per tahap. Tombol yang belum bisa dipakai nonaktif dan alasannya tertulis di dekatnya. Halaman Server menyatakan terang bahwa tidak ada program server yang perlu dijalankan.
Pencarian server hanya jalan saat diklik, dan keterangan batasnya ditampilkan di tempat tombolnya. Halaman panjang (Dashboard, Server, Client) bisa digulir dan diuji tanpa overflow horizontal pada 980x600.

## Perbaikan otomatis
Pratinjau dulu, tidak ada perubahan tanpa klik Terapkan. Prasyarat (pengaturan aktif, hak administrator) ditampilkan sebagai status dengan tombol untuk memenuhinya. Yang tidak otomatis selalu disertai alasannya. Hasil selalu diverifikasi ulang dan scan diulang.

## Yang sengaja belum ada dari mockup
Jeda/batalkan/hapus antrean (ini mengubah sistem; Fase 1 baca-saja), pilihan jenis pemeriksaan (mesin menjalankan semua lapisan), tab Settings pada detail printer, minimize ke tray, dan scan otomatis saat buka.
