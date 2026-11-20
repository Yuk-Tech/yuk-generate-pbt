# Yuk Generate PBT! — Plugin QGIS

Plugin QGIS untuk generate **Peta Bidang Tanah (PBTF)** dari GeoPackage + template QPT. Port plugin dari aplikasi desktop "Yuk Generate PBT! by @Muhfadllah".

## Fitur

- Grouping hibrida (blok oleh pembagi + grid + greedy + min-10) — 115 persil jadi 10 lembar @1:500
- Label 3 baris (NAMA / NIB / L=...m2), satu warna teks, tanpa wrap
- Render PDF per lembar (varian dengan/tanpa citra ECW) + ZIP
- **Satu proyek QGIS (.qgs) berisi semua lembar** — bisa diedit di QGIS sebelum diekspor ke PDF
- **Isi frame 9 butir**: sistem koordinat, desa/kelurahan, kabupaten/kota, kecamatan, provinsi, petugas ukur + lisensi, pimpinan, penggunaan, pelaksana
- **Beta: butuh kode akses** — Hitung lembar dan Generate terkunci sampai kode akses beta dimasukkan (berlaku sampai 31 Des 2026)

## Instalasi

- **QGIS Plugin Manager** (setelah rilis di plugins.qgis.org): cari "Yuk Generate PBT!", instal.
- **Manual / dari ZIP**: unduh rilis ZIP, di QGIS buka `Plugins → Manage and Install Plugins → Install from ZIP`, pilih file ZIP-nya. Atau salin folder `yuk_generate_pbt/` ke folder plugin QGIS (`%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` di Windows).

## Pakai

1. Buka sidebar plugin (toolbar / menu Plugins).
2. Masukkan kode akses beta (bagian "Kode Akses Beta") lalu Aktifkan.
3. Pilih GeoPackage + layer + template QPT (+ ECW bila pakai citra).
4. Atur skala, warna, dan isi frame.
5. Generate — PDF + ZIP + file `.qgs` tersimpan di folder output.

## Struktur repo

```
yuk_generate_pbt/   plugin (metadata.txt, engine.py, panel.py, ...)
```

File `test_*.py` adalah uji headless (QGIS 3.22 di sandbox E2B).

## Lisensi

GPL-3.0 — lihat `LICENSE`.
