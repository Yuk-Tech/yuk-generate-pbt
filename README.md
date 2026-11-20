# Yuk Generate PBT! — QGIS Plugin

> **Bahasa Indonesia di bawah, English below.**
> Ikuti kami di Instagram: **[@yuktech](https://instagram.com/yuktech)** — kabar update, contoh hasil, dan tanya-jawab seputar plugin ini.

---

## Bahasa Indonesia

Plugin QGIS untuk generate **Peta Bidang Tanah (PBTF)** dari GeoPackage + template QPT. Port plugin dari aplikasi desktop "Yuk Generate PBT! by @Muhfadllah".

### Fitur

- Grouping hibrida (blok oleh pembagi + grid + greedy + min-10) — 115 persil jadi 10 lembar @1:500
- Label 3 baris (NAMA / NIB / L=...m2), satu warna teks, tanpa wrap
- Render PDF per lembar (varian dengan/tanpa citra ECW) + ZIP
- **Satu proyek QGIS (.qgs) berisi semua lembar** — bisa diedit di QGIS sebelum diekspor ke PDF
- **Isi frame 9 butir**: sistem koordinat, desa/kelurahan, kabupaten/kota, kecamatan, provinsi, petugas ukur + lisensi, pimpinan, penggunaan, pelaksana
- **Beta: butuh kode akses** — Hitung lembar dan Generate terkunci sampai kode akses beta dimasukkan (berlaku sampai 31 Des 2026)

### Instalasi

- **QGIS Plugin Manager** (setelah rilis di plugins.qgis.org): cari "Yuk Generate PBT!", instal.
- **Manual / dari ZIP**: unduh rilis ZIP, di QGIS buka `Plugins → Manage and Install Plugins → Install from ZIP`, pilih file ZIP-nya. Atau salin folder `yuk_generate_pbt/` ke folder plugin QGIS (`%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` di Windows).

### Cara pakai

1. Buka sidebar plugin (toolbar / menu Plugins).
2. Masukkan kode akses beta (bagian "Kode Akses Beta") lalu Aktifkan.
3. Pilih GeoPackage + layer + template QPT (+ ECW bila pakai citra).
4. Atur skala, warna, dan isi frame.
5. Generate — PDF + ZIP + file `.qgs` tersimpan di folder output.

### Kode akses beta (gratis, untuk feedback)

Sepuluh kode di bawah ini masing-masing berlaku untuk **5 generate**, sampai **31 Desember 2026**. Silakan pakai salah satunya — kami butuh masukanmu! Kalau ada bug, saran, atau hasil generate yang mau dipamerkan, hubungi kami lewat Instagram **[@yuktech](https://instagram.com/yuktech)**.

```
YUK-4KEUCW-HP2W2S
YUK-4V7KHZ-DFM87T
YUK-6WCQXX-APQCMA
YUK-884E2X-WKTV3U
YUK-CGCWRX-U7YDKE
YUK-GBK8JX-96TZFG
YUK-RYTJAZ-9D2C4M
YUK-UT8T3T-GVD6MX
YUK-XW7VWM-T9KEF9
YUK-YS3YNM-W3YPC2
```

### Contoh template QPT

Contoh template PBTF siap pakai (sudah berisi nama demo "ig:@yuktech" dan "PT Kebakaran Jenggot", bukan nama asli) bisa diunduh di sini:

**[Download contoh template QPT (Google Drive)](https://drive.google.com/drive/folders/17w9zbwWBJ7eAM6O0-dlcQSDCBQyDR0cc?usp=drive_link)**

### Saran layer untuk file GPKG

Satu layer berisi semua bidang, geometri **MULTIPOLYGON**, sistem koordinat **TM-3 zona wilayahmu** (contoh: EPSG:23834 untuk TM-3 Zona 48.2). Field yang dibaca plugin:

| Field | Isi | Contoh |
|---|---|---|
| `080201` | NIB (Nomor Identifikasi Bidang) | `00841` |
| `NAMA` | Nama pemilik / pemegang hak | `ELIH SOLIHAH` |
| `M2` | Luas bidang dalam m² (angka) | `86` |
| `A` | NIK pemilik | `320312...` |
| `KET` | `JALAN` / `IRIGASI` untuk jalan & irigasi (digambar warna khusus, bukan persil); kosong untuk persil | `JALAN` |
| `LUAS` | Luas terformat (opsional, plugin memakai `M2`) | `L=177M2` |
| `080203` | Nomor Hak (penanda SHM, untuk PBTK) | `M.00291` |

Contoh file GPKG yang sudah sesuai struktur ini:

**[Download contoh GPKG (Google Drive)](https://drive.google.com/file/d/11Xs6WbK8qmuHC11um0RwWq6z56CALSjf/view?usp=drive_link)**

### Struktur repo

```
yuk_generate_pbt/   plugin (metadata.txt, engine.py, panel.py, ...)
```

File `test_*.py` adalah uji headless (QGIS 3.22 di sandbox E2B).

### Lisensi

GPL-3.0 — lihat `LICENSE`.

---

## English

QGIS plugin to generate **Peta Bidang Tanah (PBTF)** land parcel maps from a GeoPackage + QPT template. QGIS port of the desktop app "Yuk Generate PBT! by @Muhfadllah".

Follow us on Instagram: **[@yuktech](https://instagram.com/yuktech)** — updates, sample outputs, and Q&A about this plugin.

### Features

- Hybrid grouping (divider blocks + grid + greedy + min-10) — 115 parcels become 10 sheets @1:500
- 3-line labels (NAMA / NIB / L=...m2), single text color, no wrap
- PDF render per sheet (with/without ECW imagery variants) + ZIP
- **One QGIS project (.qgs) with all sheets** — editable in QGIS before exporting to PDF
- **9 frame fields**: coordinate system, village/subdistrict, regency/city, district, province, surveyor + license, leader, usage, executor
- **Beta: requires an access code** — Count sheets and Generate are locked until a beta access code is entered (valid until 31 Dec 2026)

### Installation

- **QGIS Plugin Manager** (after release on plugins.qgis.org): search "Yuk Generate PBT!" and install.
- **Manual / from ZIP**: download the release ZIP, in QGIS open `Plugins → Manage and Install Plugins → Install from ZIP`, and select the ZIP file. Or copy the `yuk_generate_pbt/` folder into the QGIS plugins folder (`%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` on Windows).

### Usage

1. Open the plugin sidebar (toolbar / Plugins menu).
2. Enter your beta access code ("Beta Access Code" section) and click Activate.
3. Pick a GeoPackage + layer + QPT template (+ ECW for imagery).
4. Set the scale, colors, and frame fields.
5. Generate — the PDFs + ZIP + `.qgs` file are saved to the output folder.

### Beta access codes (free, for feedback)

Each of the ten codes below is good for **5 generates**, until **31 December 2026**. Feel free to use one — we need your feedback! If you find a bug, have a suggestion, or want to show off your generated sheets, reach us on Instagram **[@yuktech](https://instagram.com/yuktech)**.

```
YUK-4KEUCW-HP2W2S
YUK-4V7KHZ-DFM87T
YUK-6WCQXX-APQCMA
YUK-884E2X-WKTV3U
YUK-CGCWRX-U7YDKE
YUK-GBK8JX-96TZFG
YUK-RYTJAZ-9D2C4M
YUK-UT8T3T-GVD6MX
YUK-XW7VWM-T9KEF9
YUK-YS3YNM-W3YPC2
```

### Sample QPT template

A ready-to-use sample PBTF template (already filled with the demo names "ig:@yuktech" and "PT Kebakaran Jenggot", not real names) is available here:

**[Download the sample QPT template (Google Drive)](https://drive.google.com/drive/folders/17w9zbwWBJ7eAM6O0-dlcQSDCBQyDR0cc?usp=drive_link)**

### Suggested layer for your GPKG file

One layer holding all parcels, **MULTIPOLYGON** geometry, in the **TM-3 zone of your area** (e.g. EPSG:23834 for TM-3 Zone 48.2). Fields the plugin reads:

| Field | Content | Example |
|---|---|---|
| `080201` | NIB (parcel identification number) | `00841` |
| `NAMA` | Owner / rights-holder name | `ELIH SOLIHAH` |
| `M2` | Parcel area in m² (number) | `86` |
| `A` | Owner's NIK (national ID number) | `320312...` |
| `KET` | `JALAN` / `IRIGASI` for roads & irrigation (drawn in special colors, not counted as parcels); empty for parcels | `JALAN` |
| `LUAS` | Pre-formatted area string (optional, the plugin uses `M2`) | `L=177M2` |
| `080203` | Land-right number (SHM marker, for PBTK) | `M.00291` |

A sample GPKG file following this structure:

**[Download the sample GPKG (Google Drive)](https://drive.google.com/file/d/11Xs6WbK8qmuHC11um0RwWq6z56CALSjf/view?usp=drive_link)**

### Repository structure

```
yuk_generate_pbt/   plugin (metadata.txt, engine.py, panel.py, ...)
```

The `test_*.py` files are headless tests (QGIS 3.22 in an E2B sandbox).

### License

GPL-3.0 — see `LICENSE`.
