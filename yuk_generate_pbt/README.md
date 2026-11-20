# Yuk Generate PBT! — By @muhfadllah — Plugin QGIS (PoC)

**Di luar proyek PTSL** — uji coba apakah aplikasi desktop "Yuk Generate PBT!"
bisa hidup sebagai plugin QGIS tanpa menghilangkan satu pun fitur. Jawabannya:
bisa; ini buktinya.

## Isi paket

| File | Isi |
|---|---|
| `metadata.txt` | Metadata plugin (nama "Yuk Generate PBT! — By @muhfadllah", versi 0.2.0, QGIS ≥ 3.22, author @Muhfadllah) |
| `__init__.py` | Titik masuk — `classFactory()` |
| `yuk_generate_pbt.py` | Kelas plugin: tombol toolbar + menu, buka/tutup sidebar (QDockWidget) |
| `panel.py` | Panel sidebar PyQt: pemilih GPKG/QPT/ECW, skala, warna, varian, form pengesahan, format, riwayat, tombol Tutup |
| `engine.py` | Mesin PyQGIS: grouping hibrida + styling + render + ZIP (tanpa dependensi Qt) |
| `test_headless.py` | Uji render headless di sandbox (tanpa GUI) |
| `test_dock.py` | Uji sidebar headless di sandbox (toggle, Tutup, X, screenshot) |
| `test_enums.py` | Uji resolusi enum label headless di sandbox (QGIS 4 vs QGIS 3) |
| `test_citra.py` | Uji render DENGAN citra headless di sandbox (urutan layer vektor/raster) |
| `test_subset_fallback.py` | Uji fallback subset headless di sandbox (subset 0 fitur / SQL invalid) |
| `test_frame_qgs.py` | Uji isi frame + proyek .qgs headless di sandbox (nilai kustom, muat ulang .qgs) |
| `icon.png` | Ikon toolbar (robot) |
| `yuk-logo.png` | Logo di panel |

## Cara pasang (QGIS 4.2.2, Windows)

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

## Cara pakai

1. Pilih **GeoPackage** (`PBT_2091.gpkg`) → layer terisi otomatis.
2. Pilih **Template QPT** (`PBTF_WARDOY.qpt`).
3. (Opsional) Pilih **Citra ECW** → centang "Dengan citra ECW".
4. Atur skala (default Auto), warna persil (default Hijau), warna teks
   (default Abu gelap), isi Tanggal / No PBT / No Blok, logo & TTD bila ada.
5. Pilih folder output + format (PDF / PDF+ZIP).
6. **Hitung lembar** dulu untuk melihat komposisi lembar, lalu **Generate**.
7. PDF per lembar: `PBTF_2091_L01_1-500_TANPA_CITRA.pdf` dst.
   ZIP (`PBTF_2091.zip`) hanya berisi PDF — tanpa file debug/log.
8. Layout hasil juga terdaftar di Layout Manager QGIS ("PBTF 2091")
   untuk dibuka/diperiksa manual.

## Yang di-port 1:1 dari aplikasi desktop (v17.15)

- Grouping hibrida v17.7: blok oleh pembagi (sel 2 m, buffer 2 m,
  4-connectivity) + grid + greedy + min-10 opsi A (v17.8). Maks 24/lembar.
- Renderer aturan KET: jalan/gang merah #FF3F00, air biru #003FFF,
  persil warna pilihan; trim jalan/air buffer 5 m (GeometryGenerator).
- Labeling 3 baris (NAMA / NIB / L=…m2), satu warna teks, placement
  OverPoint (v17.13), font adaptif tanpa wrap (v17.11), obstacleType=1 (v17.9).
- Subset per lembar: 1 persil hanya di 1 lembar; pembagi yang menyentuh
  extent ikut sebagai konteks.
- Variabel layout: tgl/tglF/pbt/b/lembar; gambar LOGO / TTD PANCA / TTD RUDY;
  label skala ditulis literal (seperti v17).
- Riwayat sederhana (maks 20, QSettings), "klik 2x = pakai folder ini".

## Yang berubah (sifat plugin, bukan pengurangan fitur)

- **Tidak bisa jalan standalone** — QGIS harus dibuka dulu. Sebagai gantinya:
  tidak ada lagi hack layer-id (v17.1), tidak ada `qgis_process`, tidak ada
  proyek `.qgs` sementara, tidak ada file debug/log.
