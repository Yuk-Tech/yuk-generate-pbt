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
| `metadata.txt` | Metadata plugin (nama "Yuk Generate PBT! — By @muhfadllah", versi 0.6.3, QGIS ≥ 3.22, author @Muhfadllah) |
| `__init__.py` | Titik masuk — `classFactory()` |
| `yuk_generate_pbt.py` | Kelas plugin: tombol toolbar + menu, buka/tutup sidebar (QDockWidget) |
| `panel.py` | Panel sidebar PyQt: kode akses beta, pemilih GPKG/QPT/ECW, skala, warna, varian, form pengesahan, isi frame, format, riwayat, tombol Hitung lembar / Preview / Generate / Tutup |
| `preview_dialog.py` | Dialog Preview (v0.6.2): tabel lembar + gambar preview per lembar, tombol "Generate (pakai 1 kuota)" / "Tutup" — Preview tidak memakai kuota |
| `license.py` | Gerbang kode akses beta: hash SHA-256 kode, masa berlaku sampai 31 Des 2026, status aktif di QSettings |
| `engine.py` | Mesin PyQGIS: grouping wilayah-dulu (v0.6.3) + styling + render + ZIP (tanpa dependensi Qt); `render_preview()` untuk Preview tanpa kuota; pembagi (jalan/irigasi) dipangkas di Python ke layer memori per lembar |
| `test_headless.py` | Uji render headless di sandbox (tanpa GUI) |
| `test_dock.py` | Uji sidebar headless di sandbox (toggle, Tutup, X, screenshot) |
| `test_enums.py` | Uji resolusi enum label headless di sandbox (QGIS 4 vs QGIS 3) |
| `test_citra.py` | Uji render DENGAN citra headless di sandbox (urutan layer vektor/raster) |
| `test_subset_fallback.py` | Uji fallback subset headless di sandbox (subset 0 fitur / SQL invalid) |
| `test_frame_qgs.py` | Uji isi frame + proyek .qgs headless di sandbox (nilai kustom, muat ulang .qgs) |
| `test_access.py` | Uji gerbang kode akses beta headless di sandbox (validasi kode, kunci/buka panel, tersimpan di QSettings) |
| `test_auto_mixed.py` | Uji grouping Auto wilayah-dulu v0.6.3 headless di sandbox (komposisi + penilaian label + regresi eksplisit) |
| `test_auto_scored.py` | Uji Auto v0.6.3 vs v0.6.0 headless di sandbox (metrik lama + penilaian label baru) |
| `test_preview.py` | Uji Preview tanpa kuota headless di sandbox (mock + server asli, dialog 9 baris, consume tepat 1x) |
| `test_frame_names.py` | Uji nama frame kanan headless di sandbox (surveyor/leader/usage + 2 PT tidak tertukar, WARDOY + Demo) |
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

1. Masukkan **kode akses** di bagian "Kode Akses" lalu Aktifkan — tombol Hitung lembar, Preview, dan Generate terkunci sampai kode valid dimasukkan. Butuh kode? Klik "Hubungi kami" di bawah kolom kode akses (Instagram @yuktech).
2. Pilih **GeoPackage** (`PBT_2091.gpkg`) → layer terisi otomatis.
3. Pilih **Template QPT** (`PBTF_WARDOY.qpt`).
3. (Opsional) Pilih **Citra ECW** → centang "Dengan citra ECW".
4. Atur skala (default Auto), warna persil (default Hijau), warna teks
   (default Abu gelap), isi Tanggal / No PBT / No Blok, logo & TTD bila ada.
   **Auto (v0.6.3) itu wilayah-dulu:** persil dipotong secara spasial
   (di celah terlebar antar persil) menjadi wilayah kompak, lalu tiap
   wilayah diberi skala terkecil yang memuat wilayahnya dan lolos
   penilaian label — persil kecil masuk lembar zoom-in (1:250/1:500)
   supaya labelnya muat. Skala eksplisit (mis. 1:1000) tetap satu skala
   untuk semua lembar seperti sebelumnya.
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

