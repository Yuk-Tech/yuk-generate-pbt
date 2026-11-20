# Yuk Generate PBT! — By @muhfadllah — Plugin QGIS (PoC)

> **Bahasa Indonesia di bawah, English below.**
> Ikuti kami di Instagram: **[@yuktech](https://instagram.com/yuktech)** — kabar update, contoh hasil, dan tanya-jawab seputar plugin ini.

---

## Bahasa Indonesia

**Di luar proyek PTSL** — uji coba apakah aplikasi desktop "Yuk Generate PBT!"
bisa hidup sebagai plugin QGIS tanpa menghilangkan satu pun fitur. Jawabannya:
bisa; ini buktinya.

### Isi paket

| File | Isi |
|---|---|
| `metadata.txt` | Metadata plugin (nama "Yuk Generate PBT! — By @muhfadllah", versi 0.5.6, QGIS ≥ 3.22, author @Muhfadllah) |
| `__init__.py` | Titik masuk — `classFactory()` |
| `yuk_generate_pbt.py` | Kelas plugin: tombol toolbar + menu, buka/tutup sidebar (QDockWidget) |
| `panel.py` | Panel sidebar PyQt: kode akses beta, pemilih GPKG/QPT/ECW, skala, warna, varian, form pengesahan, isi frame, format, riwayat, tombol Tutup |
| `license.py` | Gerbang kode akses beta: hash SHA-256 kode, masa berlaku sampai 31 Des 2026, status aktif di QSettings |
| `engine.py` | Mesin PyQGIS: grouping hibrida + styling + render + ZIP (tanpa dependensi Qt) |
| `test_headless.py` | Uji render headless di sandbox (tanpa GUI) |
| `test_dock.py` | Uji sidebar headless di sandbox (toggle, Tutup, X, screenshot) |
| `test_enums.py` | Uji resolusi enum label headless di sandbox (QGIS 4 vs QGIS 3) |
| `test_citra.py` | Uji render DENGAN citra headless di sandbox (urutan layer vektor/raster) |
| `test_subset_fallback.py` | Uji fallback subset headless di sandbox (subset 0 fitur / SQL invalid) |
| `test_frame_qgs.py` | Uji isi frame + proyek .qgs headless di sandbox (nilai kustom, muat ulang .qgs) |
| `test_access.py` | Uji gerbang kode akses beta headless di sandbox (validasi kode, kunci/buka panel, tersimpan di QSettings) |
| `icon.png` | Ikon toolbar (robot) |
| `yuk-logo.png` | Logo di panel |

### Cara pasang (QGIS 4.2.2, Windows)

1. Zip **folder** `yuk-generate-pbt/` seutuhnya menjadi
   `yuk-generate-pbt.zip` — di dalam zip harus ada **satu folder root**
   (`yuk_generate_pbt/`, garis bawah) yang berisi `metadata.txt`,
   `__init__.py`, dan file lainnya. **Jangan** zip isi folder tanpa
   foldernya: QGIS menolak zip tanpa folder root ("No root folder was
   found inside"). Nama folder pakai garis bawah karena QGIS mengimpor
   plugin sebagai paket Python.
2. QGIS → Plugins → Manage and Install Plugins → Install from ZIP →
   pilih zip → Install Plugin.
3. Atau manual: ekstrak ke
   `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\yuk_generate_pbt\`
   lalu aktifkan di Plugin Manager.
4. Tombol robot muncul di toolbar + menu "Yuk Generate PBT! — By @muhfadllah".
   Klik tombolnya → sidebar terbuka di sisi kanan QGIS (klik lagi →
   tertutup). Menutup sidebar: tombol **Tutup** di bawah panel, tombol X
   di judul sidebar, atau klik lagi tombol toolbarnya.

### Cara pakai

1. Masukkan **kode akses beta** di bagian "Kode Akses Beta" lalu Aktifkan — tombol Hitung lembar dan Generate terkunci sampai kode valid dimasukkan.
2. Pilih **GeoPackage** (`PBT_2091.gpkg`) → layer terisi otomatis.
3. Pilih **Template QPT** (`PBTF_WARDOY.qpt`).
3. (Opsional) Pilih **Citra ECW** → centang "Dengan citra ECW".
4. Atur skala (default Auto), warna persil (default Hijau), warna teks
   (default Abu gelap), isi Tanggal / No PBT / No Blok, logo & TTD bila ada.
5. Pilih folder output + format (PDF / PDF+ZIP).
6. **Hitung lembar** dulu untuk melihat komposisi lembar, lalu **Generate**.
7. PDF per lembar: `PBTF_2091_L01_1-500_TANPA_CITRA.pdf` dst.
   ZIP (`PBTF_2091.zip`) hanya berisi PDF — tanpa file debug/log.
8. Layout hasil juga terdaftar di Layout Manager QGIS ("PBTF 2091")
   untuk dibuka/diperiksa manual.

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



## English

**Outside the PTSL project** — a trial of whether the desktop app "Yuk Generate PBT!" can live as a QGIS plugin without losing a single feature. Answer: yes; this is the proof.

Follow us on Instagram: **[@yuktech](https://instagram.com/yuktech)** — updates, sample outputs, and Q&A about this plugin.

### Package contents

| File | Contents |
|---|---|
| `metadata.txt` | Plugin metadata (name "Yuk Generate PBT! — By @muhfadllah", version 0.5.6, QGIS ≥ 3.22, author @Muhfadllah) |
| `__init__.py` | Entry point — `classFactory()` |
| `yuk_generate_pbt.py` | Plugin class: toolbar button + menu, open/close sidebar (QDockWidget) |
| `panel.py` | PyQt sidebar panel: beta access code, GPKG/QPT/ECW pickers, scale, colors, variant, approval form, frame fields, format, history, Close button |
| `license.py` | Beta access-code gate: SHA-256 code hash, valid until 31 Dec 2026, active status stored in QSettings |
| `engine.py` | PyQGIS engine: hybrid grouping + styling + render + ZIP (no Qt dependency) |
| `test_headless.py` | Headless render test in the sandbox (no GUI) |
| `test_dock.py` | Headless sidebar test in the sandbox (toggle, Close, X, screenshot) |
| `test_enums.py` | Headless label-enum resolution test in the sandbox (QGIS 4 vs QGIS 3) |
| `test_citra.py` | Headless render WITH imagery test in the sandbox (vector/raster layer order) |
| `test_subset_fallback.py` | Headless subset-fallback test in the sandbox (0-feature subset / invalid SQL) |
| `test_frame_qgs.py` | Headless frame-fields + .qgs project test in the sandbox (custom values, .qgs reload) |
| `test_access.py` | Headless beta access-code gate test in the sandbox (code validation, panel lock/unlock, QSettings persistence) |
| `icon.png` | Toolbar icon (robot) |
| `yuk-logo.png` | Panel logo |

### Installation (QGIS 4.2.2, Windows)

1. Zip the **whole** `yuk-generate-pbt/` folder into `yuk-generate-pbt.zip` — inside the zip there must be **one root folder** (`yuk_generate_pbt/`, underscores) containing `metadata.txt`, `__init__.py`, and the other files. **Do not** zip the folder's contents without the folder: QGIS rejects zips with no root folder ("No root folder was found inside"). The folder name uses underscores because QGIS imports the plugin as a Python package.
2. QGIS → Plugins → Manage and Install Plugins → Install from ZIP → pick the zip → Install Plugin.
3. Or manually: extract to `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\yuk_generate_pbt\` and enable it in the Plugin Manager.
4. The robot button appears in the toolbar + the "Yuk Generate PBT! — By @muhfadllah" menu. Click it → the sidebar opens on the right side of QGIS (click again → closes). Close the sidebar with the **Close** button at the bottom of the panel, the X on the sidebar title, or by clicking the toolbar button again.

### Usage

1. Enter your **beta access code** in the "Beta Access Code" section and click Activate — the Count sheets and Generate buttons stay locked until a valid code is entered.
2. Pick a **GeoPackage** (`PBT_2091.gpkg`) → the layer fills in automatically.
3. Pick a **QPT template** (`PBTF_WARDOY.qpt`).
4. (Optional) Pick an **ECW image** → check "With ECW imagery".
5. Set the scale (default Auto), parcel color (default Green), text color (default Dark gray), fill in Date / PBT No / Block No, logo & signatures if any.
6. Pick the output folder + format (PDF / PDF+ZIP).
7. **Count sheets** first to see the sheet composition, then **Generate**.
8. One PDF per sheet: `PBTF_2091_L01_1-500_TANPA_CITRA.pdf`, etc. The ZIP (`PBTF_2091.zip`) contains only PDFs — no debug/log files.
9. The resulting layouts are also registered in the QGIS Layout Manager ("PBTF 2091") for manual opening/inspection.

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