- Riwayat pindah dari localStorage ke QSettings.
- Tidak ada installer NSIS/MSI — distribusi lewat zip plugin.
- Render berjalan di thread utama (log tetap jalan via processEvents).
  Port penuh sebaiknya pindah ke QgsTask.

## Yang sudah terverifikasi (sandbox QGIS 3.22.16, 2026-11-20)

- `py_compile` bersih untuk semua file Python.
- Logika grouping murni (tanpa QGIS): tabel font, palet warna, ekspresi
  trim, ekspresi label, nama file, dan grouping sintetis (blok + min-10
  merge) semuanya cocok dengan engine Rust.
- **Uji headless LULUS** (`test_headless.py`, "SEMUA UJI HEADLESS LULUS"):
  GPKG asli PBT_2091 (124 fitur) + template WARDOY asli → grouping
  10 lembar **[2, 3, 3, 4, 7, 11, 17, 21, 23, 24] persis sama dengan
  komposisi Rust v17.8**; 10 PDF TANPA_CITRA + ZIP yang hanya berisi
  ke-10 PDF; label terisi literal (Nomor 2091, Blok 004, Cianjur
  20 November 2026, Lembar 1–10, Skala 1:500); persil putih outline
  hijau, label 3 baris di tengah persil. Pratinjau L01 diperiksa dengan
  mata (lihat `out/L01-preview.png` di folder kerja).
- **Belum:** uji GUI interaktif di QGIS 4.2.2 milik Derana (satu lembar
  dulu) — dialog PyQt6 belum pernah diklik di QGIS mana pun. Yang sudah
  terbukti: dialog **terbangun & ter-render headless** di sandbox
  (PyQt5, QGIS 3.22, offscreen — `shot_dialog.py`): semua kontrol tampil,
  watermark "By @muhfadllah" terlihat di judul jendela, header, dan
  footer (lihat `out/dialog-preview.png` di folder kerja). Yang belum:
  klik tombol, file picker, dan render batch dari dalam dialog di 4.2.2.
- **v0.1.3 (2026-11-20):** perbaikan PyQt6 — `Qt.AlignCenter` (bentuk
  PyQt5) tidak ada di PyQt6/QGIS 4 dan membuat dialog crash saat dibuka
  (`AttributeError`, dilaporkan dari QGIS 4.2.2). Sekarang memakai
  konstanta `ALIGN_CENTER` yang memilih `Qt.AlignmentFlag.AlignCenter`
  (PyQt6) atau `Qt.AlignCenter` (PyQt5). Satu-satunya pemakaian enum
  `Qt.*` flat di plugin — sudah dicek tidak ada yang lain.
- **v0.1.5 (2026-11-20):** perbaikan bug minimize, tahap 2 — v0.1.4
  (`showNormal()`) dilaporkan masih gagal. Dua kemungkinan: QGIS masih
  menjalankan versi lama (update dari ZIP kadang tidak ter-reload tanpa
  restart), atau dialog anak jendela utama memang tidak bisa di-restore
  andal di Windows. Maka: (1) dialog dibuat tanpa parent — jendela
  mandiri dengan tombol taskbar sendiri, minimize/restore seperti
  aplikasi biasa; (2) footer menampilkan nomor versi (dibaca dari
  `metadata.txt`) supaya ketahuan versi berapa yang sedang jalan.
  **Setelah install v0.1.5, tutup QGIS dulu lalu buka lagi**, dan cek
  footer dialog tertulis v0.1.5.
- **v0.2.0 (2026-11-20):** UI diganti sidebar (QDockWidget) atas
  permintaan Derana — dialog melayang dihapus. Panel (`panel.py`) berisi
  semua kontrol yang sama + tombol **Tutup** (menyembunyikan sidebar);
  sidebar juga bisa ditutup lewat X di judulnya atau toggle tombol
  toolbar (tombol tampil tertekan saat sidebar terbuka). Form memakai
  `WrapAllRows` (label di atas field) + QScrollArea agar muat di panel
  sempit. Diuji headless (`test_dock.py`): dock dibuat + tampil,
  toggle, Tutup, X, sinkron tombol toolbar, stempel v0.2.0 di footer,
  unload membersihkan dock (screenshot `out/dock-preview.png`).