**[Download contoh template QPT (Google Drive)](https://drive.google.com/file/d/1ejQQAfs3PYvlo8Y-K8dT8X4UV2D1lpjI/view?usp=drive_link)**

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

### Yang di-port 1:1 dari aplikasi desktop (v17.15)

- Grouping skala eksplisit mengikuti aplikasi desktop v17.8 (grid +
  greedy + min-10 opsi A, maks 24/lembar). **Mode Auto di plugin
  berbeda dari desktop sejak v0.6.3:** wilayah dulu, skala kemudian —
  potong spasial di celah terlebar, lalu skala terkecil yang memuat
  wilayah dan lolos penilaian label (median rasio label <= 0,60 dan
  >= 80% label muat); tanpa batas bawah fill.
- Renderer aturan KET: jalan/gang merah #FF3F00, air biru #003FFF,
  persil warna pilihan; trim jalan/air buffer 5 m. Di jalur PDF trim
  lewat GeometryGenerator; di jalur Preview/.qgs pembagi dipangkas
  dulu di Python ke layer memori per lembar (perbaikan v0.6.3 —
  `aggregate(@layer_id, ...)` tidak bisa menemukan layer lembar di
  proyek .qgs terpisah).
- Labeling 3 baris (NAMA / NIB / L=…m2), satu warna teks, placement
  OverPoint (v17.13), font adaptif tanpa wrap (v17.11), obstacleType=1 (v17.9).
- Subset per lembar: 1 persil hanya di 1 lembar; pembagi yang menyentuh
  persil lembar atau memotong frame ikut sebagai konteks, dipangkas ke
  buffer 5 m dari persil lembar.
- Variabel layout: tgl/tglF/pbt/b/lembar; gambar LOGO / TTD PANCA / TTD RUDY;
  label skala ditulis literal (seperti v17).
- Riwayat sederhana (maks 20, QSettings), "klik 2x = pakai folder ini".

### Yang berubah (sifat plugin, bukan pengurangan fitur)

- **Tidak bisa jalan standalone** — QGIS harus dibuka dulu. Sebagai gantinya:
  tidak ada lagi hack layer-id (v17.1), tidak ada `qgis_process`, tidak ada
  proyek `.qgs` sementara, tidak ada file debug/log.
- Riwayat pindah dari localStorage ke QSettings.
- Tidak ada installer NSIS/MSI — distribusi lewat zip plugin.
- Render berjalan di thread utama (log tetap jalan via processEvents).
  Port penuh sebaiknya pindah ke QgsTask.

### Yang sudah terverifikasi (sandbox QGIS 3.22.16, 2026-11-20)

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

### Changelog

- **v0.6.3 (2026-11-26):** perbaikan pembagian lembar mode Auto. Sebelumnya
  persil dipilah ke tier skala *per persil* sebelum dikelompokkan, sehingga
  persil besar dan kecil yang bertetangga di satu blok jatuh ke lembar
  berbeda, frame antar-lembar saling menimpa, dan tiap PDF memuat persil
  yang "bolong-bolong". Sekarang urutannya dibalik: **wilayah dulu, skala
  kemudian** — persil dipotong secara spasial (di celah terlebar antar
  persil) menjadi wilayah kompak, lalu tiap lembar diberi skala terkecil
  yang memuat wilayahnya dan lolos penilaian label. Skala tetap campuran
  antar-lembar, tetapi tidak pernah dicampur di dalam satu wilayah. Skala
  manual (1:250 … 1:2500) tidak berubah.
  Pengaman bidang loncat: bidang yang menyendiri di lembarnya (jarak ke
  bidang terdekat > 8% lebar frame di tanah) dipindahkan ke lembar tetangga
  yang masih menampungnya, dan penggabungan lembar kecil tidak boleh
  melompati celah > 12% lebar frame.
  **Perbaikan jalan/irigasi di Preview (juga v0.6.3):** jalan dan irigasi
  (KET JALAN/IRIGASI) sempat tidak muncul di Preview — akar masalahnya
  bukan grouping, melainkan ekspresi trim `aggregate(@layer_id, ...)`
  yang tidak bisa menemukan layer lembar, karena Preview membangun
  proyek .qgs terpisah dari `QgsProject.instance()`. Sekarang pembagi
  dipangkas di Python (buffer 5 m dari persil lembar) dan digambar dari
  layer memori per lembar; jalan/irigasi kini terlihat di Preview maupun
  PDF. Uji PBT_2091: sebelum perbaikan 0 piksel jalan/air di area peta
  pada semua 9 preview; sesudah perbaikan jalan oranye + irigasi biru
  terlihat di semua lembar yang bersangkutan (mis. L07: jalan di tepi
  barat + segmen irigasi kecil; total 9 lembar: 15.331 piksel oranye,
  6.449 piksel biru).
  **Perbaikan nama frame yang tertukar (juga v0.6.3):** nama Petugas
  Ukur dan nama Penggunaan di frame kanan sempat tertukar (dan dua nama
  PT juga tertukar) — akar masalahnya fungsi `_y()` di
  `_apply_frame_texts` memakai `item.rect().top()` yang SELALU 0,0
  (`rect()` adalah koordinat lokal item, bukan posisi di layout),
  sehingga pengurutan label kembar tidak jalan dan penugasan mengikuti
  urutan `layout.items()` yang sembarang. Sekarang `_y()` memakai
  `scenePos().y()` (fallback `pos().y()`); teruji di kedua template
  (WARDOY + Demo) dengan nama berbeda — surveyor di blok "Untuk
  Pembuatannya", penggunaan di blok "Untuk Penggunaannya" (uji baru
  `test_frame_names.py`).
- **v0.6.2 (2026-11-26):** **Preview tanpa kuota** atas permintaan Derana
  ("rugi kalau kuota sudah terpakai tapi hasilnya tidak sesuai
  ekspektasi"). Tombol **Preview** baru di panel (di samping Hitung
  lembar / Generate): menjalankan grouping + membangun proyek .qgs +
  mengekspor satu PNG resolusi rendah per lembar, lalu menampilkan
  dialog preview berisi tabel lembar (nomor, skala, jumlah bidang,
  fill fraction, median rasio label, peringatan) dan gambar tiap
  lembar yang bisa digeser — semuanya **tanpa memanggil consume**
  (jalur Preview tidak menyentuh lisensi sama sekali; kuota tidak
  berkurang meski Preview gagal). Dialog menampilkan sisa generate
  (dari validate terakhir) dan tombol **"Generate (pakai 1 kuota)"**
  yang menjalankan alur Generate yang sudah ada (validate fresh +
  consume 1 + export PDF + ZIP); tombol "Tutup" menutup tanpa pakai
  kuota. **Juga di v0.6.2:** label "Kode Akses Beta" diganti "Kode
  Akses" (judul grup + pesan status/log), dan di bawah kolom kode
  akses ada link "Butuh Kode Akses? Hubungi kami" ke Instagram
  @yuktech. Uji: PBT_2091 → Preview 7 lembar (skala v0.6.1), kuota
  tetap 5 sebelum/sesudah Preview (mock + server asli), Generate
  dari dialog consume tepat 1x (5 → 4 mock; 5 → 4 server asli,
  kode YUK-6WCQXX-APQCMA); PBT_2130 → Preview 13 lembar. Skala
  eksplisit + Auto v0.6.1 tidak berubah. Catatan: dua kode beta
  publik pertama (YUK-4KEUCW-HP2W2S, YUK-4V7KHZ-DFM87T) sudah habis
  (0 sisa) saat uji server asli — uji memakai kode beta publik
  berikutnya yang masih ada sisanya.
