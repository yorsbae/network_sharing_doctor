# Arah desain

Alat bantu administrator dan staf kantor yang sedang menghadapi masalah cetak atau folder bersama. Tenang, jelas, dan tidak ramai.

## Dial
ENERGY 1, RHYTHM 1, MOTION 1. Aplikasi kerja yang dipakai saat sedang terburu-buru; keseragaman memang disengaja.

## Warna (alasan satu baris per pilihan)
- Hijau-biru tua (`primary`) sebagai satu-satunya aksen: tombol utama dan fokus. Dekat dengan nuansa "dokter" tanpa memakai biru-ungu bawaan.
- Latar krem hangat (terang) dan arang kehijauan (gelap): mengurangi silau saat dibaca lama.
- Merah, kuning tua, hijau hanya untuk status Gagal, Peringatan, Lulus. Selalu disertai label teks seperti `[GAGAL]`.
- Semua pasangan teks diuji otomatis (WCAG AA) di `tests/ui/test_theme_and_pages.py`.

## Bentuk dan tipografi
- Radius 6 px untuk kontrol, 10 px untuk panel. Tidak ada bayangan, glow, gradien, atau kaca buram.
- Font sistem Windows (Segoe UI). Pilihan ini membuat teks Indonesia terbaca baik dan tanpa unduhan font.
- Tidak ada ikon dekoratif. Menu hanya memuat halaman yang benar-benar ada.

## Teks
Bahasa Indonesia, kalimat pendek, tombol berupa kata kerja spesifik (Scan & Diagnosa, Ekspor laporan, Hapus riwayat). Tanpa tanda pisah panjang, tanpa angka atau klaim yang tidak berasal dari data nyata.