- **v0.2.1 (2026-11-20):** perbaikan crash di QGIS 4.2.2 — render gagal
  "a member of enum 'LabelPlacement' is expected not
  'LabelPredefinedPointPosition'". Penyebab: QGIS 4 memindahkan enum
  label dari `QgsPalLayerSettings` ke namespace `Qgis` (`Qgis::Label-
  Placement`, `LabelMultiLineAlignment`, `LabelQuadrantPosition`, ...),
  dan akses datar PyQt6 (`QgsPalLayerSettings.OverPoint`) mengembalikan
  anggota enum yang salah. Perbaikan (`engine.py`, helper baru
  `_qgis_enum`): jalur `Qgis.*` dicoba dulu, baru jalur
  `QgsPalLayerSettings.*` (QGIS 3), baru fallback angka. `quadrantOffset`
  dan `obstacleType` tidak ada di `QgsPalLayerSettings` QGIS 4 (pindah ke
  `pointSettings()` / `obstacleSettings()`) — guard `hasattr` sudah
  menanganinya; nilai `obstacleType` hanya dicari bila atributnya ada.
  Diuji headless (`test_enums.py`): jalur QGIS 4 gagal diam-diam di
  3.22, nilai QGIS 3 benar (placement 1, multilineAlign 1, quad 4,
  size_key 0); render penuh tetap lulus (10 lembar). Catatan jujur:
  cabang QGIS 4 diverifikasi terhadap dok API QGIS 4.0/4.2 + sumber
  QGIS, bukan dengan menjalankan di 4.2 — uji satu lembar di 4.2.2
  tetap di tangan Derana. Diketahui juga: `QuadrantCenter` tidak punya
  anggota Python di 3.22 (enum lompat 3 → 5) — nilai tengah = 4 (int).
- **v0.2.2 (2026-11-20):** perbaikan lembar kosong di QGIS 4.2.2 — PDF
  CITRA maupun TANPA_CITRA tidak menampilkan satu pun persil (tanpa
  garis maupun label), padahal citra, grid, dan panel ter-render benar.
  Bukan urutan layer: uji `test_citra.py` membuktikan urutan
  `[vektor, raster]` sudah benar di 3.22 (persil di atas citra; urutan
  terbalik justru menyembunyikan garis persil). Penyebab paling kuat:
  filter per-lembar (`setSubsetString`) gagal diam-diam di QGIS 4
  (0 fitur, tanpa error) — bila SQL-nya invalid (kolom pk salah ->
  nilai string tak dikutip), GDAL gagal prepare dan layer kosong.
  Perbaikan (`engine.py`, helper baru `_layer_has_features`): setelah
  subset dipasang, engine memeriksa ada tidaknya fitur (featureCount
  lalu getFeatures, karena featureCount bisa -1 bila hitung gagal);
  bila kosong padahal grup berisi fitur, coba kolom `fid`, lalu lepas
  subset (semua fitur, dibatasi extent lembar) supaya lembar tetap
  terisi, sambil mencatat PERINGATAN di log panel. Diuji headless
  (`test_subset_fallback.py`): jalur normal tanpa PERINGATAN; subset
  valid-0-cocok dan subset SQL-invalid sama-sama memicu fallback dan
  lembar tetap berisi persil; render penuh tetap lulus (10 lembar).
  Catatan: pada fallback, persil lembar tetangga yang masuk extent
  bisa ikut tampil — itu harga darurat supaya lembar tidak kosong;
  log PERINGATAN menandai kapan itu terjadi. Akar masalah subset di
  QGIS 4.2.2 sendiri belum teridentifikasi pasti (tidak ada QGIS 4 di
  sini) — bila log Derana menampilkan PERINGATAN subset, kirim lognya.
- **v0.2.3 (2026-11-20):** akar masalah lembar kosong akhirnya ketemu
  dari temuan Derana: persil baru muncul bila GPKG dan ECW ikut dibuka di
  kanvas QGIS (Layers panel), bukan hanya dipilih di panel plugin. Sebab:
  peta di template `PBTF_WARDOY.qpt` menyimpan `keepLayerSet="false"`,
  sehingga di QGIS 4.2.2 peta mengikuti layer tree kanvas dan membuang
  daftar layer yang dipasang plugin lewat `setLayers()` (layer plugin
  ditambah dengan `addMapLayer(..., False)`). Itu menjelaskan semuanya:
  citra sempat tampil karena ECW sudah dibuka di kanvas, GPKG belum.
  Perbaikan (`engine.py`): setelah layout dimuat, engine memanggil
  `map_item.setKeepLayerSet(True)` sehingga peta terkunci ke daftar layer
  plugin — plugin berdiri sendiri, tidak perlu lagi layer dibuka di
  kanvas. Fallback subset v0.2.2 tetap dipertahankan sebagai jaring
  pengaman (bukan penyebabnya, tapi tidak merugikan). Render penuh di
  sandbox tetap lulus (10 lembar). Jujur: cabang QGIS 4.2.2 belum bisa
  diuji di sini — Derana perlu coba v0.2.3 TANPA membuka layer di kanvas
  dan laporkan apakah persil tetap muncul.