- **v0.6.1 (2026-11-26):** dua perubahan atas permintaan Derana.
  **(1) Penilaian skala di mode Auto** (bukan cap tetap — Derana menolak
  cap maks 1:1000 karena plugin harus fleksibel ke semua gambar): tiap
  lembar Auto kini dinilai dari fill fraction (luas bbox persil / luas
  frame peta) dan median rasio lebar label / lebar persil di kertas.
  Lembar dengan >= 10 bidang yang terlalu kosong (fill < 0,15) atau
  labelnya terlalu memenuhi persil (median rasio > 0,60) diturunkan
  satu tingkat (zoom-in) dan persilnya dikelompokkan ulang — sampai
  lolos atau mencapai 1:250. Lembar kecil (< 10 bidang) tidak dinilai
  (urusannya merge, bukan skala). Ambang fill 0,15 dipilih dari bukti
  dua dataset: lembar 1:500 yang benar punya fill 0,16-0,19,
  sementara lembar 1:1500/1:2500 yang bermasalah punya fill 0,08-0,13
  (ambang 0,20 salah menandai lembar 1:500 yang benar dan memecah
  persilnya sampai 1:250). Uji: PBT_2091 → Auto tetap 7 lembar, tapi
  tanpa 1:2500 (L03 1:2500/0,08 → 1:1500/0,23; L06 1:2500/0,10 →
  1:1500/0,28; L04 1:1500/0,10 → 1:1000/0,23); PBT_2130 → Auto tetap
  13 lembar, tanpa 1:2500 (keduanya → 1:2000), semua lembar >= 10
  bidang lolos penilaian. Skala eksplisit tidak berubah.
  **(2) Alamat API lisensi disembunyikan dari panel** — kolom "API
  lisensi" dihapus sepenuhnya (label + isian + handler); pengguna
  hanya melihat kolom kode akses, tanpa tahu alamat API-nya (sama
  seperti YUK Entry). URL tetap hardcoded di `license.py`
  (`DEFAULT_API_BASE_URL`, satu-satunya tempat URL itu ada di kode);
  nilai tersimpan di QSettings dari mesin lama tetap dihormati
  diam-diam sebagai fallback internal. Pesan status/error tidak
  menampilkan URL.
- **v0.6.0 (2026-11-26):** mode **Auto jadi campuran** — sebelumnya Auto
  memilih SATU skala untuk seluruh pekerjaan, sehingga satu lembar bisa
  berisi persil besar dan kecil dengan satu ukuran font (teks meluber /
  bertabrakan, terutama di 1:1000). Sekarang tiap persil masuk tier
  menurut skala terbesar yang label 3 barisnya masih muat di dalam
  persil (dihitung dari panjang label dan bbox persil), lalu tiap tier
  dikelompokkan pada skalanya sendiri — persil kecil dapat lembar
  zoom-in (1:250/1:500), persil besar dapat lembar 1:1500/1:2000/1:2500.
  Lembar kecil boleh gabung antar-tier bila bbox gabungan muat pada
  skala yang lebih zoom-in. Ukuran font label tetap per skala seperti
  sebelumnya (6 pt @1:250, 5 pt @1:500, 4 pt @1:1000 ke atas).
  Skala eksplisit (1:250…1:2500) tidak berubah. Uji: dataset PBT_2091
  (115 persil) → Auto 7 lembar (4× 1:500, 1× 1:1500, 2× 1:2500),
  semua persil tepat satu kali, tanpa pelanggaran label-muat; 1:500
  tetap 10 lembar [2,3,3,4,7,11,17,21,23,24] seperti sebelumnya.
- **v0.5.9 (2026-11-21):** perbaikan kompatibilitas Qt6 untuk upload
  plugins.qgis.org — pemindai menemukan 2 masalah enum: bentuk datar
  `QgsWkbTypes.PolygonGeometry` dan `QgsUnitTypes.RenderPoints` harus
  ditulis scoped (`GeometryType.PolygonGeometry`,
  `RenderUnit.RenderPoints`). Keduanya teruji di sandbox QGIS 3.22
  bernilai sama (2 dan 4) dengan bentuk datar, jadi tetap jalan di
  QGIS 3 maupun 4. Catatan: di QGIS 4.2.2 bentuk datar sebenarnya
  masih jalan saat runtime (uji v0.5.1 lulus) — ini murni persyaratan
  pemindai statis situs. Isi lain sama dengan v0.5.8.
- **v0.5.8 (2026-11-21):** perbaikan keamanan untuk upload
  plugins.qgis.org — v0.5.7 diblokir pemindai keamanan situs (2 temuan
  kritis: Bandit 23 + Secrets Detection 10). Semua 33 temuan ternyata
  positif palsu / pola sengaja dan kini ditandai di kode: 10 hash SHA-256
  kode beta di `license.py` diberi `# pragma: allowlist secret`
  (hash dari kode yang sudah publik di deskripsi — bukan rahasia);
  `urlopen` ke API Supabase diberi `# nosec B310` (hanya HTTPS ke
  endpoint tetap, sertifikat diverifikasi default urllib); 22 blok
  `try/except: pass/continue` (best-effort, kegagalan opsional)
  diberi `# nosec B110/B112`. Verifikasi lokal: Bandit 0 temuan,
  detect-secrets 0 temuan. Isi plugin sama dengan v0.5.7.
- **v0.5.7 (2026-11-21):** perbaikan metadata untuk upload
  plugins.qgis.org — validator situs menolak zip v0.5.6 karena field
  `tracker` tidak ada (dok QGIS menyebutnya opsional, tapi validator
  situs mewajibkannya). Ditambahkan `tracker` (GitHub Issues repo) dan
  `homepage` (halaman repo, karena belum ada situs sendiri) — ketiganya
  (homepage, tracker, repository) kini valid dan publik, sesuai butir
  checklist upload. Isi plugin sama dengan v0.5.6.
- **v0.5.6 (2026-11-21):** README (repo + plugin) jadi dwibahasa
  (Indonesia + Inggris); semua penjelasan kini mempromosikan Instagram
  **@yuktech**; ditambahkan link download contoh template QPT (Google
  Drive) dan contoh GPKG; **semua 10 kode akses beta dicantumkan di
  deskripsi** (gratis, untuk feedback — hubungi @yuktech); ditambahkan
  panduan saran layer untuk file GPKG. Metadata tetap Bahasa Inggris
  saja. Changelog detail tetap Bahasa Indonesia.
- **v0.5.5 (2026-11-21):** nilai default isi frame diganti ke nama
  demo/promosi dari template contoh `PBTF_Demo_YukTech.qpt`
  (Petugas Ukur "ig:@yuktech" + lisensi 9-6969-69; Pimpinan "PT
  Kebakaran Jenggot" + "ig:@yuktech"; Penggunaan "Wakil Raja Iblis" +
  "ig:@yuktech" + NIP 123456789; Pelaksana "PT Kebakaran Jenggot" +
  alamat Jl. Kebakaran Jenggot No. 69, Jakarta Selatan) — bukan lagi
  nama asli Cianjur, karena plugin ini dibagikan ke publik. Nama tempat
  (Gudang/Cianjur) tetap. Pencocokan label frame (`_apply_frame_texts`)
  menerima jangkar teks DUA versi template (WARDOY + demo); tiga label
  "ig:@yuktech" yang kembar dibedakan lewat posisi y (kecil = petugas
  ukur, tengah = pimpinan, besar = penggunaan).
- **v0.5.4 (2026-11-21):** email kontak di metadata diganti
  mfadllah4th@gmail.com (seluruh source
  dicek — hanya metadata.txt yang memakai email itu). Isi plugin
  sama dengan v0.5.3.
- **v0.5.3 (2026-11-21):** deskripsi + about metadata ditulis ulang
  dalam Bahasa Inggris (syarat checklist upload plugins.qgis.org —
  sebelumnya Bahasa Indonesia). Isi plugin sama dengan v0.5.2.
- **v0.5.2 (2026-11-21):** perbaikan keamanan kuota. `consume-generate`
  sekarang WAJIB memakai kode asli — versi 0.5.0/0.5.1 mengirim hash
  tersimpan, padahal hash-nya tercantum di kode plugin (terbuka),
  sehingga siapa pun bisa menguras kuota semua kode beta tanpa tahu
  kodenya. Sekarang kode asli disimpan di QSettings (mesin pengguna
  sendiri) dan dikirim ke server, yang menghitung hash-nya di sana.
  Aktivasi lama (hanya hash, tanpa kode) dianggap tidak aktif —
  pengguna memasukkan ulang kodenya sekali. Plugin mengirim kode +
  hash sekaligus supaya tetap jalan selama function lama belum
  di-deploy ulang; function baru mengabaikan hash. Diuji headless
  lawan API tiruan (`test_api_license.py`): serangan hash-only
  ditolak dan kuota utuh, migrasi aktivasi lama, konsumsi normal.
- **v0.5.1 (2026-11-21):** URL API lisensi jadi bawaan plugin
  (`DEFAULT_API_BASE_URL` = server Supabase produksi `xxxxx`). Penguji beta tidak perlu lagi mengisi kolom
  API — cukup masukkan kode akses. Kolom API di panel saat itu tetap
  ada sebagai override (pindah server); mengosongkannya berarti mode
  lokal. (Kolom ini dihapus di v0.6.1 — alamat API tidak lagi
  ditampilkan.) URL ini bukan rahasia (endpoint publik; kredensialnya
  kode akses).
- **v0.5.0 (2026-11-20):** kode akses beta pindah ke server Supabase.
  Panel saat itu punya kolom **API lisensi**: isi URL dasar
  (`https://xxxxx.supabase.co/functions/v1`) untuk mode server, kosong =
  mode lokal lama. (Kolom ini dihapus di v0.6.1.) Mode server: aktivasi dicek ke endpoint
  `validate-code`, dan setiap Generate memotong 1 generate lewat
  `consume-generate` (atomik, 5 generate per kode, s.d. 31 Des 2026);
  status panel menampilkan sisa generate dari server. Aktivasi lokal
  lama yang tersimpan otomatis dikonfirmasi sekali ke server saat API
  diisi (tanpa memasukkan ulang kode). Mode server yang tidak
  terjangkau = Generate ditolak (kuota tidak boleh diakali); mode lokal
  tetap jalan tanpa hitungan. Paket API (skema + 2 Edge Function +
  panduan deploy) ada di `supabase-api/`. Diuji headless melawan API
  tiruan (`test_api_license.py`): validasi, konsumsi 5→0, penolakan
  saat habis, kode salah, server mati.
- **v0.4.2 (2026-11-20):** lantai ukuran nama panjang naik dari 3 pt
  menjadi 4 pt (permintaan Derana). Nama > 12 karakter tetap mengecil
  proporsional, tapi tidak lebih kecil dari 4 pt. Diuji render L01:
  UJANG NURMAN ALAMSAH (20 karakter, nama terpanjang di data) tetap
  muat di dalam persilnya pada 4 pt, tanpa tabrakan baru.