- **v0.3.0 (2026-11-20):** dua fitur besar. **(a) Satu proyek QGIS
  (.qgs) berisi SEMUA lembar sebagai layout** (`PBTF_{batch}.qgs` di
  folder output, checkbox "Simpan proyek QGIS" default aktif) — dibuka
  di QGIS, tiap lembar bisa diedit (geser label, betulkan nama, ubah
  teks panel), lalu diekspor ke PDF dari QGIS. Dibangun di QgsProject
  terpisah (bukan proyek user yang sedang terbuka); tiap lembar punya
  layer vektor sendiri (subset per-lembar) + layout sendiri dari
  template. PDF tetap dirender jalur lama (tidak berubah).
  **(b) Isi frame 9 butir** (bagian "Isi Frame" di panel; tanggal, TTD,
  dan logo yang sudah ada tetap): (1) Sistem Koordinat — dropdown 37
  pilihan Indonesia (TM-3 zona 46.1–54.2, UTM 46N–54N/46S–54S, WGS
  1984; default TM3 Zona 48.2) — teks label saja, CRS peta tetap ikut
  data; (2) Desa/Kelurahan — radio (satu wajib dipilih) + nama, masuk
  ke kolom nilai panel dan label kiri berubah ikut (Desa/Kelurahan);
  (3) Kabupaten/Kota — radio + nama, masuk ke panel DAN header atas
  frame; (4) Kecamatan + Provinsi — provinsi juga masuk header atas;
  (5) nama kabupaten/kota otomatis jadi nama tempat di baris tanggal
  ("Cianjur, 20 November 2026"); (6) Petugas Ukur + No Lisensi;
  (7) Pimpinan dari (PT) + nama + jabatan di bawah nama; (8) Penggunaan
  sebagai (peran) + nama + NIP; (9) Pelaksana PT + alamat. Label
  template dikenali dari isi teks bawaannya (dua label PT yang kembar
  dibedakan lewat posisi y); bila template lain dipakai dan label tidak
  ketemu, dicatat di log dan dilewati (tidak crash). Diuji headless
  (`test_frame_qgs.py`): nilai kustom (Kelurahan Sukamaju, Kota Bogor,
  UTM 48S, dst.) — 16/16 teks benar di .qgs hasil muat ulang, tanpa
  sisa nilai default; render penuh tetap lulus (10 lembar + .qgs 10
  layout + isi frame default).
- **v0.1.4 (2026-11-20):** perbaikan bug minimize — dialog yang
  diminimize "hilang" (tidak ada tombol taskbar sendiri karena dia anak
  jendela utama QGIS) dan klik tombol plugin tidak membukanya lagi,
  karena `run()` memakai `show()` yang tidak mengembalikan jendela yang
  diminimize di Windows. Sekarang memakai `showNormal()` (plus
  `raise_()` + `activateWindow()`), dan bila objek C++ dialog sudah
  dihapus, dialog dibuat baru. Diuji headless (`test_restore.py`):
  dialog kembali setelah minimize maupun setelah ditutup (X).
- Selama uji headless ditemukan & diperbaiki 4 perbedaan API QGIS 3.22:
  konstruktor `Rule(symbol, filter, label)` tidak menerima string,
  `setDataDefinedProperty` tidak ada (pakai koleksi properti),
  `setElse` tidak ada (pakai `setFilterExpression("ELSE")`), konstruktor
  `QgsRuleBasedRenderer` menyisipkan rule default isi biru (dihapus),
  dan variabel layout tidak ter-evaluasi di `[%...%]` (nilai ditulis
  literal seperti aplikasi desktop). Semuanya sudah masuk ke `engine.py`.

## Langkah berikut (bila PoC diterima)

1. Uji GUI di QGIS 4.2.2 Derana (satu lembar dulu).
2. Pindah render ke QgsTask + progress bar.
3. Samakan daftar field mapping dengan aplikasi desktop (saat ini display
   mapping belum ada — sama seperti desktop v17.14 yang mapping-nya
   display-only).