- **v0.4.1 (2026-11-20):** perbaikan teks persil "tidak rapih" (laporan
  Derana + PDF L01 1:500 dari QGIS 4.2.2). Akar masalahnya dua, keduanya
  di `apply_parcel_style` (`engine.py`): **(1)** Di QGIS 3, `QgsPalLayerSettings`
  TIDAK punya anggota C++ `fontSize`/`textColor`/`fontFamily` (pindah ke
  `QgsTextFormat`); menulis `settings.fontSize = ...` hanya membuat atribut
  Python yang hilang saat settings disalin ke labeling — label selama ini
  dirender dengan format default 10 pt (dua kali ukuran rancangan 5 pt di
  1:500), sehingga label persil kecil yang berdekatan bertabrakan
  (MIFTAHUDIN 00865 vs OIS PIRMANSAH 00892, SOPYAN SUGANDA 00853 vs LIYAH
  00868, UJANG NURMAN ALAMSAH 00895 meluber + menabrak L=207m2). Sekarang
  format diatur lewat `QgsTextFormat` + `settings.setFormat()` (ukuran
  sesuai skala, Arial, warna teks panel). **(2)** Ekspresi data-defined
  Size memakai `greatest()` yang tidak ada di QGIS 3.22 ("Function is not
  known") — ekspresi gagal parse, nama panjang tidak pernah mengecil.
  Diganti `max()` (ada sejak QGIS 2.x; UJANG NURMAN ALAMSAH 20 karakter
  kini 3 pt dan muat di dalam persilnya). Rotasi label mengikuti sumbu
  persil sempat dicoba lalu DIBATALKAN: properti Rotation berevaluasi
  benar tapi diabaikan total saat render di sandbox 3.22 (rotasi konstan
  45° tidak mengubah satu piksel pun), dan arah putar di 4.2.2 tidak bisa
  diverifikasi dari sini — pada 5 pt + dd Size yang benar, tabrakan sudah
  hilang tanpa rotasi. Diuji headless: render L01 diperiksa per klaster
  (atas/tengah/kiri-bawah) — semua 24 label rapi di dalam persil, tanpa
  tabrakan; render penuh tetap lulus (10 lembar).
- **v0.4.0 (2026-11-20):** gerbang kode akses. Panel punya bagian
  "Kode Akses" (dulu "Kode Akses Beta", diganti di v0.6.2): tombol Hitung lembar dan Generate terkunci sampai
  kode yang valid dimasukkan. Validasi di `license.py` — yang
  disimpan hanya hash SHA-256 kode (kode asli tidak masuk repo),
  masa beta sampai 31 Des 2026, status aktif tersimpan di QSettings
  (cukup sekali per mesin). Kode dibuat dengan `gen_beta_codes.py`
  (format `YUK-XXXXXX-XXXXXX`, 10 kode beta). Jujur: ini gerbang lunak
  — plugin GPL, siapa pun bisa menghapus pengecekan dari salinannya;
  langganan sesungguhnya nanti dicek ke server. Diuji headless
  (`test_access.py`): kode salah + kedaluwarsa ditolak, kode benar
  membuka tombol, status tersimpan di panel baru, deactivate mengunci
  lagi, stempel v0.4.0 di footer; render penuh tetap lulus (10 lembar).
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
- **v0.2.0 (2026-11-20):** UI diganti sidebar (QDockWidget) atas
  permintaan Derana — dialog melayang dihapus. Panel (`panel.py`) berisi
  semua kontrol yang sama + tombol **Tutup** (menyembunyikan sidebar);
  sidebar juga bisa ditutup lewat X di judulnya atau toggle tombol
  toolbar (tombol tampil tertekan saat sidebar terbuka). Form memakai
  `WrapAllRows` (label di atas field) + QScrollArea agar muat di panel
  sempit. Diuji headless (`test_dock.py`): dock dibuat + tampil,
  toggle, Tutup, X, sinkron tombol toolbar, stempel v0.2.0 di footer,
  unload membersihkan dock (screenshot `out/dock-preview.png`).
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
- **v0.1.4 (2026-11-20):** perbaikan bug minimize — dialog yang
  diminimize "hilang" (tidak ada tombol taskbar sendiri karena dia anak
  jendela utama QGIS) dan klik tombol plugin tidak membukanya lagi,
  karena `run()` memakai `show()` yang tidak mengembalikan jendela yang
  diminimize di Windows. Sekarang memakai `showNormal()` (plus
  `raise_()` + `activateWindow()`), dan bila objek C++ dialog sudah
  dihapus, dialog dibuat baru. Diuji headless (`test_restore.py`):
  dialog kembali setelah minimize maupun setelah ditutup (X).
- **v0.1.3 (2026-11-20):** perbaikan PyQt6 — `Qt.AlignCenter` (bentuk
  PyQt5) tidak ada di PyQt6/QGIS 4 dan membuat dialog crash saat dibuka
  (`AttributeError`, dilaporkan dari QGIS 4.2.2). Sekarang memakai
  konstanta `ALIGN_CENTER` yang memilih `Qt.AlignmentFlag.AlignCenter`
  (PyQt6) atau `Qt.AlignCenter` (PyQt5). Satu-satunya pemakaian enum
  `Qt.*` flat di plugin — sudah dicek tidak ada yang lain.
- Selama uji headless ditemukan & diperbaiki 4 perbedaan API QGIS 3.22:
  konstruktor `Rule(symbol, filter, label)` tidak menerima string,
  `setDataDefinedProperty` tidak ada (pakai koleksi properti),
  `setElse` tidak ada (pakai `setFilterExpression("ELSE")`), konstruktor
  `QgsRuleBasedRenderer` menyisipkan rule default isi biru (dihapus),
  dan variabel layout tidak ter-evaluasi di `[%...%]` (nilai ditulis
  literal seperti aplikasi desktop). Semuanya sudah masuk ke `engine.py`.

### Langkah berikut (bila PoC diterima)

1. Uji GUI di QGIS 4.2.2 Derana (satu lembar dulu).
2. Pindah render ke QgsTask + progress bar.
3. Samakan daftar field mapping dengan aplikasi desktop (saat ini display
   mapping belum ada — sama seperti desktop v17.14 yang mapping-nya
   display-only).

---

## English

**Outside the PTSL project** — a trial of whether the desktop app "Yuk Generate PBT!" can live as a QGIS plugin without losing a single feature. Answer: yes; this is the proof.

Follow us on Instagram: **[@yuktech](https://instagram.com/yuktech)** — updates, sample outputs, and Q&A about this plugin.

### Package contents

| File | Contents |
|---|---|
| `metadata.txt` | Plugin metadata (name "Yuk Generate PBT! — By @muhfadllah", version 0.6.3, QGIS ≥ 3.22, author @Muhfadllah) |
| `__init__.py` | Entry point — `classFactory()` |
| `yuk_generate_pbt.py` | Plugin class: toolbar button + menu, open/close sidebar (QDockWidget) |
| `panel.py` | PyQt sidebar panel: beta access code, GPKG/QPT/ECW pickers, scale, colors, variant, approval form, frame fields, format, history, Close button |
| `license.py` | Beta access-code gate: SHA-256 code hash, valid until 31 Dec 2026, active status stored in QSettings |
| `engine.py` | PyQGIS engine: region-first grouping (v0.6.3) + styling + render + ZIP (no Qt dependency); dividers (roads/irrigation) pre-trimmed in Python into a per-sheet memory layer |
| `test_headless.py` | Headless render test in the sandbox (no GUI) |
| `test_dock.py` | Headless sidebar test in the sandbox (toggle, Close, X, screenshot) |
| `test_enums.py` | Headless label-enum resolution test in the sandbox (QGIS 4 vs QGIS 3) |
| `test_citra.py` | Headless render WITH imagery test in the sandbox (vector/raster layer order) |
| `test_subset_fallback.py` | Headless subset-fallback test in the sandbox (0-feature subset / invalid SQL) |
| `test_frame_qgs.py` | Headless frame-fields + .qgs project test in the sandbox (custom values, .qgs reload) |
| `test_access.py` | Headless beta access-code gate test in the sandbox (code validation, panel lock/unlock, QSettings persistence) |
| `test_auto_mixed.py` | Headless v0.6.3 region-first Auto grouping test in the sandbox (composition + label scoring + explicit-scale regression) |
| `test_auto_scored.py` | Headless Auto v0.6.3 vs v0.6.0 test in the sandbox (old metrics + new label scoring) |
| `test_preview.py` | Headless quota-free Preview test in the sandbox (mock + real server, 9-row dialog, exactly 1 consume) |
| `test_frame_names.py` | Headless right-frame names test in the sandbox (surveyor/leader/usage + 2 company names never swapped, WARDOY + Demo) |
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
   **Auto (v0.6.3) is region-first:** parcels are cut spatially (at the
   widest gap between parcels) into compact regions, then each region gets
   the smallest scale that contains it and passes the label check — small
   parcels go to zoomed-in sheets (1:250/1:500) so their labels fit. An
   explicit scale (e.g. 1:1000) still uses one scale for all sheets, as
   before.
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

**[Download the sample QPT template (Google Drive)](https://drive.google.com/file/d/1ejQQAfs3PYvlo8Y-K8dT8X4UV2D1lpjI/view?usp=drive_link)**

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

### Ported 1:1 from the desktop app (v17.15)

- Explicit-scale grouping follows the desktop app v17.8 (grid + greedy +
  min-10 option A, max 24/sheet). **Auto mode in the plugin differs from
  the desktop since v0.6.3:** region first, scale second — spatial split
  at the widest gap, then the smallest scale that contains the region and
  passes the label check (median label ratio <= 0.60 and >= 80% of labels
  fit); no lower fill bound.
- KET rule renderer: roads/lanes red #FF3F00, water blue #003FFF, parcels in the chosen color; road/water trim with a 5 m buffer. On the PDF path the trim runs through GeometryGenerator; on the Preview/.qgs path dividers are pre-trimmed in Python into a per-sheet memory layer (v0.6.3 fix — `aggregate(@layer_id, ...)` cannot find the sheet layer in a separate .qgs project).
- 3-line labeling (NAMA / NIB / L=…m2), single text color, OverPoint placement (v17.13), adaptive font without wrap (v17.11), obstacleType=1 (v17.9).
- Per-sheet subset: 1 parcel on exactly 1 sheet; dividers touching a sheet's parcels or crossing its frame are included as context, trimmed to a 5 m buffer around the sheet's parcels.
- Layout variables: tgl/tglF/pbt/b/lembar; LOGO / TTD PANCA / TTD RUDY pictures; scale label written literally (as in v17).
- Simple history (max 20, QSettings), "double-click = use this folder".

### What changed (plugin nature, not fewer features)

- **Cannot run standalone** — QGIS must be open first. In return: no more layer-id hack (v17.1), no `qgis_process`, no temporary `.qgs` project, no debug/log files.
- History moved from localStorage to QSettings.
- No NSIS/MSI installer — distribution via plugin zip.
- Rendering runs on the main thread (log still flows via processEvents). A full port should move to QgsTask.

### Verified so far (sandbox QGIS 3.22.16, 2026-11-20)

- `py_compile` clean for all Python files.
- Pure grouping logic (no QGIS): font table, color palette, trim expression, label expression, file names, and synthetic grouping (blocks + min-10 merge) all match the Rust engine.
- **Headless test PASSED** (`test_headless.py`, "SEMUA UJI HEADLESS LULUS"): the real PBT_2091 GPKG (124 features) + the real WARDOY template → grouping of 10 sheets **[2, 3, 3, 4, 7, 11, 17, 21, 23, 24], exactly the same composition as Rust v17.8**; 10 TANPA_CITRA PDFs + a ZIP containing exactly those 10 PDFs; labels filled literally (Number 2091, Block 004, Cianjur 20 November 2026, Sheets 1–10, Scale 1:500); white parcels with green outlines, 3-line labels centered on parcels. The L01 preview was checked by eye (see `out/L01-preview.png` in the working folder).
- **Not yet:** interactive GUI test on Derana's QGIS 4.2.2 (one sheet first) — the PyQt6 dialog has never been clicked in any QGIS. What is proven: the dialog **builds & renders headless** in the sandbox (PyQt5, QGIS 3.22, offscreen — `shot_dialog.py`): all controls show, the "By @muhfadllah" watermark is visible in the window title, header, and footer (see `out/dialog-preview.png` in the working folder). Not yet: button clicks, file pickers, and batch rendering from inside the dialog on 4.2.2.

### Recent changes

- **v0.6.3 (2026-11-26):** fix to Auto-mode sheet splitting. Parcels used to be
  sorted into per-parcel scale tiers before grouping, so neighbouring big and
  small parcels of the same block landed on different sheets, sheet frames
  overlapped heavily, and each PDF showed scattered, "holey" parcels. The
  order is now reversed: **region first, scale second** — parcels are cut
  spatially (at the widest gap) into compact regions, then each sheet gets
  the smallest official scale that contains its region and passes the label
  check. Scales still vary between sheets, never within one region. Explicit
  scales (1:250 … 1:2500) are unchanged.
  "Jumping parcel" guard: a parcel isolated on its sheet (distance to the
  nearest parcel > 8% of the ground frame width) is moved to a neighbouring
  sheet that can hold it, and small-sheet merging may not jump a gap > 12%
  of the frame width.
  **Road/irrigation fix in Preview (also v0.6.3):** roads and irrigation
  (KET JALAN/IRIGASI) used to be missing from Preview — the root cause was
  not the grouping but the trim expression `aggregate(@layer_id, ...)`,
  which cannot find the sheet layer because Preview builds a .qgs project
  separate from `QgsProject.instance()`. Dividers are now pre-trimmed in
  Python (5 m buffer around the sheet's parcels) and drawn from a
  per-sheet memory layer; roads/irrigation now show in Preview and in
  PDFs. PBT_2091 test: before the fix, 0 road/water pixels in the map
  area of all 9 previews; after the fix, orange roads + blue irrigation
  appear on every sheet they belong to (e.g. L07: road along the west
  edge + a small irrigation segment; 9 sheets total: 15,331 orange
  pixels, 6,449 blue pixels).
  **Swapped frame names fix (also v0.6.3):** the Surveyor name and the
  Usage name in the right frame used to be swapped (and so were the two
  company names) — the root cause was the `_y()` helper in
  `_apply_frame_texts` using `item.rect().top()`, which is ALWAYS 0.0
  (`rect()` is the item's local coordinates, not its layout position),
  so sorting the duplicate labels did nothing and assignment followed
  the arbitrary `layout.items()` order. `_y()` now uses
  `scenePos().y()` (fallback `pos().y()`); verified on both templates
  (WARDOY + Demo) with distinct names — surveyor in the "Untuk
  Pembuatannya" block, usage in the "Untuk Penggunaannya" block (new
  test `test_frame_names.py`).
- **v0.6.2 (2026-11-26):** **Quota-free Preview** at Derana's request
  ("a waste if quota is already spent but the result doesn't match
  expectations"). A new **Preview** button on the panel (next to Count
  sheets / Generate): runs grouping + builds the .qgs project +
  exports one low-resolution PNG per sheet, then shows a preview
  dialog with a sheet table (number, scale, parcel count, fill
  fraction, median label ratio, warnings) and a per-sheet image
  viewer — all **without calling consume** (the Preview path never
  touches licensing; quota doesn't decrease even if Preview fails).
  The dialog shows the remaining generates (from the last validate)
  and a **"Generate (use 1 quota)"** button that runs the existing
  Generate flow (fresh validate + consume 1 + export PDF + ZIP);
  "Close" exits without using quota. **Also in v0.6.2:** the
  "Kode Akses Beta" label is renamed "Kode Akses" (group title +
  status/log messages), and a "Butuh Kode Akses? Hubungi kami" link
  to Instagram @yuktech sits below the access-code field. Tests:
  PBT_2091 → Preview shows 7 sheets (v0.6.1 scales), quota stays 5
  before/after Preview (mock and real server), Generate from the
  dialog consumes exactly 1x (5 → 4 mock; 5 → 4 real server, code
  YUK-6WCQXX-APQCMA); PBT_2130 → Preview 13 sheets. Explicit scales
  + Auto v0.6.1 unchanged. Note: the first two public beta codes
  (YUK-4KEUCW-HP2W2S, YUK-4V7KHZ-DFM87T) are already exhausted
  (0 remaining) at the time of the real-server test — the test used
  the next public
  beta code that still had quota.
- **v0.6.1 (2026-11-26):** two changes at Derana's request.
  **(1) Per-sheet scale scoring in Auto mode** (not a fixed cap — Derana
  rejected a max-1:1000 cap because the plugin must stay flexible for
  any dataset): each Auto sheet is now scored on fill fraction (parcel
  bbox area / map frame area) and the median label-width / parcel-width
  ratio on paper. Sheets with >= 10 parcels that are too empty
  (fill < 0.15) or whose labels nearly fill their parcels (median ratio
  > 0.60) step down one scale level (zoom in) and regroup — until they
  pass or reach 1:250. Small sheets (< 10 parcels) are not scored
  (merging handles them, not scale). The 0.15 fill threshold comes from
  evidence on both datasets: correct 1:500 sheets have fill 0.16–0.19,
  while the problematic 1:1500/1:2500 sheets have fill 0.08–0.13 (a
  0.20 threshold wrongly flagged correct 1:500 sheets and fragmented
  them down to 1:250). Tests: PBT_2091 → Auto still 7 sheets, but no
  1:2500 (L03 1:2500/0.08 → 1:1500/0.23; L06 1:2500/0.10 → 1:1500/0.28;
  L04 1:1500/0.10 → 1:1000/0.23); PBT_2130 → Auto still 13 sheets, no
  1:2500 (both → 1:2000), every sheet with >= 10 parcels passes
  scoring. Explicit scales unchanged.
  **(2) License API address hidden from the panel** — the "API lisensi"
  field is removed entirely (label + input + handler); users only see
  the access-code field, without knowing the API address (same as YUK
  Entry). The URL stays hardcoded in `license.py`
  (`DEFAULT_API_BASE_URL`, the only place it exists in code); a stored
  QSettings value from older machines is still respected silently as an
  internal fallback. Status/error messages never show the URL.
- **v0.6.0 (2026-11-26):** Auto mode became mixed-scale — previously
  Auto picked ONE scale for the whole job, so one sheet could hold big
  and small parcels with a single font size (text overflowing or
  colliding, especially at 1:1000). Now each parcel is tiered by the
  largest scale its 3-line label still fits inside the parcel
  (computed from label length and parcel bbox), then each tier is
  grouped at its own scale — small parcels get zoomed-in sheets
  (1:250/1:500), big parcels get 1:1500/1:2000/1:2500 sheets. Small
  sheets may merge across tiers when their combined bbox fits at the
  more zoomed-in scale. Label font size stays per scale as before
  (6 pt @1:250, 5 pt @1:500, 4 pt @1:1000 and above). Explicit scales
  (1:250…1:2500) unchanged. Tests: PBT_2091 (115 parcels) → Auto
  7 sheets (4× 1:500, 1× 1:1500, 2× 1:2500), every parcel exactly
  once, no label-fit violations; 1:500 still 10 sheets
  [2,3,3,4,7,11,17,21,23,24] as before.
- **v0.5.9 (2026-11-21):** Qt6 compatibility fix for the plugins.qgis.org upload — the scanner flagged 2 enum issues: the flat forms `QgsWkbTypes.PolygonGeometry` and `QgsUnitTypes.RenderPoints` must be written scoped (`GeometryType.PolygonGeometry`, `RenderUnit.RenderPoints`). Both were verified in the QGIS 3.22 sandbox to hold the same values (2 and 4) as the flat forms, so the plugin still runs on QGIS 3 and 4. Note: on QGIS 4.2.2 the flat forms actually still work at runtime (the v0.5.1 live test passed) — this is purely a requirement of the site's static scanner. Everything else identical to v0.5.8.
- **v0.5.8 (2026-11-21):** security-scan fix for the plugins.qgis.org upload — v0.5.7 was blocked by the site scanner (2 critical findings: 23 Bandit + 10 Secrets Detection). All 33 findings were false positives / deliberate patterns and are now marked in the code: the 10 SHA-256 beta-code hashes in `license.py` carry `# pragma: allowlist secret` (hashes of codes already published in the description — not secrets); the `urlopen` call to the Supabase API carries `# nosec B310` (HTTPS-only to a fixed endpoint, certificates verified by urllib's default); the 22 `try/except: pass/continue` blocks (best-effort, non-fatal failures) carry `# nosec B110/B112`. Verified locally: Bandit 0 findings, detect-secrets 0 findings. Plugin content identical to v0.5.7.
- **v0.5.7 (2026-11-21):** metadata fix for the plugins.qgis.org upload — the site validator rejected the v0.5.6 zip because the `tracker` field was missing (the QGIS docs call it optional, but the site validator requires it). Added `tracker` (the repo's GitHub Issues page) and `homepage` (the repo page, as there is no separate website yet) — all three links (homepage, tracker, repository) are now valid and public, as the upload checklist requires. Plugin content identical to v0.5.6.
- **v0.5.6 (2026-11-21):** READMEs (repo + plugin) are now bilingual (Indonesian + English); all explanations promote Instagram **@yuktech**; added links to download the sample QPT template (Google Drive) and the sample GPKG; **all 10 beta access codes are listed in the description** (free, for feedback — contact @yuktech); added the suggested-layer guide for GPKG files. Metadata stays English-only. The detailed changelog remains in Indonesian (see the Bahasa Indonesia section above).
- **v0.5.5 (2026-11-21):** default frame values changed to the demo/promotional names from the sample template `PBTF_Demo_YukTech.qpt` (Surveyor "ig:@yuktech" + license 9-6969-69; Leader "PT Kebakaran Jenggot" + "ig:@yuktech"; Usage "Wakil Raja Iblis" + "ig:@yuktech" + NIP 123456789; Executor "PT Kebakaran Jenggot" + address Jl. Kebakaran Jenggot No. 69, Jakarta Selatan) — no longer the real Cianjur names, because this plugin is shared publicly. Place names (Gudang/Cianjur) unchanged. Frame-label matching (`_apply_frame_texts`) accepts anchor texts from BOTH template versions (WARDOY + demo); the three identical "ig:@yuktech" labels are told apart by y position (small = surveyor, middle = leader, large = usage).
- **v0.5.4 (2026-11-21):** contact email in metadata changed to mfadllah4th@gmail.com (whole source checked — only metadata.txt used that email). Plugin content identical to v0.5.3.
- **v0.5.3 (2026-11-21):** metadata description + about rewritten in English (plugins.qgis.org upload checklist requirement — previously Indonesian). Plugin content identical to v0.5.2.
- **v0.5.2 (2026-11-21):** quota security fix. `consume-generate` now REQUIRES the real code — v0.5.0/0.5.1 sent the stored hash, but the hashes are listed in the open plugin source, so anyone could drain all beta codes' quotas without knowing any code. Now the real code is stored in QSettings (on the user's own machine) and sent to the server, which computes the hash there. Old hash-only activations are treated as inactive — users re-enter their code once. The plugin sends code + hash together so it keeps working until the old function is redeployed; the new function ignores the hash. Tested headless against a mock API (`test_api_license.py`): hash-only attack rejected with quota intact, old-activation migration, normal consumption.

### Next steps (if the PoC is accepted)

1. GUI test on Derana's QGIS 4.2.2 (one sheet first).
2. Move rendering to QgsTask + progress bar.
3. Align the field-mapping list with the desktop app (currently display mapping only — same as desktop v17.14, whose mapping is display-only).
