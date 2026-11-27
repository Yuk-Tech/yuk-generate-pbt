"""
Yuk Generate PBT! — mesin plugin QGIS (PoC).

Port Python dari engine Rust aplikasi desktop "Yuk Generate PBT!"
(v17.15), khusus untuk dipakai DI DALAM QGIS lewat PyQGIS. Tidak ada
dependensi Qt di file ini — logika grouping + styling + render bisa diuji
headless (QgsApplication tanpa GUI).

Yang di-port 1:1 dari src-tauri/src/engine.rs:
- pengelompokan hibrida v17.7 (blok oleh pembagi + grid + greedy + min-10
  opsi A v17.8), termasuk konstanta sel 2 m / buffer 2 m / trim 5 m;
- renderer aturan KET (jalan merah #FF3F00, air biru #003FFF, persil warna
  pilihan) + trim GeometryGenerator;
- labeling single-expression (persil biasa NAMA / NIB / L=...m2;
  persil SHM hanya NIB / No Hak, v0.6.6), satu warna,
  placement OverPoint (v17.13), font adaptif tanpa wrap (v17.11),
  obstacleType=1 (v17.9);
- nama file PDF PBTF_{batch}_{Lxx}_{skala}_{CITRA|TANPA_CITRA}.pdf;
- ZIP hanya berisi PDF (v17.15), tanpa file debug/log.

Yang TIDAK perlu di-port (lebih mudah di plugin):
- layer-id hack v17.1 — layer di plugin adalah objek hidup, bukan XML;
- qgis_process — render langsung lewat QgsLayoutExporter di dalam QGIS.

Yang DITAMBAH di plugin (tidak ada di desktop v17.15):
- proyek QGIS (.qgs) berisi SEMUA lembar sebagai layout (v0.3.0) —
  bisa dibuka dan diedit di QGIS sebelum diekspor ke PDF;
- isi frame 9 butir (sistem koordinat, desa/kelurahan, kabupaten/kota,
  kecamatan, provinsi, petugas ukur, pimpinan, penggunaan, pelaksana)
  ditulis ke label layout (v0.3.0);
- mode Auto CAMPURAN (v0.6.0): tiap persil masuk tier menurut skala
  terbesar yang label 3 barisnya masih muat (label_fits /
  parcel_max_denominator); tiap tier dikelompokkan pada skalanya
  sendiri; merge_small_accs scale-aware (gabung antar-tier hanya bila
  bbox gabungan muat pada skala min). Skala eksplisit tetap satu skala.
- penilaian skala per lembar (v0.6.1): tiap lembar Auto dinilai dari
  fill fraction (luas bbox persil / luas frame peta) dan median rasio
  lebar label / lebar persil di kertas; lembar dengan >= 10 bidang
  yang terlalu kosong (fill < 0,15) atau labelnya terlalu memenuhi
  persil (median rasio > 0,60) diturunkan satu tingkat (zoom-in) dan
  persilnya dikelompokkan ulang — sampai lolos atau mencapai 1:250.
  Lembar kecil (< 10 bidang) tidak dinilai (urusannya merge, bukan
  skala). Bukan cap tetap: dataset persil besar yang memang padat di
  1:2500 boleh tetap 1:2500.
- SHP persil PER LEMBAR + ZIP per lembar (v0.7.2, port PBTK v0.2.3):
  satu file ZIP per lembar (PBTF_{batch}_{Lxx}_{skala}_persil.zip,
  berisi 5 komponen SHP), hanya persil lembar itu (tanpa pembagi);
  file SHP lepas dihapus setelah ZIP terverifikasi.
- grid peta skala-bergantung opsi B (v0.7.2, port PBTK v0.2.1): jarak
  garis 100 mm di layout, interval tanah = denominator x 0,1 m,
  offset per lembar supaya garis lewat titik jangkar (pusat frame —
  asumsi, tidak ada referensi grid PBT yang bisa diukur; template
  PBTF_WARDOY.qpt intervalnya 0 sehingga grid tidak ter-render
  sebelum v0.7.2). Label grid bilangan bulat (annotationPrecision 0).
"""

import math
import os
import re
import zipfile
from collections import deque

# ---------------------------------------------------------------------------
# Konstanta (sama persis dengan engine Rust)
# ---------------------------------------------------------------------------

OFFICIAL_SCALES = [250.0, 500.0, 1000.0, 1500.0, 2000.0, 2500.0]
FILL_RATIO = 0.95
MAX_FEATURES_PER_SHEET = 24
MIN_FEATURES_PER_SHEET = 10
BLOCK_CELL_M = 2.0
BLOCK_BUFFER_M = 2.0
TRIM_BUFFER_M = 5.0
# v0.7.4: toleransi trim pembagi (m). Tepi jalan/sungai yang berjalan
# tepat di batas persil (offset digitasi beberapa cm) terpotong oleh
# trim v0.6.9 di tiap sentuhan sudut persil — garis jadi fragmen.
# Persil dikecilkan TRIM_TOL_M saat menghitung `keep`, jadi garis yang
# menyentuh/masuk persil sedalam <= TRIM_TOL_M tetap utuh. 0,20 m =
# 0,8 mm di 1:250 (di bawah ambang terlihat), jauh di bawah X-crossing
# v0.6.9 yang diperbaiki trim (orde meter).
TRIM_TOL_M = 0.20
# v0.7.5: toleransi sambung potongan pembagi (m). Persil jalan/sungai
# yang dipotong pendek-pendek saat disetorkan terpisah-pisah di GPKG;
# potongan yang sama jalan (KET sama) bersentuhan persis di sambungannya
# (jarak cincin 0,000 m, berbagi 2 vertex — diukur TEST-PBT-277 di
# PBT_2091: sambungan 6-97, 6-117, 97-117, 20-28 semuanya 0,000 m),
# sedangkan pasangan se-KET terdekat yang BUKAN sambungan berjarak
# 0,98 m (IRIGASI 20-89) — jadi 0,05 m duduk di celah yang bersih:
# cukup longgar untuk noise digitasi sub-cm, jauh di bawah 0,98 m.
MERGE_TOL_M = 0.05
DEFAULT_MAP_MM = (308.0, 276.0)

ROAD_WORDS = ["jalan", "gang"]
WATER_WORDS = ["sungai", "irigasi", "saluran", "selokan"]
SPECIAL_WORDS = ROAD_WORDS + WATER_WORDS

# ---------------------------------------------------------------------------
# Helper geometri / skala (port langsung)
# ---------------------------------------------------------------------------


def union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def parse_scale(text):
    """'1:1000' -> 1000.0 ; '1.000' (ribuan) ikut didukung seperti Rust."""
    if not isinstance(text, str) or ":" not in text:
        return None
    left, right = text.split(":", 1)
    if left.strip() != "1":
        return None
    try:
        value = float(right.strip().replace(".", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def scale_label(denominator):
    return "1:{}".format(int(round(denominator)))


def fits_at(bbox, map_mm, denominator):
    width = map_mm[0] / 1000.0 * denominator * FILL_RATIO
    height = map_mm[1] / 1000.0 * denominator * FILL_RATIO
    return bbox[2] - bbox[0] <= width and bbox[3] - bbox[1] <= height


def pick_scale(requested, bbox, map_mm):
    if requested == "Auto":
        for candidate in OFFICIAL_SCALES:
            if fits_at(bbox, map_mm, candidate):
                return (candidate, True)
        return (OFFICIAL_SCALES[-1], False)
    denominator = parse_scale(requested)
    if denominator is None:
        denominator = 1000.0
    return (denominator, fits_at(bbox, map_mm, denominator))


def validate_requested_scale(requested):
    if requested == "Auto":
        return None
    value = parse_scale(requested)
    if value is None or value not in OFFICIAL_SCALES:
        return (
            "Skala '{}' tidak valid. Pilih Auto, 1:250, 1:500, 1:1000, "
            "1:1500, 1:2000, atau 1:2500.".format(requested)
        )
    return None


def layout_extent(center, denominator, map_mm):
    half_w = map_mm[0] / 1000.0 * denominator / 2.0
    half_h = map_mm[1] / 1000.0 * denominator / 2.0
    return [
        center[0] - half_w,
        center[1] - half_h,
        center[0] + half_w,
        center[1] + half_h,
    ]


def is_special_ket(ket):
    if not ket:
        return False
    lower = str(ket).lower()
    return any(w in lower for w in SPECIAL_WORDS)


def label_font_size_pt(denominator):
    d = int(round(denominator))
    if d <= 250:
        return 6
    if d <= 500:
        return 5
    return 4


# ---------------------------------------------------------------------------
# Grid peta skala-bergantung (v0.7.2, opsi B — port dari PBTK v0.2.1)
# ---------------------------------------------------------------------------
# Prinsip opsi B (pilihan Derana 2026-11-27): jarak garis di layout
# TETAP (seperti contoh), interval tanah = denominator x 0,1 m
# (1:250 -> 25 m ... 1:2500 -> 250 m); offset dihitung PER LEMBAR
# supaya satu garis lewat titik jangkar; label menampilkan koordinat
# asli (tidak dibulatkan ke kelipatan 250).
#
# JANGKAR PBT (ASUMSI, dinyatakan eksplisit — bukan salinan PBTK):
# frame PBT 308,594 x 276,749 mm (Map 1 PBTF_WARDOY.qpt, posisi
# 10.0229, 10.1488 mm). TIDAK ADA referensi grid PBT yang bisa diukur
# — template intervalX=0/intervalY=0 (grid tidak ter-render; terbukti
# render lama tanpa label grid) dan tidak ada lembar PBT jadi dengan
# grid. Jadi jangkar = PUSAT frame (50% lebar, 50% tinggi): garis
# tengah vertikal 154,30 mm dari tepi kiri, garis tengah horizontal
# 138,37 mm dari tepi atas. Dengan jarak layout 100 mm, garis jatuh
# di vertikal [54,30 / 154,30 / 254,30] mm dan horizontal
# [38,37 / 138,37 / 238,37] mm — 3+3 garis di semua skala, simetris.
# Bila Derana punya lembar contoh dengan posisi grid yang diinginkan,
# jangkar ini tinggal diganti angkanya.
GRID_LAYOUT_SPACING_MM = 100.0
GRID_ANCHOR_X_MM = 154.30  # garis tengah vertikal, dari tepi kiri frame
GRID_ANCHOR_Y_MM = 138.37  # garis tengah horizontal, dari tepi atas frame


def grid_interval_m(denominator):
    """Interval grid tanah (meter) opsi B: jarak layout tetap 100 mm,
    jadi interval = denominator * 0,1 m. 1:250 -> 25 m, 1:500 -> 50 m,
    1:1000 -> 100 m, 1:1500 -> 150 m, 1:2000 -> 200 m, 1:2500 -> 250 m.
    None bila denominator tidak valid."""
    try:
        d = float(denominator)
    except (TypeError, ValueError):
        return None
    if d <= 0:
        return None
    return d * GRID_LAYOUT_SPACING_MM / 1000.0


def grid_offsets(extent, map_mm, denominator):
    """Offset grid (meter) per lembar supaya satu garis lewat titik
    jangkar layout (GRID_ANCHOR_X_MM dari kiri, GRID_ANCHOR_Y_MM dari
    atas). extent = [xmin, ymin, xmax, ymax] (meter, CRS peta);
    map_mm = (lebar, tinggi) frame peta (mm). Mengembalikan
    (offsetX, offsetY) dalam [0, interval); garis grid di
    offset + k*interval, jadi satu garis tepat lewat titik jangkar.
    None bila denominator/extent tidak valid."""
    interval = grid_interval_m(denominator)
    if interval is None:
        return None
    try:
        xmin, ymin, xmax, ymax = (float(v) for v in extent)
        w_mm, h_mm = (float(v) for v in map_mm)
    except (TypeError, ValueError):
        return None
    if w_mm <= 0 or h_mm <= 0 or xmax <= xmin or ymax <= ymin:
        return None
    x_anchor = xmin + (GRID_ANCHOR_X_MM / w_mm) * (xmax - xmin)
    y_anchor = ymax - (GRID_ANCHOR_Y_MM / h_mm) * (ymax - ymin)
    return (x_anchor % interval, y_anchor % interval)


def grid_line_layout_positions(extent, map_mm, denominator):
    """Posisi garis grid di layout (mm dari tepi kiri/atas frame) untuk
    satu lembar — dipakai uji murni + verifikasi render: dihitung dari
    offset (bukan dari QGIS) sehingga posisi yang diharapkan bisa
    dibandingkan dengan garis yang ter-render. Mengembalikan
    (xs_mm, ys_mm): posisi garis vertikal (dari kiri) dan horizontal
    (dari atas) yang jatuh di dalam frame. ([], []) bila tidak valid."""
    offs = grid_offsets(extent, map_mm, denominator)
    interval = grid_interval_m(denominator)
    if offs is None or interval is None:
        return ([], [])
    ox, oy = offs
    xmin, ymin, xmax, ymax = (float(v) for v in extent)
    w_mm, h_mm = (float(v) for v in map_mm)
    xs = []
    k = math.ceil((xmin - ox) / interval - 1e-9)
    while True:
        x = ox + k * interval
        if x > xmax + 1e-9:
            break
        xs.append((x - xmin) / (xmax - xmin) * w_mm)
        k += 1
    ys = []
    k = math.ceil((ymin - oy) / interval - 1e-9)
    while True:
        y = oy + k * interval
        if y > ymax + 1e-9:
            break
        ys.append((ymax - y) / (ymax - ymin) * h_mm)
        k += 1
    return (xs, ys)


def _attr_str(value):
    """Nilai atribut fitur -> str; NULL -> "".

    QGIS 3.22 (OGR) mengembalikan NULL sebagai QVariant null, BUKAN
    Python None — `v is None` saja TIDAK cukup: str(QVariant null)
    = "NULL" (truthy). Dipakai di kode BARU yang membaca atribut
    (ekspor SHP v0.7.2); JANGAN dipakai untuk mengubah perilaku
    label_len_of/val() lama (bug QVariant-null itu di luar scope
    v0.7.2, menunggu keputusan Derana)."""
    if value is None:
        return ""
    try:
        if value.isNull():
            return ""
    except AttributeError:
        pass
    return str(value)


# ---------------------------------------------------------------------------
# Kecocokan label (mode Auto campuran, v0.6.0)
# ---------------------------------------------------------------------------
# Label 3 baris (NAMA / NIB / L=...m2) dirender dengan font
# label_font_size_pt(denominator). Lebar satu karakter rata-rata
# diperkirakan 0,55 × ukuran font (Arial proporsional) dan tinggi baris
# 1,2 × ukuran font; 1 pt = 0,3528 mm. Label dianggap muat bila lebar dan
# tingginya ≤ 85% lebar/tinggi bbox persil di kertas — 15% sisanya untuk
# bentuk persil yang tidak persegi dan padding label QGIS.

PT_TO_MM = 0.3528
LABEL_FIT_RATIO = 0.85
LABEL_CHAR_WIDTH_FACTOR = 0.55
LABEL_LINE_HEIGHT_FACTOR = 1.2


def label_fits(parcel, denominator):
    """True bila label persil muat di dalam bbox persil di kertas
    pada skala `denominator`. Tinggi label = label_lines baris
    (v0.6.6: 3 biasa, 2 SHM)."""
    font_pt = label_font_size_pt(denominator)
    label_w_mm = parcel.label_len * LABEL_CHAR_WIDTH_FACTOR * font_pt * PT_TO_MM
    label_h_mm = parcel.label_lines * font_pt * LABEL_LINE_HEIGHT_FACTOR * PT_TO_MM
    paper_w_mm = (parcel.bbox[2] - parcel.bbox[0]) / denominator * 1000.0
    paper_h_mm = (parcel.bbox[3] - parcel.bbox[1]) / denominator * 1000.0
    return (
        label_w_mm <= LABEL_FIT_RATIO * paper_w_mm
        and label_h_mm <= LABEL_FIT_RATIO * paper_h_mm
    )


def parcel_max_denominator(parcel):
    """Skala TERBESAR (penyebut terbesar = paling kecil di kertas) yang
    label persil ini masih muat, dari OFFICIAL_SCALES. Mengembalikan
    (denominator, warning) — warning berisi pesan bila label tidak muat
    bahkan pada 1:250 (tetap dikembalikan 250 supaya render jalan).
    label_len 0 (tidak diketahui) dianggap muat di semua skala."""
    if parcel.label_len <= 0:
        return (OFFICIAL_SCALES[-1], None)
    for d in reversed(OFFICIAL_SCALES):
        if label_fits(parcel, d):
            return (d, None)
    return (
        OFFICIAL_SCALES[0],
        "Label bidang {} tidak muat bahkan pada skala 1:{}; "
        "label mungkin meluber.".format(parcel.id, int(OFFICIAL_SCALES[0])),
    )


# ---------------------------------------------------------------------------
# Penilaian skala lembar (mode Auto, v0.6.1)
# ---------------------------------------------------------------------------
# Aturan v0.6.0 ("skala TERBESAR yang labelnya muat") terlalu agresif:
# setengah persil PBT_2091 (58/115) dilempar ke 1:2500, lembarnya ~90%
# kosong (fill 8-10%) dan label 4pt berdesakan (rasio median 0,64) —
# secara aturan "muat", secara praktik PBT tidak cocok (lihat
# DIAG-2091-2026-11-26.md). Derana menolak cap tetap (mis. maks 1:1000)
# karena plugin harus fleksibel ke semua gambar: dataset persil besar
# yang memang padat di 1:2500 BOLEH tetap 1:2500.
#
# Karena itu tiap lembar Auto DINILAI pada skalanya sendiri, dari dua
# ukuran yang bisa dihitung:
#   (a) fill fraction = luas bbox persil / luas frame peta di tanah
#       (target ~0,30-0,60; < 0,15 = lembar terlalu kosong);
#   (b) rasio label = lebar label / lebar persil di kertas, median
#       per lembar (target ~0,3-0,5; > 0,60 = label nyaris memenuhi
#       persil, sulit dibaca).
# Ambang fill 0,15 (bukan 0,20): bukti dari dua dataset — lembar
# 1:500 yang BENAR (persil kecil, skala tepat) punya fill 0,16-0,19,
# sementara lembar 1:1500/1:2500 yang bermasalah (lembar ~90% kosong)
# punya fill 0,08-0,13. Ambang 0,20 salah menandai lembar 1:500 yang
# benar sebagai gagal, sehingga persilnya dipecah sampai 1:250 (uji
# pertama v0.6.1: PBT_2091 meledak dari 7 menjadi 16 lembar).
# Lembar dengan < 10 bidang TIDAK dinilai (lihat _rescore_auto_sheets):
# kekosongan / kesesakan label pada lembar kecil adalah masalah JUMLAH
# bidang, bukan skala — merge_small_accs yang mengurusnya.
# Lembar yang gagal (fill < 0,15 ATAU median rasio > 0,60) diturunkan
# satu tingkat (zoom-in) dan persilnya dikelompokkan ulang pada skala
# baru, lalu dinilai lagi — sampai lolos atau mencapai skala terkecil
# (1:250). Penilaian hanya bisa MENURUNKAN skala lembar, tidak pernah
# menaikkan di atas D_max terkecil persil di dalamnya (skala awal =
# tier D_max, dan tiap langkah hanya turun). Jumlah lembar bukan
# kriteria keras: lebih sedikit lebih baik, tapi TIDAK boleh
# mengorbankan fill dan rasio label.
# Catatan: penilaian jalan SEBELUM merge_small_accs. Lembar hasil
# merge mewarisi kelolosan: gabungan dua lembar yang lolos, pada skala
# min, punya fill >= fill tiap penyusun (bbox gabungan >= bbox
# penyusun, frame min <= frame penyusun) dan median rasio <= maks
# median penyusun (tiap persil di skala min rasionya <= rasio di skala
# asalnya) — jadi lembar merge tidak perlu dinilai ulang.

AUTO_MIN_FILL = 0.15
AUTO_MAX_LABEL_RATIO = 0.60


def sheet_fill_fraction(acc, map_mm):
    """Luas bbox persil / luas frame peta di tanah (0..1)."""
    den = acc.scale if acc.scale else 1000.0
    frame_w = map_mm[0] / 1000.0 * den
    frame_h = map_mm[1] / 1000.0 * den
    frame_area = frame_w * frame_h
    if frame_area <= 0:
        return 0.0
    return area(acc.bbox) / frame_area


def sheet_label_ratio_median(acc, parcels_by_id):
    """Median rasio lebar label / lebar persil di kertas untuk persil
    di lembar ini (0 bila tidak ada persil yang bisa dihitung)."""
    den = acc.scale if acc.scale else 1000.0
    font_pt = label_font_size_pt(den)
    ratios = []
    for pid in acc.ids:
        p = parcels_by_id.get(pid)
        if p is None or p.label_len <= 0:
            continue
        paper_w_mm = (p.bbox[2] - p.bbox[0]) / den * 1000.0
        if paper_w_mm <= 0:
            continue
        label_w_mm = p.label_len * LABEL_CHAR_WIDTH_FACTOR * font_pt * PT_TO_MM
        ratios.append(label_w_mm / paper_w_mm)
    if not ratios:
        return 0.0
    ratios.sort()
    n = len(ratios)
    if n % 2:
        return ratios[n // 2]
    return (ratios[n // 2 - 1] + ratios[n // 2]) / 2.0


def sheet_score_ok(acc, parcels_by_id, map_mm):
    """(lolos, fill, rasio_median) — lolos bila fill >= AUTO_MIN_FILL
    dan median rasio <= AUTO_MAX_LABEL_RATIO."""
    fill = sheet_fill_fraction(acc, map_mm)
    ratio = sheet_label_ratio_median(acc, parcels_by_id)
    return (fill >= AUTO_MIN_FILL and ratio <= AUTO_MAX_LABEL_RATIO, fill, ratio)


def sheet_group_metrics(groups, boxes, map_mm):
    """Metrik per lembar untuk tabel Preview (v0.6.2): daftar dict
    {id, scale, count, fill, ratio, ok, warnings} — bbox tiap lembar
    direkonstruksi dari union bbox persilnya (sama dengan acc.bbox),
    lalu dinilai dengan sheet_score_ok yang sama dengan penilaian
    Auto v0.6.1. Lembar kecil (< 10 bidang) tetap dilaporkan apa
    adanya (fill/rasio bisa gagal — itu urusan merge, bukan skala)."""
    parcels_by_id = {b.id: b for b in boxes}
    out = []
    for g in groups:
        ids = [fid for fid in g.feature_ids if fid in parcels_by_id]
        if ids:
            bbox = parcels_by_id[ids[0]].bbox[:]
            for fid in ids[1:]:
                bbox = union(bbox, parcels_by_id[fid].bbox)
        else:
            bbox = list(g.extent)
        acc = Acc(list(g.feature_ids), bbox, scale=parse_scale(g.scale))
        ok, fill, ratio = sheet_score_ok(acc, parcels_by_id, map_mm)
        out.append(
            {
                "id": g.id,
                "scale": g.scale,
                "count": len(g.feature_ids),
                "fill": fill,
                "ratio": ratio,
                "ok": ok,
                "warnings": list(g.warnings),
            }
        )
    return out


def _regroup_at_scale(members, new_den, map_mm):
    """Kelompokkan ulang persil pada skala baru (v0.6.1).

    Bila semua persil muat dalam satu frame pada skala baru, kembalikan
    SATU acc (persil tetap bersama). Ini sengaja TIDAK memakai
    _accs_at_scale: pemecahan grid/blok di sana memecah lembar yang
    sudah kohesif menjadi banyak lembar kecil, yang lalu gagal fill
    lagi dan berjatuhan sampai 1:250 (terbukti di uji pertama v0.6.1:
    PBT_2091 meledak dari 7 menjadi 16 lembar, 8 di antaranya 1:250).
    Penilaian skala mengubah SKALA, bukan pengelompokan — jadi persil
    tetap bersama selama muat; hanya bila tidak muat, pecah dengan
    greedy (greedy_accs) seminimal mungkin."""
    merged = members[0].bbox[:]
    for f in members[1:]:
        merged = union(merged, f.bbox)
    if len(members) <= MAX_FEATURES_PER_SHEET and fits_at(merged, map_mm, new_den):
        return [Acc([f.id for f in members], merged, scale=new_den)]
    return greedy_accs(members, scale_label(new_den), map_mm)


def _rescore_auto_sheets(accs, parcels, map_mm):
    """Turunkan skala lembar Auto yang gagal penilaian (v0.6.1).

    Tiap acc yang fill < AUTO_MIN_FILL atau median rasio label >
    AUTO_MAX_LABEL_RATIO diturunkan satu tingkat (OFFICIAL_SCALES ke
    bawah) dan persilnya dikelompokkan ulang pada skala baru via
    _regroup_at_scale (tetap bersama bila muat, greedy-split bila
    tidak); hasilnya dinilai lagi sampai lolos atau mencapai 1:250.
    Acc dengan < MIN_FEATURES_PER_SHEET bidang TIDAK dinilai: pada
    lembar kecil, kekosongan / kesesakan label adalah masalah JUMLAH
    bidang, bukan skala — merge_small_accs (yang jalan sesudah ini)
    yang mengurusnya. Tanpa pengecualian ini, lembar kecil yang gagal
    fill dipecah sampai 1:250 dan tidak bisa digabung lagi (frame
    1:250 terlalu kecil), sehingga jumlah lembar meledak.
    Mengembalikan daftar acc baru (lembar yang lolos / kecil tidak
    disentuh). Berhenti dijamin: tiap penggantian menurunkan skala,
    dan skala terbawah 1:250."""
    parcels_by_id = {p.id: p for p in parcels}
    pending = list(accs)
    result = []
    guard = 0
    while pending:
        guard += 1
        if guard > 10000:
            # Pengaman: tidak boleh loop selamanya (skala terbatas,
            # jadi ini tidak seharusnya tercapai).
            result.extend(pending)
            break
        acc = pending.pop(0)
        if len(acc.ids) < MIN_FEATURES_PER_SHEET:
            # Lembar kecil: bukan urusan penilaian skala (lihat di atas).
            result.append(acc)
            continue
        ok, _fill, _ratio = sheet_score_ok(acc, parcels_by_id, map_mm)
        if ok:
            result.append(acc)
            continue
        den = acc.scale if acc.scale else OFFICIAL_SCALES[-1]
        idx = (
            OFFICIAL_SCALES.index(den)
            if den in OFFICIAL_SCALES
            else len(OFFICIAL_SCALES) - 1
        )
        if idx <= 0:
            # Sudah di skala terkecil (1:250) — tidak bisa turun lagi.
            result.append(acc)
            continue
        new_den = OFFICIAL_SCALES[idx - 1]
        members = [parcels_by_id[i] for i in acc.ids if i in parcels_by_id]
        if not members:
            result.append(acc)
            continue
        pending.extend(_regroup_at_scale(members, new_den, map_mm))
    return result



# ---------------------------------------------------------------------------
# Pembagian lembar Auto per BLOK / wilayah (v0.6.2)
# ---------------------------------------------------------------------------
# Masalah v0.6.0-v0.6.1: persil dipilah ke tier skala PER PERSIL
# (parcel_max_denominator) SEBELUM dikelompokkan. Persil besar dan kecil
# yang bertetangga di satu blok jatuh ke tier berbeda, sehingga tiap
# tier membentuk lembar yang bentangannya menutupi seluruh area dan
# saling tumpang-tindih (uji PBT_2130: 13 lembar, hampir semua frame
# saling menimpa; tiap PDF hanya memuat persil "bolong-bolong" yang
# tersebar). Hasilnya tidak menyatu per blok dan terlihat tidak rapi.
#
# v0.6.2 membalik urutannya: WILAYAH DULU, SKALA KEMUDIAN.
#   1. Mulai dari satu unit (seluruh persil, atau tiap blok bila ada
#      pembagi jalan/irigasi — detect_blocks).
#   2. Untuk sebuah unit, skala lembar = skala resmi TERKECIL yang
#      frame-nya memuat bbox unit (fill terbaik). Unit diterima bila
#      <= MAX_FEATURES_PER_SHEET bidang dan lolos penilaian label
#      (median rasio label <= AUTO_MAX_LABEL_RATIO dan sebagian besar
#      label muat, lihat _auto_unit_ok).
#   3. Bila tidak diterima, unit DIPOTONG SECARA SPASIAL menjadi dua
#      bagian kompak (_split_unit_spatial: potong di celah/pemisah
#      terlebar dekat median, sehingga sedikit persil yang terbelah)
#      lalu tiap bagian diproses dengan aturan yang sama.
# Akibatnya tiap lembar adalah satu wilayah yang kompak, lembar yang
# bertetangga tidak saling menimpa, dan skala tiap lembar tetap
# menyesuaikan isinya (area persil kecil -> skala besar / zoom-in;
# area persil besar -> skala kecil). Skala tetap campuran antar
# lembar, tetapi TIDAK PERNAH dicampur di dalam satu wilayah.

AUTO_MIN_LABEL_FIT_FRACTION = 0.80
AUTO_SPLIT_MIN_SIDE_FRACTION = 0.25


def _bbox_of(members):
    box = members[0].bbox[:]
    for f in members[1:]:
        box = union(box, f.bbox)
    return box


def _smallest_fitting_scale(bbox, map_mm):
    """Skala resmi terkecil (penyebut terkecil) yang frame-nya memuat
    bbox; None bila bahkan 1:2500 tidak memuat."""
    for d in OFFICIAL_SCALES:
        if fits_at(bbox, map_mm, d):
            return d
    return None


def _auto_unit_ok(members, den, parcels_by_id=None):
    """Penilaian label sebuah unit pada skala `den` (lembar < 10 bidang
    tidak dinilai — urusan merge_small_accs, sama seperti v0.6.1)."""
    if len(members) < MIN_FEATURES_PER_SHEET:
        return True
    acc = Acc([f.id for f in members], _bbox_of(members), scale=den)
    by_id = {f.id: f for f in members}
    if sheet_label_ratio_median(acc, by_id) > AUTO_MAX_LABEL_RATIO:
        return False
    known = [f for f in members if f.label_len > 0]
    if known:
        fit = sum(1 for f in known if label_fits(f, den))
        if fit / float(len(known)) < AUTO_MIN_LABEL_FIT_FRACTION:
            return False
    return True


def _split_unit_spatial(members):
    """Potong unit jadi dua bagian kompak. Urut menurut pusat persil
    sepanjang sumbu terpanjang bbox; titik potong dipilih pada celah
    terlebar (jarak tepi bbox kiri-maks ke kanan-min) di rentang
    tengah, supaya persil yang terbelah sesedikit mungkin."""
    n = len(members)
    bbox = _bbox_of(members)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    axes = [0, 1] if width >= height else [1, 0]
    min_side = max(1, int(n * AUTO_SPLIT_MIN_SIDE_FRACTION))

    def best_cut(axis):
        ordered = sorted(
            members, key=lambda f: ((f.bbox[axis] + f.bbox[axis + 2]) / 2.0, f.id)
        )
        # prefix max tepi atas / suffix min tepi bawah sepanjang sumbu
        pre_max = []
        cur = -math.inf
        for f in ordered:
            cur = max(cur, f.bbox[axis + 2])
            pre_max.append(cur)
        suf_min = [0.0] * n
        cur = math.inf
        for i in range(n - 1, -1, -1):
            cur = min(cur, ordered[i].bbox[axis])
            suf_min[i] = cur
        best = None
        mid = n / 2.0
        for k in range(min_side, n - min_side + 1):
            if k <= 0 or k >= n:
                continue
            gap = suf_min[k] - pre_max[k - 1]
            key = (gap, -abs(k - mid))
            if best is None or key > best[0]:
                best = (key, k)
        if best is None:
            k = n // 2
            gap = suf_min[k] - pre_max[k - 1]
            best = ((gap, 0), k)
        return ordered, best[1], best[0][0]

    primary = best_cut(axes[0])
    chosen = primary
    if primary[2] < 0:
        secondary = best_cut(axes[1])
        if secondary[2] > 0:
            chosen = secondary
    ordered, k, _gap = chosen
    return ordered[:k], ordered[k:]


def _auto_partition_unit(members, map_mm, out):
    """Rekursif: terima unit sebagai satu lembar atau potong spasial."""
    stack = [members]
    guard = 0
    while stack:
        guard += 1
        if guard > 100000:
            # Pengaman: tidak boleh loop selamanya.
            for m in stack:
                out.append(Acc([f.id for f in m], _bbox_of(m), scale=OFFICIAL_SCALES[-1]))
            return
        cur = stack.pop()
        bbox = _bbox_of(cur)
        den = _smallest_fitting_scale(bbox, map_mm)
        if den is not None and len(cur) <= MAX_FEATURES_PER_SHEET and _auto_unit_ok(cur, den):
            out.append(Acc([f.id for f in cur], bbox, scale=den))
            continue
        if len(cur) <= 1:
            # Satu persil: tidak bisa dipotong lagi. Skala = yang
            # terkecil yang memuat; bila tidak ada, 1:2500 (peringatan
            # "lebih besar dari area peta" muncul di _build_groups).
            out.append(
                Acc([f.id for f in cur], bbox, scale=den if den else OFFICIAL_SCALES[-1])
            )
            continue
        left, right = _split_unit_spatial(cur)
        if not left or not right:
            out.append(
                Acc([f.id for f in cur], bbox, scale=den if den else OFFICIAL_SCALES[-1])
            )
            continue
        # LIFO: dorong kanan dulu supaya kiri diproses lebih awal.
        stack.append(right)
        stack.append(left)


# v0.6.3: pengaman "bidang loncat". Pemotongan spasial kadang membuat
# satu bidang tersangkut di lembar yang bidang lainnya jauh darinya,
# sehingga lembar jadi memanjang/bolong dan bidang itu tampak "loncat".
# Perbaikan: bidang yang menyendiri DIPINDAHKAN ke lembar tetangga yang
# menampungnya; bila tidak ada, dibiarkan (tidak membuat lembar 1 bidang
# baru). Terukur di PBT_2091: reattach memindahkan 16 bidang; di
# PBT_2130: 0 bidang (tidak ada yang memenuhi syarat pindah).
AUTO_ISOLATION_GAP_FRACTION = 0.08
AUTO_MERGE_MAX_GAP_FRACTION = 0.12


def _bbox_gap(a, b):
    """Jarak terdekat antara dua bbox (0 bila bersentuhan/tumpang)."""
    dx = max(0.0, max(b[0] - a[2], a[0] - b[2]))
    dy = max(0.0, max(b[1] - a[3], a[1] - b[3]))
    return math.hypot(dx, dy)


def _reattach_strays(accs, parcels_by_id, map_mm):
    """Pindahkan bidang yang menyendiri (jarak ke anggota terdekat di
    lembarnya > AUTO_ISOLATION_GAP_FRACTION x lebar frame di tanah) ke
    lembar tetangga terdekat yang: (a) muat satu bidang lagi
    (<= MAX_FEATURES_PER_SHEET), (b) bbox gabungannya muat pada skala
    lembar itu, (c) jaraknya <= batas isolasi lembar itu, dan (d) label
    bidang masih muat (skala lembar tujuan <= skala asal, atau
    label_fits). Bidang tanpa lembar tujuan dibiarkan di tempatnya.
    Mengembalikan daftar acc (objek Acc diperbarui di tempat)."""
    for _pass in range(8):
        moved = False
        for src in list(accs):
            if len(src.ids) < 2:
                continue
            src_den = src.scale if src.scale else OFFICIAL_SCALES[-1]
            limit = map_mm[0] / 1000.0 * src_den * AUTO_ISOLATION_GAP_FRACTION
            members = [parcels_by_id[i] for i in src.ids if i in parcels_by_id]
            strays = []
            for f in members:
                nearest = min(
                    _bbox_gap(f.bbox, o.bbox) for o in members if o is not f
                )
                if nearest > limit:
                    strays.append((nearest, f))
            if not strays:
                continue
            strays.sort(key=lambda t: -t[0])
            for _gap, f in strays:
                if len(src.ids) < 2:
                    break
                best = None
                for tgt in accs:
                    if tgt is src or len(tgt.ids) >= MAX_FEATURES_PER_SHEET:
                        continue
                    tden = tgt.scale if tgt.scale else OFFICIAL_SCALES[-1]
                    if not fits_at(union(tgt.bbox, f.bbox), map_mm, tden):
                        continue
                    if not (tden <= src_den or label_fits(f, tden)):
                        continue
                    tmem = [parcels_by_id[i] for i in tgt.ids if i in parcels_by_id]
                    if not tmem:
                        continue
                    g = min(_bbox_gap(f.bbox, o.bbox) for o in tmem)
                    if g > map_mm[0] / 1000.0 * tden * AUTO_ISOLATION_GAP_FRACTION:
                        continue
                    if g < _gap and (best is None or g < best[0]):
                        best = (g, tgt)
                if best is None:
                    continue
                tgt = best[1]
                src.ids.remove(f.id)
                tgt.ids.append(f.id)
                tgt.bbox = union(tgt.bbox, f.bbox)
                rest = [parcels_by_id[i] for i in src.ids if i in parcels_by_id]
                if rest:
                    src.bbox = _bbox_of(rest)
                moved = True
        if not moved:
            break
    return accs


def _auto_accs(parcels, dividers, map_mm):
    """Auto v0.6.2: wilayah dulu, skala kemudian. Mengembalikan Acc."""
    if dividers:
        units = detect_blocks(parcels, dividers)
    else:
        units = [list(parcels)]
    accs = []
    for unit in units:
        if unit:
            _auto_partition_unit(unit, map_mm, accs)
    return accs


def parcel_color_rgb(name):
    """Palet bernama — sama dengan parcel_color_rgb() di Rust.

    Warna core (v0.6.5, kode dari Derana 2026-11-26): Ungu FE01AE,
    Hijau 00FB00, Merah FD0000."""
    key = (name or "").strip().lower()
    table = {
        "putih": (255, 255, 255),
        "white": (255, 255, 255),
        "merah": (253, 0, 0),
        "red": (253, 0, 0),
        "ungu": (254, 1, 174),
        "magenta": (254, 1, 174),
        "purple": (254, 1, 174),
        "hijau": (0, 251, 0),
        "green": (0, 251, 0),
        "biru": (0, 112, 192),
        "blue": (0, 112, 192),
        "kuning": (255, 192, 0),
        "yellow": (255, 192, 0),
        "oranye": (255, 128, 0),
        "orange": (255, 128, 0),
        "hitam": (0, 0, 0),
        "black": (0, 0, 0),
        "abu gelap": (35, 35, 35),
        "abu-gelap": (35, 35, 35),
        "darkgray": (35, 35, 35),
        "dark-grey": (35, 35, 35),
        "darkgrey": (35, 35, 35),
    }
    return table.get(key, (0, 251, 0))  # hijau = default


def text_color_rgb(name):
    if not name:
        return (35, 35, 35)
    return parcel_color_rgb(name)


# ---------------------------------------------------------------------------
# Struktur data pengelompokan
# ---------------------------------------------------------------------------


class FeatureBox:
    """Satu fitur: id (pk sebagai string), bbox, cincin poligon, KET.

    label_len = panjang (karakter) baris label terpanjang (persil biasa
    NAMA / NIB / L=...m2; persil SHM NIB / No Hak) — dipakai mode Auto
    campuran v0.6.0 untuk menentukan skala terbesar yang labelnya
    masih muat. 0 = tidak diketahui (dianggap muat di semua skala).

    label_lines = jumlah baris label (v0.6.6): 3 untuk persil biasa,
    2 untuk persil SHM (NIB + No Hak). Dipakai label_fits untuk
    tinggi label. Default 3 (perilaku lama).

    lines = polylines TERBUKA (pembagi garis dari layer 'dividers',
    v0.6.4): daftar garis, tiap garis daftar titik (x, y). Dipakai
    detect_blocks lewat point_lines_dist (tanpa segmen penutup)."""

    __slots__ = ("id", "bbox", "rings", "ket", "label_len", "label_lines", "lines")

    def __init__(self, fid, bbox, rings, ket, label_len=0, lines=None,
                 label_lines=3):
        self.id = str(fid)
        self.bbox = list(bbox)
        self.rings = rings
        self.ket = ket
        self.label_len = int(label_len) if label_len else 0
        self.label_lines = int(label_lines) if label_lines else 3
        self.lines = [list(ln) for ln in lines] if lines else []

    def center(self):
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )


class Acc:
    __slots__ = ("ids", "bbox", "scale")

    def __init__(self, ids, bbox, scale=None):
        self.ids = list(ids)
        self.bbox = list(bbox)
        # scale = penyebut skala lembar ini (mis. 500.0). None = belum
        # ditentukan (diisi pemanggil dari skala tier / skala tetap).
        self.scale = scale


class SheetGroup:
    __slots__ = ("id", "feature_ids", "extent", "scale", "warnings")

    def __init__(self, gid, feature_ids, extent, scale, warnings):
        self.id = gid
        self.feature_ids = list(feature_ids)
        self.extent = list(extent)
        self.scale = scale
        self.warnings = list(warnings)


# ---------------------------------------------------------------------------
# Deteksi blok v17.7 (port langsung dari detect_blocks)
# ---------------------------------------------------------------------------


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def point_rings_contains(x, y, rings):
    return any(ring and point_in_ring(x, y, ring) for ring in rings)


def point_seg_dist(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(x - ax, y - ay)
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def point_lines_dist(x, y, lines):
    """Jarak terdekat ke polylines TERBUKA (tanpa segmen penutup).

    Berbeda dengan point_rings_dist yang menutup cincin (segmen
    terakhir -> titik pertama): garis pembagi (jalan/sungai dari layer
    dividers) tidak punya sisi penutup, jadi jarak dihitung hanya ke
    segmen yang benar-benar ada."""
    best = math.inf
    for line in lines:
        for i in range(len(line) - 1):
            ax, ay = line[i]
            bx, by = line[i + 1]
            d = point_seg_dist(x, y, ax, ay, bx, by)
            if d < best:
                best = d
    return best


def point_rings_dist(x, y, rings):
    best = math.inf
    for ring in rings:
        n = len(ring)
        for i in range(n):
            ax, ay = ring[i]
            bx, by = ring[(i + 1) % n]
            d = point_seg_dist(x, y, ax, ay, bx, by)
            if d < best:
                best = d
    return best


def detect_blocks(parcels, dividers):
    if not parcels:
        return []
    total = parcels[0].bbox[:]
    for p in parcels[1:]:
        total = union(total, p.bbox)
    cell = BLOCK_CELL_M

    def dims(c):
        return (
            max(1, int(math.ceil((total[2] - total[0]) / c))),
            max(1, int(math.ceil((total[3] - total[1]) / c))),
        )

    nx, ny = dims(cell)
    while nx * ny > 1_000_000:
        cell *= 2.0
        nx, ny = dims(cell)

    def cell_center(ix, iy):
        return (
            total[0] + (ix + 0.5) * cell,
            total[1] + (iy + 0.5) * cell,
        )

    def cell_range(bb, pad):
        ix0 = int(max(0, min(nx - 1, math.floor((bb[0] - pad - total[0]) / cell))))
        iy0 = int(max(0, min(ny - 1, math.floor((bb[1] - pad - total[1]) / cell))))
        ix1 = int(max(0, min(nx - 1, math.floor((bb[2] + pad - total[0]) / cell))))
        iy1 = int(max(0, min(ny - 1, math.floor((bb[3] + pad - total[1]) / cell))))
        return (ix0, iy0, ix1, iy1)

    land = [False] * (nx * ny)
    for p in parcels:
        ix0, iy0, ix1, iy1 = cell_range(p.bbox, 0.0)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                idx = iy * nx + ix
                if not land[idx]:
                    cx, cy = cell_center(ix, iy)
                    if point_rings_contains(cx, cy, p.rings):
                        land[idx] = True

    blocked = [False] * (nx * ny)
    for d in dividers:
        ix0, iy0, ix1, iy1 = cell_range(d.bbox, BLOCK_BUFFER_M)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                idx = iy * nx + ix
                if not blocked[idx]:
                    cx, cy = cell_center(ix, iy)
                    if point_rings_contains(cx, cy, d.rings) or point_rings_dist(
                        cx, cy, d.rings
                    ) <= BLOCK_BUFFER_M or point_lines_dist(
                        cx, cy, d.lines
                    ) <= BLOCK_BUFFER_M:
                        blocked[idx] = True

    comp = [-1] * (nx * ny)
    ncomp = 0
    queue = deque()
    for start in range(nx * ny):
        if not land[start] or blocked[start] or comp[start] != -1:
            continue
        queue.append(start)
        comp[start] = ncomp
        while queue:
            c = queue.popleft()
            cx, cy = c % nx, c // nx
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxx, nyy = cx + dx, cy + dy
                if 0 <= nxx < nx and 0 <= nyy < ny:
                    n = nyy * nx + nxx
                    if land[n] and not blocked[n] and comp[n] == -1:
                        comp[n] = ncomp
                        queue.append(n)
        ncomp += 1

    blocks = []
    block_of = [None] * max(0, ncomp)
    for p in parcels:
        cx, cy = p.center()
        ix = int(max(0, min(nx - 1, math.floor((cx - total[0]) / cell))))
        iy = int(max(0, min(ny - 1, math.floor((cy - total[1]) / cell))))
        found = comp[iy * nx + ix] if comp[iy * nx + ix] != -1 else None
        if found is None:
            for r in range(1, 12):
                done = False
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if max(abs(dx), abs(dy)) != r:
                            continue
                        jx, jy = ix + dx, iy + dy
                        if 0 <= jx < nx and 0 <= jy < ny and comp[jy * nx + jx] != -1:
                            found = comp[jy * nx + jx]
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
        if found is not None:
            if block_of[found] is None:
                blocks.append([])
                block_of[found] = len(blocks) - 1
            blocks[block_of[found]].append(p)
        else:
            blocks.append([p])
    return blocks


# ---------------------------------------------------------------------------
# Greedy + min-10 merge (port langsung)
# ---------------------------------------------------------------------------


def greedy_accs(features, requested_scale, map_mm):
    den = parse_scale(requested_scale)
    if den is None:
        den = 1000.0
    accs = []
    for feature in features:
        best = None  # (index, growth)
        for index, acc in enumerate(accs):
            if len(acc.ids) >= MAX_FEATURES_PER_SHEET:
                continue
            merged = union(acc.bbox, feature.bbox)
            if not pick_scale(requested_scale, merged, map_mm)[1]:
                continue
            growth = area(merged) - area(acc.bbox)
            if best is None or growth < best[1]:
                best = (index, growth)
        if best is not None:
            index, _ = best
            accs[index].bbox = union(accs[index].bbox, feature.bbox)
            accs[index].ids.append(feature.id)
        else:
            accs.append(Acc([feature.id], feature.bbox, scale=den))
    return accs


def merge_small_accs(accs, map_mm, denominator, max_gap_fraction=None):
    """Gabung lembar kecil (< MIN_FEATURES_PER_SHEET) ke tetangga terdekat.

    Scale-aware (v0.6.0): dua lembar boleh gabung hanya bila bbox gabungan
    muat pada skala min(D_A, D_B) — skala hasil gabungan = min itu,
    sehingga label semua persil tetap muat (min ≤ D_max tiap persil).
    Bila acc.scale None, dipakai `denominator` (jalur skala eksplisit lama,
    semua lembar satu skala — perilaku tidak berubah)."""
    def center(bbox):
        return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)

    def dist(a, b):
        ax, ay = center(a)
        bx, by = center(b)
        return math.hypot(ax - bx, ay - by)

    work = list(accs)
    unmergeable = []
    while True:
        small = None
        for i, acc in enumerate(work):
            if len(acc.ids) < MIN_FEATURES_PER_SHEET and i not in unmergeable:
                key = (len(acc.ids), area(acc.bbox), i)
                if small is None or key < small[0]:
                    small = (key, i)
        if small is None:
            break
        i = small[1]
        cands = [j for j in range(len(work)) if j != i]
        cands.sort(key=lambda j: (dist(work[i].bbox, work[j].bbox), j))
        merged = False
        for j in cands:
            n = len(work[i].ids) + len(work[j].ids)
            bbox = union(work[i].bbox, work[j].bbox)
            den = min(
                work[i].scale if work[i].scale else denominator,
                work[j].scale if work[j].scale else denominator,
            )
            if max_gap_fraction is not None:
                # v0.6.3 (Auto): jangan melompati celah lebar.
                limit = map_mm[0] / 1000.0 * den * max_gap_fraction
                if _bbox_gap(work[i].bbox, work[j].bbox) > limit:
                    continue
            if n <= MAX_FEATURES_PER_SHEET and fits_at(bbox, map_mm, den):
                ids = work[i].ids + work[j].ids
                work[j] = Acc(ids, bbox, scale=den)
                del work[i]
                unmergeable = [u - 1 if u > i else u for u in unmergeable]
                merged = True
                break
        if not merged:
            unmergeable.append(i)
    leftover = []
    for u in unmergeable:
        ids = sorted(work[u].ids)
        leftover.append(ids)
    return (work, leftover)


# ---------------------------------------------------------------------------
# Pembagian lembar (port group_feature_boxes)
# ---------------------------------------------------------------------------


def _accs_at_scale(parcels, dividers, denominator, map_mm):
    """Grid/detect_blocks + greedy pada SATU skala. Mengembalikan daftar Acc
    (masing-masing .scale = denominator). Tanpa merge kecil — merge
    dilakukan pemanggil (merge_small_accs)."""
    win_w = map_mm[0] / 1000.0 * denominator * FILL_RATIO
    win_h = map_mm[1] / 1000.0 * denominator * FILL_RATIO
    total = parcels[0].bbox[:]
    for p in parcels[1:]:
        total = union(total, p.bbox)
    total_w = max(0.0, total[2] - total[0])
    total_h = max(0.0, total[3] - total[1])

    if not dividers:
        nx = max(1, int(math.ceil(total_w / win_w))) if win_w > 0 else 1
        ny = max(1, int(math.ceil(total_h / win_h))) if win_h > 0 else 1
        cell_w = total_w / nx if total_w > 0 else 1.0
        cell_h = total_h / ny if total_h > 0 else 1.0
        grid = [[] for _ in range(nx * ny)]
        for feature in parcels:
            cx, cy = feature.center()
            col = min(int(math.floor((cx - total[0]) / cell_w)), nx - 1)
            row = min(int(math.floor((total[3] - cy) / cell_h)), ny - 1)
            grid[row * nx + col].append(feature)
        cells = grid
    else:
        cells = detect_blocks(parcels, dividers)

    fixed_scale = scale_label(denominator)
    accs = []
    for cell in cells:
        if not cell:
            continue
        merged = cell[0].bbox[:]
        for f in cell[1:]:
            merged = union(merged, f.bbox)
        if len(cell) <= MAX_FEATURES_PER_SHEET and fits_at(merged, map_mm, denominator):
            accs.append(Acc([f.id for f in cell], merged, scale=denominator))
        else:
            accs.extend(greedy_accs(cell, fixed_scale, map_mm))
    return accs


def _build_groups(accs, small_leftovers, map_mm, label_warnings):
    """Acc -> SheetGroup. Tiap lembar memakai skalanya sendiri (acc.scale);
    label_warnings = {id_persil: pesan} ditempel ke lembar pemiliknya."""
    accs.sort(key=lambda a: (-((a.bbox[1] + a.bbox[3]) / 2.0), (a.bbox[0] + a.bbox[2]) / 2.0))

    width = max(2, len(str(max(1, len(accs)))))
    groups = []
    for index, acc in enumerate(accs):
        denominator = acc.scale if acc.scale else 1000.0
        fixed_scale = scale_label(denominator)
        ok = fits_at(acc.bbox, map_mm, denominator)
        warnings = []
        if not ok:
            warnings.append(
                "Bidang {} lebih besar dari area peta pada skala {}; "
                "sebagian akan terpotong.".format(", ".join(acc.ids), fixed_scale)
            )
        mine = sorted(acc.ids)
        if any(ids == mine for ids in small_leftovers):
            warnings.append(
                "Lembar ini hanya memuat {} bidang (di bawah minimum {}); "
                "tidak ada lembar tetangga yang bisa digabung tanpa melampaui "
                "frame {}.".format(len(acc.ids), MIN_FEATURES_PER_SHEET, fixed_scale)
            )
        for pid in acc.ids:
            if pid in label_warnings:
                warnings.append(label_warnings[pid])
        center = ((acc.bbox[0] + acc.bbox[2]) / 2.0, (acc.bbox[1] + acc.bbox[3]) / 2.0)
        groups.append(
            SheetGroup(
                "L{:0{w}d}".format(index + 1, w=width),
                acc.ids,
                layout_extent(center, denominator, map_mm),
                fixed_scale,
                warnings,
            )
        )
    return groups


def group_feature_boxes(features, requested_scale, map_mm):
    """Bagi fitur jadi lembar.

    Skala eksplisit (1:250..1:2500): SATU skala untuk semua lembar,
    sama persis seperti v0.5.9.

    Auto (v0.6.0, campuran): tiap persil masuk tier menurut skala
    TERBESAR yang labelnya masih muat (parcel_max_denominator); tiap
    tier dikelompokkan pada skalanya sendiri; merge_small_accs yang
    scale-aware lalu boleh menggabung lembar kecil antar-tier (skala
    hasil = min). Tiap lembar mendapat skalanya sendiri.

    Auto (v0.6.2, wilayah dulu): unit (seluruh persil, atau tiap blok
    bila ada pembagi jalan/irigasi) dipotong secara spasial menjadi
    wilayah kompak; tiap lembar memakai skala resmi terkecil yang
    memuat wilayahnya dan lolos penilaian label (_auto_accs). Skala
    campuran antar lembar, tidak pernah di dalam satu wilayah.
    (Tier per persil v0.6.0 dan _rescore_auto_sheets v0.6.1 tidak
    lagi dipakai oleh jalur Auto.)"""
    err = validate_requested_scale(requested_scale)
    if err:
        raise ValueError(err)
    features = sorted(
        features,
        key=lambda f: (-f.center()[1], f.center()[0], f.id),
    )
    parcels = [f for f in features if not (is_special_ket(f.ket) and (f.rings or f.lines))]
    dividers = [f for f in features if is_special_ket(f.ket) and (f.rings or f.lines)]
    if not parcels:
        raise ValueError("Tidak ada fitur untuk dikelompokkan.")
    if requested_scale == "Auto":
        # v0.6.2: wilayah dulu, skala kemudian (lihat _auto_accs).
        # Peringatan label per persil (label tidak muat bahkan di
        # 1:250) tetap dihitung dari parcel_max_denominator.
        label_warnings = {}
        for p in parcels:
            _d, warn = parcel_max_denominator(p)
            if warn:
                label_warnings[p.id] = warn
        accs = _auto_accs(parcels, dividers, map_mm)
        # v0.6.3: bidang yang menyendiri dipindah ke lembar tetangga.
        accs = _reattach_strays(accs, {p.id: p for p in parcels}, map_mm)
        # merge_small_accs scale-aware: lembar < 10 bidang digabung ke
        # tetangga terdekat bila bbox gabungan muat pada skala min
        # (tidak melompati celah lebar — lihat max_gap_fraction).
        accs, small_leftovers = merge_small_accs(
            accs, map_mm, OFFICIAL_SCALES[-1],
            max_gap_fraction=AUTO_MERGE_MAX_GAP_FRACTION,
        )
        return _build_groups(accs, small_leftovers, map_mm, label_warnings)
    denominator = parse_scale(requested_scale) or 1000.0
    accs = _accs_at_scale(parcels, dividers, denominator, map_mm)
    accs, small_leftovers = merge_small_accs(accs, map_mm, denominator)
    return _build_groups(accs, small_leftovers, map_mm, {})

# ---------------------------------------------------------------------------
# Bagian PyQGIS (import malas — modul tetap bisa di-import tanpa QGIS
# untuk menguji grouping murni)
# ---------------------------------------------------------------------------


def _qgis_enum(*candidates, fallback=None):
    """Ambil nilai enum dari beberapa kandidat "Root.Dotted.Path".

    QGIS 4 memindahkan enum label dari QgsPalLayerSettings ke namespace
    Qgis (LabelPlacement, LabelMultiLineAlignment, LabelQuadrantPosition,
    ...), dan PyQt6 menolak nilai enum yang salah tipe. Di QGIS 4.2,
    akses datar ("OverPoint") mengembalikan anggota enum yang salah —
    render gagal: "a member of enum 'LabelPlacement' is expected not
    'LabelPredefinedPointPosition'". Karena itu jalur Qgis.* (QGIS 4)
    dicoba DULU, baru jalur QgsPalLayerSettings.* (QGIS 3).
    QGIS 3.22 (sandbox) tidak punya Qgis.LabelPlacement — jalur itu
    gagal diam-diam lalu jalur QGIS 3 yang dipakai.
    """
    from qgis.core import Qgis, QgsPalLayerSettings

    roots = {"Qgis": Qgis, "QgsPalLayerSettings": QgsPalLayerSettings}
    for cand in candidates:
        root_name, _, rest = cand.partition(".")
        root = roots.get(root_name)
        if root is None or not rest:
            continue
        try:
            obj = root
            for part in rest.split("."):
                obj = getattr(obj, part)
            return obj
        except AttributeError:  # nosec B112  # kandidat berikut dicoba
            continue
    return fallback


def _qgis_color(rgb):
    from qgis.PyQt.QtGui import QColor

    return QColor(rgb[0], rgb[1], rgb[2], 255)


def _rgb_hex(rgb):
    """(r, g, b) -> '#RRGGBB' (huruf besar) — untuk ekspresi warna
    data-defined QGIS (label Color menerima string hex)."""
    return "#{:02X}{:02X}{:02X}".format(
        int(rgb[0]), int(rgb[1]), int(rgb[2]))


def shm_label_color_expression(fields, shm_rgb, text_rgb):
    """Ekspresi warna label data-defined (v0.7.3, murni — tanpa QGIS).

    Persil SHM (field 080203 terisi, Nomor Hak) memakai warna "Warna
    SHM" (shm_rgb — sama dengan warna garis SHM), persil biasa memakai
    warna "Warna teks" (text_rgb). Mengembalikan None bila field 080203
    tidak ada ATAU shm_rgb None — pemanggil lalu memakai warna dasar
    fmt.setColor(text_rgb) untuk semua label (perilaku lama).
    Kondisi SHM sama dengan cabang SHM di label_expression
    (coalesce 080203 != '')."""
    if shm_rgb is None:
        return None
    hak = next((f for f in fields if f.lower() == "080203"), None)
    if not hak:
        return None
    return (
        "CASE WHEN coalesce(\"{}\", '') != '' "
        "THEN '{}' ELSE '{}' END"
    ).format(hak, _rgb_hex(shm_rgb), _rgb_hex(text_rgb))


def ket_ilike_expr(ket_field, keywords):
    k = 'coalesce("{}", \'\')'.format(ket_field)
    return " OR ".join("{} ILIKE '%{}%'".format(k, w) for w in keywords)


# trim_expression DIHAPUS di v0.6.7: geometry generator untuk pembagi
# poligon sudah tidak dipakai — trim pembagi kini di Python
# (_trimmed_divider_layers), supaya jalur PDF dan Preview/.qgs sama.


def label_expression(fields):
    """Ekspresi label — sama persis dengan default_labeling Rust.

    Persil biasa: NAMA / NIB (080201) / L=...m2 (3 baris; fitur
    spesial jalan/sungai hanya NAMA). Persil SHM (v0.6.6, keputusan
    Derana 2026-11-26: "untuk Persil SHM hanya perlu NIB dan No
    Haknya saja"): hanya NIB + No Hak (080203), 2 baris — tanpa NAMA,
    tanpa LUAS, tanpa No SU. array_filter membuang baris kosong."""
    by_lower = {f.lower(): f for f in fields}

    def find(wanted):
        return by_lower.get(wanted.lower())

    special = None
    ket = find("KET")
    if ket:
        special = "({}) OR ({})".format(
            ket_ilike_expr(ket, ROAD_WORDS), ket_ilike_expr(ket, WATER_WORDS)
        )
    # Baris persil biasa: NAMA / NIB / L=...m2.
    lines = []
    nama = find("NAMA")
    if nama:
        lines.append('coalesce("{}", \'\')'.format(nama))
    nib = find("080201")
    if nib:
        if special:
            lines.append(
                'case when {} then \'\' else coalesce("{}", \'\') end'.format(
                    special, nib
                )
            )
        else:
            lines.append('coalesce("{}", \'\')'.format(nib))
    area_field, is_luas = (None, False)
    if find("M2"):
        area_field, is_luas = find("M2"), False
    elif find("LUAS"):
        area_field, is_luas = find("LUAS"), True
    if area_field:
        guard = "when {} then '' ".format(special) if special else ""
        f = '"{}"'.format(area_field)
        if is_luas:
            lines.append(
                "case {}when {} is null or {} = '' then '' when left({}, 2) = 'L=' "
                "then {} else concat('L=', {}, 'm2') end".format(
                    guard, f, f, f, f, f
                )
            )
        else:
            lines.append(
                "case {}when {} is null or {} = '' then '' else "
                "concat('L=', {}, 'm2') end".format(guard, f, f, f)
            )
    ordinary = None
    if lines:
        ordinary = "array_to_string(array_filter(array({}), @element != ''), '\\n')".format(
            ", ".join(lines)
        )
    # Persil SHM (v0.6.6): hanya NIB + No Hak (080203).
    hak = find("080203")
    if hak:
        shm_lines = []
        if nib:
            shm_lines.append('coalesce("{}", \'\')'.format(nib))
        shm_lines.append('coalesce("{}", \'\')'.format(hak))
        shm = "array_to_string(array_filter(array({}), @element != ''), '\\n')".format(
            ", ".join(shm_lines)
        )
        if ordinary:
            return "case when coalesce(\"{}\", '') != '' then {} else {} end".format(
                hak, shm, ordinary
            )
        return shm
    return ordinary


def _style_kwargs(opts):
    """Kwargs gaya dari opts panel (v0.6.4): lebar garis per jenis,
    warna SHM, buffer teks. Default = perilaku lama."""
    try:
        parcel_w = float(opts.get("parcel_width_mm") or 0.5)
    except (TypeError, ValueError):
        parcel_w = 0.5
    try:
        road_w = float(opts.get("road_width_mm") or 0.5)
    except (TypeError, ValueError):
        road_w = 0.5
    try:
        water_w = float(opts.get("water_width_mm") or 0.5)
    except (TypeError, ValueError):
        water_w = 0.5
    try:
        shm_w = float(opts.get("shm_width_mm") or 0.5)
    except (TypeError, ValueError):
        shm_w = 0.5
    shm_color = opts.get("shm_color")
    return {
        "parcel_width_mm": parcel_w,
        "road_width_mm": road_w,
        "water_width_mm": water_w,
        "shm_rgb": parcel_color_rgb(shm_color) if shm_color else None,
        "shm_width_mm": shm_w,
        "text_buffer": bool(opts.get("text_buffer", False)),
    }


def apply_parcel_style(layer, outline_rgb, text_rgb, fields, denominator,
                       parcel_width_mm=0.5, road_width_mm=0.5,
                       water_width_mm=0.5, shm_rgb=None, shm_width_mm=0.5,
                       text_buffer=False):
    """Terapkan renderer aturan + labeling ke QgsVectorLayer (port
    build_project_xml: rule_renderer_polygon + default_labeling).

    v0.6.4: lebar garis per jenis (persil/jalan/sungai/SHM), rule SHM
    (field 080203 terisi -> warna SHM + lebar SHM, sebelum rule ELSE),
    dan buffer teks (halo putih 0,5 mm) bila text_buffer True. Semua
    kwarg baru punya default = perilaku lama, jadi pemanggil lama
    (termasuk test) tidak berubah.

    v0.6.7: rule jalan/sungai (geometry generator) dihapus dari sini —
    pembagi poligon digambar dari layer memori _trimmed_divider_layers
    (cincin dibuka jadi garis terbuka). road_width_mm/water_width_mm
    kini hanya diteruskan ke layer pembagi itu; di sini tidak dipakai
    lagi (dipertahankan di signature supaya pemanggil lama tetap jalan)."""
    from qgis.core import (
        QgsFillSymbol,
        QgsPalLayerSettings,
        QgsProperty,
        QgsRuleBasedRenderer,
        QgsSimpleFillSymbolLayer,
        QgsSingleSymbolRenderer,
        QgsSymbol,
        QgsVectorLayerSimpleLabeling,
    )

    geom_type = layer.geometryType()
    # Bentuk enum scoped (QGIS 4 / Qt6) — nilai sama di QGIS 3.22
    # (teruji: GeometryType.PolygonGeometry == 2, RenderUnit.RenderPoints
    # == 4 di kedua versi). Bentuk datar (QgsWkbTypes.PolygonGeometry)
    # ditolak pemindai kompatibilitas Qt6 plugins.qgis.org.
    is_polygon = geom_type == 2
    ket_field = next((f for f in fields if f.lower() == "ket"), None)

    if is_polygon and ket_field:
        # v0.6.7: rule jalan/sungai (geometry generator) DIHAPUS —
        # pembagi poligon kini digambar dari layer memori hasil
        # _trimmed_divider_layers (cincin dibuka jadi garis terbuka),
        # supaya jalur PDF dan Preview/.qgs konsisten. Persil spesial
        # tidak lagi masuk subset layer ini, jadi rule ELSE di bawah
        # tidak pernah melihatnya.
        def parcel_symbol(rgb, width_mm):
            return QgsFillSymbol.createSimple(
                {
                    "color": "255,255,255,0",
                    "outline_color": "{},{},{},255".format(*rgb),
                    "outline_width": str(width_mm),
                    "outline_width_unit": "MM",
                    "outline_style": "solid",
                }
            )

        renderer = QgsRuleBasedRenderer(QgsFillSymbol())
        root = renderer.rootRule()
        # Konstruktor QgsRuleBasedRenderer() menyisipkan satu rule default
        # (isi biru 0,0,255, filter kosong = cocok SEMUA fitur) sebagai anak
        # pertama root — itu yang membuat semua persil terisi biru di render
        # PoC pertama. Hapus rule default itu; yang dipakai hanya 3 rule
        # di bawah. (Root sendiri tidak punya simbol.)
        if root.children():
            root.removeChildAt(0)

        def make_rule(symbol, filter_exp, label):
            # Konstruktor Rule(symbol, filter, label) tidak stabil antar
            # versi sip — pakai konstruktor 1-arg + setter (ada di 3.x/4.x).
            rule = QgsRuleBasedRenderer.Rule(symbol)
            rule.setFilterExpression(filter_exp)
            rule.setLabel(label)
            return rule

        # (Rule jalan/sungai geometry-generator dihapus di v0.6.7 —
        # pembagi digambar dari layer memori _trimmed_divider_layers.)
        # SHM (v0.6.4): field 080203 terisi (Nomor Hak M.00xxx) ->
        # warna + lebar SHM sendiri. Rule ini SEBELUM rule ELSE, jadi
        # persil SHM tidak ikut rule ELSE (ELSE = tidak cocok rule lain).
        shm_field = next((f for f in fields if f.lower() == "080203"), None)
        if shm_rgb is not None and shm_field:
            shm_filter = '"{}" IS NOT NULL AND "{}" <> \'\''.format(shm_field, shm_field)
            root.appendChild(
                make_rule(parcel_symbol(shm_rgb, shm_width_mm), shm_filter, "SHM")
            )
        else_rule = QgsRuleBasedRenderer.Rule(parcel_symbol(outline_rgb, parcel_width_mm))
        else_rule.setLabel("Bidang Tanah")
        # Jadikan rule ELSE: di QGIS 3.22 tidak ada setElse() —
        # setFilterExpression("ELSE") adalah cara kanonisnya (sama seperti
        # yang tertulis di XML: filter="ELSE").
        else_rule.setFilterExpression("ELSE")
        root.appendChild(else_rule)
        layer.setRenderer(renderer)
    else:
        # Tanpa KET tidak ada rule jalan/sungai; bila ada field SHM dan
        # warna SHM diminta, pakai 2 rule (SHM + ELSE) supaya SHM tetap
        # beda warna — kalau tidak, satu simbol dengan lebar persil.
        shm_field = next((f for f in fields if f.lower() == "080203"), None)
        if is_polygon and shm_rgb is not None and shm_field:
            renderer = QgsRuleBasedRenderer(QgsFillSymbol())
            root = renderer.rootRule()
            if root.children():
                root.removeChildAt(0)

            def make_rule2(symbol, filter_exp, label):
                rule = QgsRuleBasedRenderer.Rule(symbol)
                rule.setFilterExpression(filter_exp)
                rule.setLabel(label)
                return rule

            def parcel_symbol2(rgb, width_mm):
                return QgsFillSymbol.createSimple(
                    {
                        "color": "255,255,255,0",
                        "outline_color": "{},{},{},255".format(*rgb),
                        "outline_width": str(width_mm),
                        "outline_width_unit": "MM",
                        "outline_style": "solid",
                    }
                )

            shm_filter = '"{}" IS NOT NULL AND "{}" <> \'\''.format(shm_field, shm_field)
            root.appendChild(make_rule2(parcel_symbol2(shm_rgb, shm_width_mm), shm_filter, "SHM"))
            else_rule = QgsRuleBasedRenderer.Rule(parcel_symbol2(outline_rgb, parcel_width_mm))
            else_rule.setFilterExpression("ELSE")
            else_rule.setLabel("Bidang Tanah")
            root.appendChild(else_rule)
            layer.setRenderer(renderer)
        else:
            symbol = QgsFillSymbol.createSimple(
                {
                    "color": "255,255,255,0",
                    "outline_color": "{},{},{},255".format(*outline_rgb),
                    "outline_width": str(parcel_width_mm),
                    "outline_width_unit": "MM",
                    "outline_style": "solid",
                }
            )
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    if is_polygon:
        expr = label_expression(fields)
        if expr:
            settings = QgsPalLayerSettings()
            settings.fieldName = expr
            settings.isExpression = True
            # Format teks lewat QgsTextFormat (setFormat) — v0.4.1.
            # Di QGIS 3, QgsPalLayerSettings TIDAK lagi punya anggota
            # C++ fontSize/textColor/fontFamily/fontSizeUnit (pindah ke
            # QgsTextFormat); menulis settings.fontSize = ... dsb. hanya
            # membuat atribut Python yang hilang saat settings disalin
            # ke labeling, sehingga label selama ini dirender dengan
            # format default (10 pt, Liberation Sans, #323232) — DUA KALI
            # lebih besar dari yang dirancang (5 pt di 1:500) dan itulah
            # penyebab utama label bertabrakan. Dibuktikan probe
            # probe_format2.py di sandbox 3.22.
            size = label_font_size_pt(denominator)
            try:
                from qgis.core import QgsTextFormat, QgsUnitTypes
                from qgis.PyQt.QtGui import QFont

                fmt = QgsTextFormat()
                fmt.setFont(QFont("Arial", size))
                fmt.setSize(size)
                fmt.setSizeUnit(QgsUnitTypes.RenderUnit.RenderPoints)
                fmt.setColor(_qgis_color(text_rgb))
                # Buffer teks (v0.6.4, ukuran 0,5 mm sejak v0.7.1):
                # halo putih 0,5 mm di sekeliling semua baris label,
                # bila opsi panel menyala. Default mati = perilaku lama
                # (tanpa buffer).
                if text_buffer:
                    try:
                        from qgis.core import QgsTextBufferSettings

                        buf = QgsTextBufferSettings()
                        buf.setEnabled(True)
                        buf.setSize(0.5)
                        buf.setSizeUnit(QgsUnitTypes.RenderUnit.RenderMillimeters)
                        buf.setColor(_qgis_color((255, 255, 255)))
                        fmt.setBuffer(buf)
                    except Exception:  # nosec B110  # best-effort
                        pass
                settings.setFormat(fmt)
            except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
                pass
            # QGIS 4: Qgis.LabelPlacement.OverPoint (placement di
            # QgsPalLayerSettings bertipe Qgis::LabelPlacement). QGIS 3:
            # QgsPalLayerSettings.Placement.OverPoint / datar. OverPoint = 1
            # di kedua versi (AroundPoint = 0).
            placement = _qgis_enum(
                "Qgis.LabelPlacement.OverPoint",
                "QgsPalLayerSettings.LabelPlacement.OverPoint",
                "QgsPalLayerSettings.Placement.OverPoint",
                "QgsPalLayerSettings.OverPoint",
                fallback=1,
            )
            if placement is not None:
                settings.placement = placement
            if hasattr(settings, "centroidInside"):
                settings.centroidInside = True
            # QGIS 4: Qgis.LabelQuadrantPosition.Over (pusat; "QuadrantCenter"
            # hanya ada di QGIS 3). quadOffset masih ada di QGIS 4,
            # quadrantOffset tidak (guard hasattr di bawah).
            quad = _qgis_enum(
                "Qgis.LabelQuadrantPosition.Over",
                "QgsPalLayerSettings.LabelQuadrantPosition.Over",
                "QgsPalLayerSettings.QuadrantPosition.QuadrantCenter",
                "QgsPalLayerSettings.QuadrantCenter",
                fallback=4,
            )
            if quad is not None:
                if hasattr(settings, "quadrantOffset"):
                    settings.quadrantOffset = quad
                elif hasattr(settings, "quadOffset"):
                    settings.quadOffset = quad
            # QGIS 4: Qgis.LabelMultiLineAlignment.Center (Left = 0,
            # Center = 1 — sama seperti MultiCenter di QGIS 3).
            multi = _qgis_enum(
                "Qgis.LabelMultiLineAlignment.Center",
                "QgsPalLayerSettings.LabelMultiLineAlignment.Center",
                "QgsPalLayerSettings.MultiLineAlign.MultiCenter",
                "QgsPalLayerSettings.MultiCenter",
                fallback=1,
            )
            if multi is not None:
                settings.multilineAlign = multi
            if hasattr(settings, "displayAll"):
                settings.displayAll = True
            if hasattr(settings, "obstacle"):
                settings.obstacle = True
            # obstacleType tidak ada di QgsPalLayerSettings QGIS 4
            # (pindah ke obstacleSettings()) — guard hasattr, dan nilai
            # enum hanya dicari bila atributnya memang ada, supaya jalur
            # datar QGIS 4 tidak sempat mengembalikan anggota enum salah.
            if hasattr(settings, "obstacleType"):
                obstacle = _qgis_enum(
                    "Qgis.LabelObstacleType.PolygonBoundary",
                    "QgsPalLayerSettings.LabelObstacleType.PolygonBoundary",
                    "QgsPalLayerSettings.ObstacleType.PolygonBoundary",
                    "QgsPalLayerSettings.PolygonBoundary",
                    fallback=1,
                )
                if obstacle is not None:
                    settings.obstacleType = obstacle
            if hasattr(settings, "drawLabels"):
                settings.drawLabels = True
            # Data-defined Size v17.11: nama panjang -> font mengecil.
            nama = next((f for f in fields if f.lower() == "nama"), None)
            if nama:
                # Data-defined Size v17.11 — jalur bersarang dulu (QGIS 4:
                # Property adalah enum class; akses datar bisa salah tipe).
                size_key = _qgis_enum(
                    "QgsPalLayerSettings.Property.Size",
                    "QgsPalLayerSettings.Size",
                    fallback=None,
                )
                if size_key is not None:
                    # v0.4.1: pakai max(), BUKAN greatest(). greatest()/least()
                    # tidak ada di QGIS 3.22 ("Function is not known") sehingga
                    # ekspresi ini gagal parse dan nama panjang tidak pernah
                    # mengecil (fallback ke ukuran format) — itulah sebabnya
                    # UJANG NURMAN ALAMSAH (20 karakter) tetap 5 pt dan
                    # meluber. max()/min() ada sejak QGIS 2.x, aman di
                    # 3.22 maupun 4.2.2.
                    # v0.4.2: lantai ukuran nama panjang naik dari 3 pt
                    # menjadi 4 pt (permintaan Derana, 2026-11-20 23:27
                    # WIB). Nama > 12 karakter mengecil proporsional
                    # (12/panjang * ukuran), tidak lebih kecil dari 4 pt.
                    dd = (
                        'CASE WHEN length("{f}") > 12 THEN max(12.0 / '
                        'length("{f}") * {s}, 4) ELSE {s} END'
                    ).format(f=nama, s=size)
                    # QGIS 3.22: tidak ada setDataDefinedProperty (tunggal) —
                    # pola resminya: ambil koleksi, set, kembalikan.
                    props = settings.dataDefinedProperties()
                    props.setProperty(size_key, QgsProperty.fromExpression(dd))
                    settings.setDataDefinedProperties(props)
            # Warna label data-defined (v0.7.3): persil SHM memakai warna
            # "Warna SHM" (shm_rgb — sama dengan warna garis SHM), persil
            # biasa memakai warna "Warna teks" (text_rgb). Tanpa ini semua
            # label satu warna tetap — laporan Derana 2026-11-27: teks SHM
            # tetap putih saat "Warna teks" = Putih (supaya terbaca di
            # varian CITRA/foto). Pola setProperty sama seperti
            # data-defined Size di atas (koleksi -> set -> kembalikan).
            # Guard: hanya bila field 080203 ada DAN shm_rgb diberikan
            # (shm_label_color_expression -> None bila tidak); bila
            # tidak, semua label pakai text_rgb seperti sebelumnya —
            # fmt.setColor(text_rgb) di atas tetap sebagai warna
            # dasar/fallback.
            color_expr = shm_label_color_expression(fields, shm_rgb, text_rgb)
            if color_expr is not None:
                try:
                    color_key = _qgis_enum(
                        "QgsPalLayerSettings.Property.Color",
                        "QgsPalLayerSettings.Color",
                        fallback=None,
                    )
                    if color_key is not None:
                        props = settings.dataDefinedProperties()
                        props.setProperty(
                            color_key, QgsProperty.fromExpression(color_expr)
                        )
                        settings.setDataDefinedProperties(props)
                except Exception:  # nosec B110  # best-effort
                    pass
            # Rotasi label (v0.4.1, DICOBA lalu DIBATALKAN): properti
            # data-defined Rotation (main_angle, mengikuti sumbu panjang
            # persil) terpasang dan berevaluasi benar, TAPI diabaikan
            # total saat render di sandbox QGIS 3.22 — bahkan rotasi
            # konstan 45 derajat tidak mengubah satu piksel pun (uji
            # canvas-rot-45 vs canvas-rot-0 identik). Arah putar di
            # QGIS 4.2.2 tidak bisa diverifikasi dari sini, jadi rotasi
            # tidak dipakai: pada 5 pt + dd Size yang benar, tabrakan
            # sudah hilang tanpa rotasi. Jangan tambah lagi tanpa bukti
            # render di 4.2.2.
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def _as_multipolygon(geom):
    """Kembalikan geometri sebagai MultiPolygon (atau None).

    intersection() pembagi dengan buffer bisa menghasilkan Polygon,
    MultiPolygon, atau GeometryCollection — layer memori pembagi bertipe
    MultiPolygon, jadi semua bagian poligon disatukan ke bentuk itu."""
    from qgis.core import QgsGeometry, QgsWkbTypes

    if geom is None or geom.isEmpty():
        return None
    if geom.wkbType() == QgsWkbTypes.Type.Polygon:
        return QgsGeometry.fromMultiPolygonXY([geom.asPolygon()])
    if geom.wkbType() == QgsWkbTypes.Type.MultiPolygon:
        return QgsGeometry(geom)
    if geom.wkbType() == QgsWkbTypes.Type.GeometryCollection:
        polys = []
        for part in geom.asGeometryCollection():
            if part.wkbType() == QgsWkbTypes.Type.Polygon:
                polys.append(part.asPolygon())
            elif part.wkbType() == QgsWkbTypes.Type.MultiPolygon:
                polys.extend(part.asMultiPolygon())
        if not polys:
            return None
        return QgsGeometry.fromMultiPolygonXY(polys)
    return None


def _as_multilinestring(geom):
    """Kembalikan geometri sebagai MultiLineString (atau None).

    intersection() pembagi garis dengan buffer bisa menghasilkan
    LineString, MultiLineString, atau GeometryCollection — layer
    memori pembagi garis bertipe MultiLineString, jadi semua bagian
    garis disatukan ke bentuk itu."""
    from qgis.core import QgsGeometry, QgsWkbTypes

    if geom is None or geom.isEmpty():
        return None
    if geom.wkbType() == QgsWkbTypes.Type.LineString:
        return QgsGeometry.fromMultiPolylineXY([geom.asPolyline()])
    if geom.wkbType() == QgsWkbTypes.Type.MultiLineString:
        return QgsGeometry(geom)
    if geom.wkbType() == QgsWkbTypes.Type.GeometryCollection:
        lines = []
        for part in geom.asGeometryCollection():
            if part.wkbType() == QgsWkbTypes.Type.LineString:
                lines.append(part.asPolyline())
            elif part.wkbType() == QgsWkbTypes.Type.MultiLineString:
                lines.extend(part.asMultiPolyline())
        if not lines:
            return None
        return QgsGeometry.fromMultiPolylineXY(lines)
    return None


def _apply_divider_style(layer, road_width_mm=0.5, water_width_mm=0.5):
    """Renderer aturan POLOS untuk layer pembagi (tanpa geometry generator).

    Warna sama dengan apply_parcel_style (jalan oranye #FF3F00, air
    biru #003FFF, outline 0,5 mm, isi transparan) — hanya saja tanpa
    trim_expression, karena geometri di layer ini SUDAH di-trim di Python
    (lihat _trimmed_divider_layers). Lebar outline mengikuti opsi panel
    (v0.6.4)."""
    from qgis.core import QgsFillSymbol, QgsRuleBasedRenderer

    road = ket_ilike_expr("KET", ROAD_WORDS)
    water = ket_ilike_expr("KET", WATER_WORDS)

    def sym(rgb, width_mm):
        return QgsFillSymbol.createSimple(
            {
                "color": "255,255,255,0",
                "outline_color": "{},{},{},255".format(*rgb),
                "outline_width": str(width_mm),
                "outline_width_unit": "MM",
                "outline_style": "solid",
            }
        )

    renderer = QgsRuleBasedRenderer(QgsFillSymbol())
    root = renderer.rootRule()
    if root.children():
        root.removeChildAt(0)

    def rule(symbol, filter_exp, label):
        r = QgsRuleBasedRenderer.Rule(symbol)
        r.setFilterExpression(filter_exp)
        r.setLabel(label)
        return r

    root.appendChild(rule(sym((255, 63, 0), road_width_mm), road, "Jalan / Gang"))
    root.appendChild(rule(sym((0, 63, 255), water_width_mm), water, "Sungai / Irigasi / Saluran"))
    layer.setRenderer(renderer)


def _apply_divider_line_style(layer, road_width_mm=0.5, water_width_mm=0.5):
    """Renderer aturan GARIS untuk layer pembagi garis (v0.6.4, tanpa
    geometry generator — geometri SUDAH di-trim di Python).

    Jalan oranye #FF3F00, air biru #003FFF, lebar dari opsi panel."""
    from qgis.core import QgsLineSymbol, QgsRuleBasedRenderer

    road = ket_ilike_expr("KET", ROAD_WORDS)
    water = ket_ilike_expr("KET", WATER_WORDS)

    def sym(rgb, width_mm):
        return QgsLineSymbol.createSimple(
            {
                "color": "{},{},{},255".format(*rgb),
                "width": str(width_mm),
                "width_unit": "MM",
            }
        )

    renderer = QgsRuleBasedRenderer(QgsLineSymbol())
    root = renderer.rootRule()
    if root.children():
        root.removeChildAt(0)

    def rule(symbol, filter_exp, label):
        r = QgsRuleBasedRenderer.Rule(symbol)
        r.setFilterExpression(filter_exp)
        r.setLabel(label)
        return r

    root.appendChild(rule(sym((255, 63, 0), road_width_mm), road, "Jalan / Gang"))
    root.appendChild(rule(sym((0, 63, 255), water_width_mm), water, "Sungai / Irigasi / Saluran"))
    layer.setRenderer(renderer)


def _open_ring(pts):
    """Buka satu cincin tertutup (jalan/sungai poligon) jadi 2 garis
    terbuka, dengan membuang 2 segmen 'tutup ujung' (cap).

    Cincin jalan/sungai adalah strip panjang-tipis: 2 sisi panjang +
    2 tutup pendek di ujungnya (yang ditandai X oleh Derana di
    screenshot 2026-11-26). Tutup = 2 segmen terpendek yang TIDAK
    bersebelahan, masing-masing < 20% keliling cincin, DAN berbelok
    tajam (> 30 derajat) di kedua ujungnya — syarat belok ini
    membedakan tutup dari jog pendek di tengah sisi (yang lurus,
    belok ~0 derajat). Bila tidak ada 2 segmen yang memenuhi (bukan
    strip — mis. persimpangan jalan yang hampir persegi), kembalikan
    None: cincin tetap tertutup (perilaku lama). `pts` = daftar
    (x, y), titik pertama == terakhir (toleransi 1e-6 m).

    v0.7.4 (loop buntu, Derana 2026-11-27: "garis tutup seperti itu
    kan logikanya jalan/gang tersebut di tutup di lapangan"): strip
    yang MELIPAT (jalan buntu / gang buntu) punya hairpin — belokan
    tajam di tengah strip dengan segmen jog yang sangat pendek. Kriteria
    "terpendek + belok tajam" salah memilih jog hairpin itu sebagai
    tutup, sehingga loop putus di tengah jalan (bukan di ujung).
    Pengaman: bila satu garis hasil bukaan jauh lebih pendek dari
    yang lain (< 1/3), bukaan itu salah — cincin tetap tertutup
    supaya loop buntu utuh. Strip lurus (2 sisi panjang sebanding,
    mis. JALAN fid 16: 113 m vs 287 m) tetap dibuka seperti v0.6.7.
    Mengembalikan [polyline, polyline] atau None."""
    if len(pts) < 5:
        return None
    if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > 1e-6:
        return None
    ring = pts[:-1]
    n = len(ring)
    if n < 4:
        return None
    seg_len = []
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        seg_len.append(math.hypot(b[0] - a[0], b[1] - a[1]))
    perim = sum(seg_len)
    if perim <= 0:
        return None

    def turn_deg(j):
        # Sudut belok di titik ring[j] (derajat): 0 = lurus, 90 = siku.
        a = ring[(j - 1) % n]
        b = ring[j]
        c = ring[(j + 1) % n]
        ux, uy = b[0] - a[0], b[1] - a[1]
        vx, vy = c[0] - b[0], c[1] - b[1]
        lu = math.hypot(ux, uy)
        lv = math.hypot(vx, vy)
        if lu == 0 or lv == 0:
            return 0.0
        cosang = (ux * vx + uy * vy) / (lu * lv)
        cosang = max(-1.0, min(1.0, cosang))
        return math.degrees(math.acos(cosang))

    turns = [turn_deg(j) for j in range(n)]
    # Kandidat tutup: pendek + belok tajam di kedua ujung.
    candidates = [
        i for i in range(n)
        if seg_len[i] < 0.20 * perim
        and turns[i] > 30.0
        and turns[(i + 1) % n] > 30.0
    ]
    if len(candidates) < 2:
        return None
    candidates.sort(key=lambda i: seg_len[i])
    cap1 = candidates[0]

    def adjacent(i, j):
        return abs(i - j) == 1 or {i, j} == {0, n - 1}

    cap2 = None
    for j in candidates[1:]:
        if not adjacent(cap1, j):
            cap2 = j
            break
    if cap2 is None:
        return None
    caps = {cap1, cap2}
    lines = []
    cur = None
    for i in range(n):
        if i in caps:
            if cur is not None:
                lines.append(cur)
                cur = None
            continue
        a = ring[i]
        b = ring[(i + 1) % n]
        if cur is None:
            cur = [a, b]
        else:
            cur.append(b)
    if cur is not None:
        lines.append(cur)
    # Rantai pertama + terakhir menyambung lewat titik awal cincin
    # (cincin itu melingkar) — gabung bila ujungnya bertemu.
    if len(lines) >= 2 and lines[-1][-1] == lines[0][0]:
        lines = [lines[-1] + lines[0][1:]] + lines[1:-1]
    lines = [ln for ln in lines if len(ln) >= 2]
    if len(lines) == 2:
        # v0.7.4: pengaman loop buntu — bila satu garis hasil bukaan
        # jauh lebih pendek dari yang lain (< 1/3), cap yang dibuang
        # bukan tutup ujung melainkan jog hairpin; kembalikan None
        # (cincin tetap tertutup, loop utuh).
        def _plen(ln):
            return sum(math.hypot(ln[i + 1][0] - ln[i][0],
                                  ln[i + 1][1] - ln[i][1])
                       for i in range(len(ln) - 1))
        l0, l1 = _plen(lines[0]), _plen(lines[1])
        if l0 > 0 and l1 > 0 and min(l0, l1) < (1.0 / 3.0) * max(l0, l1):
            return None
    return lines if len(lines) == 2 else None


def _pt_seg_dist(px, py, ax, ay, bx, by):
    """Jarak titik (px, py) ke segmen ab (m)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _seg_intersect(a, b, c, d):
    """Apakah segmen ab memotong segmen cd (termasuk bersentuhan)?"""

    def orient(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if abs(v) < 1e-12:
            return 0
        return 1 if v > 0 else -1

    def on_seg(p, q, r):
        return (min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
                and min(p[1], r[1]) - 1e-9 <= q[1]
                <= max(p[1], r[1]) + 1e-9)

    o1, o2, o3, o4 = (orient(a, b, c), orient(a, b, d),
                      orient(c, d, a), orient(c, d, b))
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_seg(a, c, b):
        return True
    if o2 == 0 and on_seg(a, d, b):
        return True
    if o3 == 0 and on_seg(c, a, d):
        return True
    if o4 == 0 and on_seg(c, b, d):
        return True
    return False


def _seg_seg_dist(a, b, c, d):
    """Jarak minimum antara segmen ab dan cd (m); 0 bila bersentuhan."""
    if _seg_intersect(a, b, c, d):
        return 0.0
    return min(
        _pt_seg_dist(a[0], a[1], c[0], c[1], d[0], d[1]),
        _pt_seg_dist(b[0], b[1], c[0], c[1], d[0], d[1]),
        _pt_seg_dist(c[0], c[1], a[0], a[1], b[0], b[1]),
        _pt_seg_dist(d[0], d[1], a[0], a[1], b[0], b[1]),
    )


def _rings_min_dist(rings_a, rings_b):
    """Jarak minimum antara dua daftar cincin (m); 0 bila bersentuhan."""
    best = math.inf
    for ra in rings_a:
        for rb in rings_b:
            for i in range(len(ra) - 1):
                for j in range(len(rb) - 1):
                    dd = _seg_seg_dist(ra[i], ra[i + 1],
                                       rb[j], rb[j + 1])
                    if dd < best:
                        best = dd
                        if best <= 0.0:
                            return 0.0
    return best


def _group_touching_divider_polys(items, tol):
    """Kelompokkan potongan pembagi poligon yang saling bersentuhan.

    v0.7.5 (sambung potongan jalan, Derana 2026-11-27): persil jalan/
    sungai yang dipotong pendek-pendek saat disetorkan terpisah-pisah
    di GPKG. Potongan yang KET-nya sama DAN bersentuhan (jarak cincin
    <= tol) adalah satu jalan yang nyambung — gabung jadi satu grup
    (transitif: A menyentuh B, B menyentuh C -> satu grup). Potongan
    yang tidak menyentuh potongan se-KET lain (ujung mentok beneran)
    tetap sendiri. Dua jalan paralel terpisah (jarak > tol) tidak
    digabung, begitu pula KET berbeda (jalan vs sungai di persimpangan).

    `items` = list (key, ket_norm, rings); rings = daftar cincin,
    tiap cincin daftar titik (x, y). Mengembalikan daftar grup
    (daftar key), diurutkan deterministik. Murni (tanpa QGIS)."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if items[i][1] != items[j][1]:
                continue
            if _rings_min_dist(items[i][2], items[j][2]) <= tol:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i][0])
    return sorted(groups.values(), key=lambda g: (len(g), g))


def _merge_touching_divider_polys(dividers, geom_by_pk):
    """Gabung (union) potongan pembagi poligon se-KET yang bersentuhan.

    v0.7.5: dipanggil di awal _trimmed_divider_layers, SEBELUM
    _open_ring + trim. Tiap grup sentuhan (lihat
    _group_touching_divider_polys, ambang MERGE_TOL_M) di-union jadi
    satu geometri — tepi bersama antar potongan hilang dari union,
    jadi garis potongan di sambungan tidak ikut kegambar dan jalan
    kelihatan nyambung. _open_ring + trim lalu diterapkan ke geometri
    gabungan (pengaman keseimbangan v0.7.4 + toleransi trim tetap
    berlaku). Pembagi GARIS (layer dividers) tidak digabung (sudah
    berupa garis, bukan potongan poligon) dan dikembalikan apa adanya.

    Mengembalikan (dividers_baru, geom_by_pk_baru): potongan yang
    tergabung diganti satu FeatureBox sintetik id
    "merged:<ket>:<fid1>+<fid2>..." dengan bbox geometri gabungan;
    geometri gabungan dititipkan di geom_by_pk_baru dengan id itu.
    Bila union gagal (combine mengembalikan null/kosong), grup itu
    jatuh kembali ke potongan masing-masing (perilaku lama).
    Butuh QGIS (QgsGeometry.combine)."""
    poly_items = []  # (key, ket_norm, ket_asli, rings, geom)
    kept = []
    for d in dividers:
        if d.lines:
            kept.append(d)
            continue
        g = geom_by_pk.get(d.id)
        if g is None:
            kept.append(d)
            continue
        polys = g.asMultiPolygon() if g.isMultipart() else [g.asPolygon()]
        rings = [[(p.x(), p.y()) for p in ring]
                 for poly in polys for ring in poly]
        if not rings:
            kept.append(d)
            continue
        poly_items.append((d.id, str(d.ket).strip().upper(), d.ket,
                           rings, g))
    by_key = {it[0]: it for it in poly_items}
    new_geoms = dict(geom_by_pk)
    out = list(kept)
    for keys in _group_touching_divider_polys(
            [(k, kn, r) for (k, kn, _ka, r, _g) in poly_items],
            MERGE_TOL_M):
        members = [by_key[k] for k in keys]
        if len(members) == 1:
            out.append(next(d for d in dividers if d.id == keys[0]))
            continue
        ket = members[0][2]
        merged = members[0][4]
        ok = True
        for m in members[1:]:
            c = merged.combine(m[4])
            if c is None or c.isNull() or c.isEmpty():
                ok = False
                break
            merged = c
        if not ok:
            for m in members:
                out.append(next(d for d in dividers if d.id == m[0]))
            continue
        bb = merged.boundingBox()
        bbox = [bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum()]
        polys = (merged.asMultiPolygon() if merged.isMultipart()
                 else [merged.asPolygon()])
        rings = [[(p.x(), p.y()) for p in ring]
                 for poly in polys for ring in poly]
        mid = "merged:{}:{}".format(
            members[0][1], "+".join(sorted(keys)))
        out.append(FeatureBox(mid, bbox, rings, ket))
        new_geoms[mid] = merged
    return out, new_geoms


def _trimmed_divider_layers(dividers, group, geom_by_pk, crs, layer_name,
                            road_width_mm=0.5, water_width_mm=0.5):
    """Bangun layer memori pembagi lembar ini, SUDAH di-trim di Python.

    Akar masalah (v0.6.3, Preview): trim_expression memakai
    aggregate(@layer_id, 'collect', ...) — aggregate itu hanya bisa
    menemukan layer yang terdaftar di QgsProject.instance(). Di jalur
    _build_qgs_project (Preview + .qgs) layer lembar tinggal di proyek
    terpisah (out_project, bukan instance), sehingga aggregate
    mengembalikan NULL ("Cannot find layer with name or ID") dan
    geometry generator tidak menggambar apa pun: 0 piksel oranye/biru
    di 16/16 PNG Preview v0.6.1+v0.6.3, padahal jalur PDF render_batch
    (layer di instance()) menggambar jalan normal. Di sini trim
    dilakukan di Python dengan semantik yang sama persis:
    intersection(geom pembagi, buffer(collect(geom persil lembar),
    TRIM_BUFFER_M)) — pembagi yang tidak menyentuh persil lembar tetap
    dibuang, yang terlalu panjang tetap dipangkas. Pembagi yang
    bbox-nya tidak memotong frame lembar tidak masuk (aturan subset
    yang sama seperti sebelumnya).

    v0.6.4: pembagi GARIS (layer dividers) ikut di-trim di sini dan
    dikembalikan sebagai layer MultiLineString terpisah — pembagi
    poligon tetap MultiPolygon. Mengembalikan daftar layer memori
    (0-2 lapis). Lebar garis mengikuti opsi panel.

    v0.6.5: pembagi GARIS di-clip ke FRAME lembar (group.extent),
    BUKAN ke buffer 5 m persil. Buffer 5 m memotong garis yang
    berjalan > 5 m dari persil — jalan/sungai keluar sebagai potongan
    pendek yang putus di tengah peta (dilaporkan Derana 2026-11-26:
    "garis jalan atau selokan tidak utuh di Preview"). Frame adalah
    area yang terlihat di peta, jadi garis utuh di dalam lembar dan
    terpotong rapi di tepi frame. Pembagi POLIGON tetap memakai buffer
    5 m (poligon punya isi — tanpa trim ia bisa menutupi peta).

    v0.6.7: pembagi yang berbentuk POLIGON (jalan/sungai strip)
    DIBUKA jadi garis terbuka — 2 segmen 'tutup ujung' (cap) di
    ujung strip dibuang via _open_ring, jadi yang tergambar hanya
    2 sisi panjangnya (permintaan Derana 2026-11-26, yang ditandai X
    di screenshot). Berlaku untuk pembagi garis yang cincinnya
    tertutup (Boundary poligon dari converter) maupun pembagi poligon
    di layer utama. Poligon yang bukan strip (tidak bisa dibuka)
    tetap digambar tertutup (perilaku lama).

    v0.6.8 (koreksi atas v0.6.7, atas perintah Derana 2026-11-26:
    "aku ingin tetap terpotong 5 m dari persil"): garis hasil bukaan
    poligon di-trim ke BUFFER 5 m persil lembar, BUKAN ke frame.
    v0.6.7 salah kaprah meng-clip-nya ke frame (seperti pembagi
    garis) — akibatnya jalan/sungai tampil utuh sepanjang lembar.
    Pembagi garis (converter) tetap di-clip ke frame (keputusan
    v0.6.5, tidak berubah). Jadi v0.6.8 = tutup ujung dibuang +
    tetap terpotong 5 m, persis seperti v0.6.6 minus tutupnya.

    v0.6.9 (atas screenshot Derana 2026-11-26, X di dekat SITI
    SA'ADAH 00870): garis hasil bukaan poligon di-trim ke cincin
    5 m TANPA persil (buffer 5 m minus persil lembar), bukan ke
    buffer penuh. Terbukti di sandbox: tepi jalan yang hampir
    berimpit dengan batas persil menyilang batas itu di beberapa
    titik (JALAN 117, JALAN 6, IRIGASI 75 vs persil 79) — X itu
    bukan tutup, melainkan persilangan garis jalan/batas persil.
    Dengan trim ke cincin tanpa persil, garis berhenti di batas
    persil dan tidak menyilangnya. Pembagi garis (converter) dan
    fallback poligon tertutup tidak berubah.

    v0.7.4 (loop buntu, Derana 2026-11-27): trim v0.6.9 memotong garis
    di TIAP sentuhan sudut persil — tepi jalan yang berjalan tepat di
    batas persil (offset digitasi beberapa cm) terpotong jadi fragmen
    pendek (4-6 potong dalam cakram r=5 m di titik yang dilingkari),
    sehingga loop buntu putus di sudut persil. Perbaikan: persil
    dikecilkan TRIM_TOL_M (0,20 m) saat menghitung `keep`, jadi garis
    yang menyentuh/masuk persil sedalam <= 0,20 m tetap utuh; garis
    yang masuk persil lebih dalam tetap terpotong (X-crossing v0.6.9
    tetap dicegah). Aturan 5 m + tanpa-X tidak berubah.

    v0.7.5 (sambung potongan jalan, Derana 2026-11-27: "persil jalan
    itu terlalu panjang, jadi dipotong-potong, garis itu adalah garis
    potongan untuk memperpendek persil" + "jalan itu seharusnya terbuka
    dan nyambung, kecuali memang ... yang benar-benar mentok"): jalan/
    sungai dijadikan persil saat disetorkan; karena terlalu panjang,
    dibuat pendek-pendek, sehingga di GPKG persil jalan TERPISAH-PISAH
    dan garis potongan antar potongan ikut kegambar — jalan kelihatan
    DITUTUP. Perbaikan: potongan pembagi poligon yang KET-nya SAMA dan
    BERSENTUHAN di-union dulu (lihat _merge_touching_divider_polys,
    ambang MERGE_TOL_M) jadi satu jalan utuh SEBELUM _open_ring + trim;
    tepi bersama antar potongan hilang dari union, jadi tidak ada garis
    di sambungannya. Aturan bedakan mentok vs kepotong (disepakati
    Derana): ujung potongan bersentuhan sama potongan jalan lain = satu
    jalan yang nyambung; ujung tidak bersentuhan sama apa-apa = mentok
    beneran (tetap sendiri, lalu _open_ring + pengaman v0.7.4 yang
    menentukan tertutup/terbuka). Dua jalan paralel terpisah (KET sama
    tapi jarak > MERGE_TOL_M) dan KET berbeda (jalan vs sungai di
    persimpangan) TIDAK digabung."""

    from qgis.core import (
        QgsFeature, QgsGeometry, QgsPointXY, QgsRectangle, QgsVectorLayer,
    )

    def bboxes_intersect(a, b):
        return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]

    parcel_geoms = [
        geom_by_pk[i] for i in group.feature_ids if i in geom_by_pk
    ]
    buf = None
    keep = None
    if parcel_geoms:
        collect = QgsGeometry.collectGeometry(parcel_geoms)
        buf = collect.buffer(TRIM_BUFFER_M, 8)
        # keep = cincin 5 m di sekitar persil, TIDAK termasuk persil
        # (v0.6.9): garis pembagi tidak boleh memotong batas persil.
        # v0.7.4: persil dikecilkan TRIM_TOL_M dulu — tepi jalan yang
        # berjalan tepat di batas persil (offset digitasi) tidak ikut
        # terpotong di tiap sudut persil; loop buntu tetap utuh.
        shrunk = collect.buffer(-TRIM_TOL_M, 8)
        if shrunk is None or shrunk.isNull() or shrunk.isEmpty():
            shrunk = collect
        keep = buf.difference(shrunk)
    frame_geom = QgsGeometry.fromRect(QgsRectangle(*group.extent))
    poly_feats = []
    line_feats = []
    # v0.7.5: gabung potongan pembagi poligon se-KET yang bersentuhan
    # (persil jalan/sungai yang dipotong pendek-pendek saat disetorkan
    # terpisah-pisah di GPKG; garis potongan antar potongan ikut kegambar
    # sehingga jalan kelihatan ditutup). Union dulu, baru _open_ring +
    # trim ke geometri gabungan — sambungan hilang, jalan nyambung.
    # Hanya KET sama + bersentuhan (<= MERGE_TOL_M); dua jalan paralel
    # terpisah tidak digabung; ujung mentok tetap sendiri.
    dividers, geom_by_pk = _merge_touching_divider_polys(
        dividers, geom_by_pk)
    for d in dividers:
        if not bboxes_intersect(d.bbox, group.extent):
            continue
        g = geom_by_pk.get(d.id)
        if g is None:
            continue
        if d.lines:
            # Garis: buka cincin tertutup dulu (v0.6.7 — poligon
            # jalan/sungai dari layer dividers), lalu clip ke frame
            # (utuh di dalam lembar).
            parts = (
                g.asMultiPolyline()
                if g.isMultipart()
                else [g.asPolyline()]
            )
            opened = []
            for part in parts:
                pts = [(p.x(), p.y()) for p in part]
                res = _open_ring(pts)
                if res:
                    opened.extend(res)
                else:
                    opened.append(pts)
            ml_geom = QgsGeometry.fromMultiPolylineXY(
                [[QgsPointXY(x, y) for x, y in ln] for ln in opened]
            )
            trimmed = ml_geom.intersection(frame_geom)
            if trimmed is None or trimmed.isEmpty():
                continue
            ml = _as_multilinestring(trimmed)
            if ml is None:
                continue
            f = QgsFeature()
            f.setGeometry(ml)
            f.setAttributes([d.ket])
            line_feats.append(f)
        else:
            # Poligon: coba buka cincinnya jadi garis terbuka (v0.6.7).
            # Bila bukan strip (tidak bisa dibuka), pakai perilaku lama
            # (trim ke buffer 5 m persil, tetap poligon). Garis hasil
            # bukaan di-trim ke cincin 5 m TANPA persil (v0.6.9 — Derana
            # minta X persilangan garis jalan/batas persil juga hilang):
            # garis tidak boleh memotong batas persil.
            polys = (
                g.asMultiPolygon()
                if g.isMultipart()
                else [g.asPolygon()]
            )
            opened = []
            closed = []
            for poly in polys:
                if len(poly) == 1:
                    pts = [(p.x(), p.y()) for p in poly[0]]
                    res = _open_ring(pts)
                    if res:
                        opened.extend(res)
                        continue
                closed.append(poly)
            if opened and keep is not None:
                ml_geom = QgsGeometry.fromMultiPolylineXY(
                    [[QgsPointXY(x, y) for x, y in ln] for ln in opened]
                )
                trimmed = ml_geom.intersection(keep)
                if trimmed is not None and not trimmed.isEmpty():
                    ml = _as_multilinestring(trimmed)
                    if ml is not None:
                        f = QgsFeature()
                        f.setGeometry(ml)
                        f.setAttributes([d.ket])
                        line_feats.append(f)
            if closed:
                # v0.7.4: cincin yang tidak dibuka (loop buntu — jalan/
                # gang buntu) digambar sebagai GARIS TERTUTUP, bukan
                # poligon isi. Ring-nya di-trim ke `keep` (cincin 5 m
                # tanpa persil, toleransi TRIM_TOL_M) persis seperti
                # garis hasil bukaan: loop tetap utuh, tapi tidak
                # memotong batas persil (aturan v0.6.9 tetap berlaku).
                # (Jalur lama: poligon isi di-trim ke buf — outline-nya
                # bisa menyilang persil karena buf mencakup persil, dan
                # QgsGeometry.fromMultiPolygon tidak ada di QGIS 3.22.)
                if keep is None:
                    continue
                ring_lines = []
                for poly in closed:
                    for ring_pts in poly:
                        pts = [(p.x(), p.y()) for p in ring_pts]
                        if len(pts) >= 2:
                            ring_lines.append(pts)
                if not ring_lines:
                    continue
                ml_geom = QgsGeometry.fromMultiPolylineXY(
                    [[QgsPointXY(x, y) for x, y in ln]
                     for ln in ring_lines]
                )
                trimmed = ml_geom.intersection(keep)
                if trimmed is None or trimmed.isEmpty():
                    continue
                ml = _as_multilinestring(trimmed)
                if ml is None:
                    continue
                f = QgsFeature()
                f.setGeometry(ml)
                f.setAttributes([d.ket])
                line_feats.append(f)
    layers = []
    if poly_feats:
        uri = "MultiPolygon?crs={}&field=KET:string".format(crs.authid())
        layer = QgsVectorLayer(uri, "{}_div".format(layer_name), "memory")
        if layer.isValid():
            layer.dataProvider().addFeatures(poly_feats)
            layer.updateExtents()
            _apply_divider_style(layer, road_width_mm, water_width_mm)
            layers.append(layer)
    if line_feats:
        uri = "MultiLineString?crs={}&field=KET:string".format(crs.authid())
        layer = QgsVectorLayer(uri, "{}_divln".format(layer_name), "memory")
        if layer.isValid():
            layer.dataProvider().addFeatures(line_feats)
            layer.updateExtents()
            _apply_divider_line_style(layer, road_width_mm, water_width_mm)
            layers.append(layer)
    return layers


def read_feature_boxes(layer, pk_col):
    """Baca fitur layer jadi FeatureBox (port load_feature_boxes).

    label_len per fitur dihitung dari baris label yang sama dengan
    label_expression() (persil biasa NAMA / NIB / L=...m2; persil SHM
    NIB / No Hak; fitur spesial hanya NAMA) — dipakai mode Auto
    campuran v0.6.0. Jumlah baris label juga dicatat (label_lines,
    v0.6.6) untuk tinggi label."""
    from qgis.core import QgsWkbTypes

    fields = [f.name() for f in layer.fields()]
    ket_field = next((f for f in fields if f.lower() == "ket"), None)
    by_lower = {f.lower(): f for f in fields}
    nama_field = by_lower.get("nama")
    nib_field = by_lower.get("080201")
    hak_field = by_lower.get("080203")
    area_field = by_lower.get("m2") or by_lower.get("luas")
    area_is_luas = area_field is not None and area_field.lower() == "luas"

    def label_len_of(feature, ket):
        """(panjang baris terpanjang, jumlah baris label) — barisnya
        sama dengan label_expression() (v0.6.6): persil SHM hanya
        NIB + No Hak (2 baris); persil biasa NAMA / NIB / L=...m2
        (3 baris). Jumlah baris biasa minimal 3 (perilaku lama)
        supaya persil biasa dan fitur spesial tidak berubah
        penilaiannya."""
        def val(name):
            if name is None:
                return ""
            v = feature.attribute(name)
            return "" if v is None else str(v)

        nama = val(nama_field)
        if is_special_ket(ket):
            return len(nama), 3
        nib = val(nib_field)
        hak = val(hak_field)
        if hak:
            # SHM (v0.6.6): hanya NIB + No Hak.
            n_lines = sum(1 for s in (nib, hak) if s)
            return (max(len(nib), len(hak)), max(1, n_lines))
        raw = val(area_field)
        if not raw:
            luas_line = ""
        elif area_is_luas and raw[:2] == "L=":
            luas_line = raw
        else:
            luas_line = "L={}m2".format(raw)
        n_lines = sum(
            1 for s in (nama, nib, luas_line) if s
        )
        return (
            max(len(nama), len(nib), len(luas_line)),
            max(3, n_lines),
        )

    boxes = []
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        rings = []
        if geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry:
            polys = (
                geom.asMultiPolygon()
                if geom.isMultipart()
                else [geom.asPolygon()]
            )
            for poly in polys:
                for ring in poly:
                    rings.append([(p.x(), p.y()) for p in ring])
        bbox = geom.boundingBox()
        ket = None
        if ket_field:
            value = feature.attribute(ket_field)
            ket = str(value) if value is not None else None
        if pk_col:
            fid = feature.attribute(pk_col)
        else:
            fid = feature.id()
        ll, nl = label_len_of(feature, ket)
        boxes.append(
            FeatureBox(
                fid,
                [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum()],
                rings,
                ket,
                label_len=ll,
                label_lines=nl,
            )
        )
    return boxes, fields


DIVIDER_LAYER_NAME = "dividers"


def read_line_dividers(gpkg_path):
    """Baca pembagi GARIS dari layer 'dividers' di GPKG yang sama.

    Layer ini ditulis converter DWG/DXF -> GPKG v0.3.5 (jalan/gang/
    sungai/selokan sebagai LINESTRING terbuka, field KET + Layer).
    Mengembalikan (boxes, geoms): boxes = FeatureBox dengan lines
    (id 'div:<pk>', rings kosong), geoms = {id: QgsGeometry} untuk
    trim di Python (_trimmed_divider_layers). ([], {}) bila layer
    tidak ada / kosong / tidak berisi garis pembagi."""
    from qgis.core import QgsVectorLayer, QgsWkbTypes

    boxes = []
    geoms = {}
    layer = QgsVectorLayer(
        "{}|layername={}".format(gpkg_path, DIVIDER_LAYER_NAME),
        DIVIDER_LAYER_NAME,
        "ogr",
    )
    if not layer.isValid():
        return boxes, geoms
    fields = [f.name() for f in layer.fields()]
    by_lower = {f.lower(): f for f in fields}
    ket_field = by_lower.get("ket")
    layer_field = by_lower.get("layer")
    pk_col = detect_pk_column(layer)
    for feat in layer.getFeatures():
        geom = feat.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        ket = None
        for src in (ket_field, layer_field):
            if src:
                v = feat.attribute(src)
                if v is not None and str(v).strip():
                    ket = str(v)
                    break
        if not is_special_ket(ket):
            continue
        lines = []
        if geom.type() == QgsWkbTypes.GeometryType.LineGeometry:
            parts = (
                geom.asMultiPolyline()
                if geom.isMultipart()
                else [geom.asPolyline()]
            )
            for part in parts:
                pts = [(p.x(), p.y()) for p in part]
                if len(pts) >= 2:
                    lines.append(pts)
        if not lines:
            continue
        fid = feat.attribute(pk_col) if pk_col else feat.id()
        box_id = "div:{}".format(fid)
        bbox = geom.boundingBox()
        boxes.append(
            FeatureBox(
                box_id,
                [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum()],
                [],
                ket,
                lines=lines,
            )
        )
        geoms[box_id] = geom
    return boxes, geoms


def parse_width_mm(text, default=0.5):
    """Parse lebar garis (mm) dari teks combo panel: '0,5' / '0.5' /
    '1' / '1,5 mm' -> float. Gagal parse -> default."""
    try:
        cleaned = str(text).strip().lower().replace("mm", "").replace(",", ".").strip()
        value = float(cleaned)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def detect_pk_column(layer):
    """Nama kolom primary key (port PRAGMA table_info; fallback 'fid')."""
    try:
        indices = layer.primaryKeyAttributes()
        if indices:
            return layer.fields().at(indices[0]).name()
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass
    names = [f.name() for f in layer.fields()]
    for candidate in ("fid", "FID", "ogc_fid", "id"):
        if candidate in names:
            return candidate
    return ""


def batch_code(gpkg_path):
    stem = os.path.splitext(os.path.basename(gpkg_path))[0]
    trimmed = stem[3:] if stem.lower().startswith("pbt") else stem
    code = "".join(c if c.isalnum() else "_" for c in trimmed).strip("_")
    return code or "BATCH"


def output_filename(batch, group_id, scale, with_imagery):
    safe_group = "".join(c if c.isalnum() else "_" for c in group_id).strip("_")
    return "PBTF_{}_{}_{}_{}.pdf".format(
        batch,
        safe_group,
        scale.replace(":", "-"),
        "CITRA" if with_imagery else "TANPA_CITRA",
    )


def sheet_shp_filename(batch, group_id, scale):
    """Nama file SHP persil satu lembar (v0.7.2, port PBTK v0.2.3):
    PBTF_{batch}_{Lxx}_{skala}_persil.shp. Ikut pola output_filename,
    TANPA sufiks CITRA/TANPA_CITRA (SHP tidak tergantung citra — satu
    SHP per grup, bukan per varian PDF). Murni."""
    safe_group = "".join(c if c.isalnum() else "_" for c in group_id).strip("_")
    return "PBTF_{}_{}_{}_persil.shp".format(
        batch, safe_group, scale.replace(":", "-")
    )


def sheet_parcel_ids(group_ids, ket_by_id):
    """ID persil (bukan pembagi) satu lembar (v0.7.2, port PBTK v0.2.3).
    Murni (tanpa QGIS).

    group_ids: id grup (pk string + 'div:...' pembagi garis).
    ket_by_id: {id fitur layer: KET} dari boxes (hanya fitur layer).
    Lolos: id ada di ket_by_id DAN KET-nya bukan spesial (persil biasa
    KET None/kosong + SHM — SHM dideteksi via 080203, bukan KET).
    Terbuang: KET spesial (JALAN/IRIGASI/...) dan 'div:...' (pembagi
    garis bukan fitur layer, tidak ada di ket_by_id). Urutan grup
    dipertahankan."""
    return [
        i for i in group_ids
        if i in ket_by_id and not is_special_ket(ket_by_id[i])
    ]


def zip_sheet_shp(shp_path, log):
    """Bundel 5 file komponen SHP satu lembar (.shp, .shx, .dbf, .prj,
    .cpg) ke SATU file ZIP per lembar (v0.7.2 — permintaan Derana
    2026-11-27: file SHP lepas menumpuk acak-acakan di folder output).

    ZIP: {stem}_persil.zip (stem sama dengan .shp, di folder output
    yang sama), berisi tepat 5 file komponen (tanpa folder di dalam
    ZIP, nama file tetap PBTF_..._persil.*). Setelah ZIP terbentuk
    DAN terverifikasi (zipfile valid + isi tepat 5 file yang
    diharapkan), file komponen lepas DIHAPUS supaya folder output
    bersih: 1 ZIP per lembar. Bila .cpg tidak ada (writer tidak
    menulisnya), ditulis dulu berisi "UTF-8" (DBF memang UTF-8)
    supaya tetap 5 file. Bila ZIP gagal / tidak terverifikasi, file
    lepas DIBIARKAN (log peringatan) dan kembalikan (None, 0) —
    SHP-nya tetap ada, hanya tidak ter-ZIP. Murni (tanpa QGIS).
    Mengembalikan (zip_path, jumlah_file_di_zip)."""
    import zipfile as _zf

    base = os.path.splitext(shp_path)[0]
    zip_path = base + ".zip"
    exts = (".shp", ".shx", ".dbf", ".prj", ".cpg")
    # .cpg: writer V2 dengan fileEncoding UTF-8 umumnya menulisnya;
    # bila tidak ada, tulis sendiri (DBF ditulis UTF-8).
    cpg_path = base + ".cpg"
    if not os.path.exists(cpg_path):
        try:
            with open(cpg_path, "w", encoding="utf-8") as fh:
                fh.write("UTF-8")
        except OSError:  # nosec B110  # best-effort; verifikasi di bawah
            pass
    parts = []
    for ext in exts:
        p = base + ext
        if os.path.exists(p):
            parts.append(p)
    if len(parts) != len(exts):
        log("ZIP SHP dilewati: {} (komponen tidak lengkap: {}/{})".format(
            os.path.basename(shp_path), len(parts), len(exts)))
        return None, 0
    if os.path.exists(zip_path):
        os.remove(zip_path)
    try:
        with _zf.ZipFile(zip_path, "w", _zf.ZIP_DEFLATED) as zf:
            for p in parts:
                zf.write(p, os.path.basename(p))
    except OSError as exc:
        log("ZIP SHP gagal: {} ({})".format(os.path.basename(zip_path), exc))
        return None, 0
    # Verifikasi SEBELUM menghapus file lepas: zip valid + isi tepat
    # 5 file yang diharapkan.
    try:
        if not _zf.is_zipfile(zip_path):
            raise ValueError("bukan file ZIP")
        with _zf.ZipFile(zip_path) as zf:
            names = sorted(zf.namelist())
        expected = sorted(os.path.basename(p) for p in parts)
        if names != expected:
            raise ValueError("isi ZIP tidak cocok: {}".format(names))
    except (ValueError, _zf.BadZipFile) as exc:
        log("ZIP SHP tidak terverifikasi: {} ({}) — file lepas dibiarkan".format(
            os.path.basename(zip_path), exc))
        return None, 0
    for p in parts:
        try:
            os.remove(p)
        except OSError:  # nosec B110  # best-effort; ZIP sudah jadi
            pass
    log("SHP ZIP: {} (5 file)".format(os.path.basename(zip_path)))
    return zip_path, len(parts)


def export_parcels_shp(layer, shp_path, log, pk_col=None, feature_ids=None, skip_empty=False):
    """Ekspor persil saja (tanpa jalan/sungai/pembagi) ke Shapefile (v0.7.0;
    v0.7.2: per lembar, port PBTK v0.2.3).

    layer: QgsVectorLayer GPKG input (sudah dimuat; subset HARUS sudah
    dibersihkan pemanggil supaya semua fitur terbaca). Hanya fitur yang
    KET-nya BUKAN spesial (is_special_ket False) yang ditulis, dengan
    SEMUA atribut + CRS asal. feature_ids (set pk string, opsional):
    bila diberikan, hanya fitur yang pk-nya ada di himpunan itu yang
    ditulis — dipakai render_batch untuk SHP per lembar (layer sudah
    di-subset ke grup itu; filter id membuat hasil benar walau subset
    gagal/lepas). pk_col: nama kolom pk (bila None, dideteksi; bila
    tidak ketemu, dipakai id internal fitur). skip_empty: bila True dan
    tidak ada persil yang cocok, lewati (log + kembalikan (None, 0))
    alih-alih ValueError — dipakai lembar dengan 0 persil. Tanpa
    feature_ids/skip_empty, perilaku lama (semua persil layer;
    ValueError bila kosong) dipertahankan.
    Pembacaan atribut memakai _attr_str (cek NULL eksplisit, bukan
    pola val() lama). Mengembalikan (path, jumlah_persil).
    SHP/DBF membatasi nama field 10 karakter dan lebar 254 — field
    GPKG (080201, NAMA, LUAS, ...) sudah memenuhi; writer memotong
    bila perlu. Penulis V2 dipakai dulu (ada di QGIS 3.22 dan 4.x),
    V1 sebagai fallback."""
    from qgis.core import (
        QgsCoordinateTransformContext, QgsFeature, QgsVectorFileWriter,
        QgsVectorLayer, QgsWkbTypes,
    )
    fields = layer.fields()
    ket_idx = next(
        (i for i, f in enumerate(fields) if f.name().lower() == "ket"), None
    )
    pk_idx = None
    if feature_ids is not None:
        col = pk_col or detect_pk_column(layer)
        if col:
            pk_idx = next(
                (i for i, f in enumerate(fields) if f.name() == col), None
            )
    geom_name = QgsWkbTypes.displayString(QgsWkbTypes.flatType(layer.wkbType()))
    crs = layer.crs()
    mem = QgsVectorLayer(
        "{}?crs={}".format(geom_name, crs.authid()), "persil", "memory"
    )
    mem.dataProvider().addAttributes(list(fields))
    mem.updateFields()
    feats = []
    for feat in layer.getFeatures():
        if feature_ids is not None:
            key = feat.attribute(pk_idx) if pk_idx is not None else feat.id()
            # pk di feature_ids disimpan sebagai string (FeatureBox.id);
            # _attr_str menangani QVariant null (bukan "NULL").
            if _attr_str(key) not in feature_ids:
                continue
        ket = (_attr_str(feat.attribute(ket_idx))
               if ket_idx is not None else None)
        if is_special_ket(ket):
            continue
        nf = QgsFeature(mem.fields())
        nf.setAttributes(feat.attributes())
        nf.setGeometry(feat.geometry())
        feats.append(nf)
    if not feats:
        if skip_empty:
            log("SHP dilewati: {} (0 persil di lembar ini)".format(
                os.path.basename(shp_path)))
            return None, 0
        raise ValueError("Tidak ada persil (bukan pembagi) di layer ini.")
    mem.dataProvider().addFeatures(feats)
    # Hapus sidecar SHP lama supaya writer tidak gagal.
    base = os.path.splitext(shp_path)[0]
    for ext in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qmd"):
        p = base + ext
        if os.path.exists(p):
            os.remove(p)
    code = None
    if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV2"):
        try:
            opts = QgsVectorFileWriter.SaveVectorOptions()
            opts.driverName = "ESRI Shapefile"
            opts.fileEncoding = "UTF-8"
            res = QgsVectorFileWriter.writeAsVectorFormatV2(
                mem, shp_path, QgsCoordinateTransformContext(), opts
            )
            code = res[0] if isinstance(res, (tuple, list)) else res
        except Exception:  # nosec B110  # fallback ke V1 di bawah
            code = None
    if code != 0 and hasattr(QgsVectorFileWriter, "writeAsVectorFormat"):
        try:
            res = QgsVectorFileWriter.writeAsVectorFormat(
                mem, shp_path, "UTF-8", crs, "ESRI Shapefile"
            )
            code = res[0] if isinstance(res, (tuple, list)) else res
        except Exception:  # nosec B110  # gagal total -> ValueError di bawah
            code = None
    if code != 0 or not os.path.exists(shp_path):
        raise ValueError("Gagal menulis SHP persil: {}".format(shp_path))
    log("SHP persil: {} ({} persil)".format(os.path.basename(shp_path), len(feats)))
    return shp_path, len(feats)


def zip_pdfs(pdf_paths, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf in pdf_paths:
            zf.write(pdf, os.path.basename(pdf))
    return zip_path


def load_layout(qpt_path, project=None):
    """Muat template .qpt jadi QgsPrintLayout (tanpa mengubah file .qpt).
    project: QgsProject pemilik layout (default QgsProject.instance())."""
    from qgis.core import QgsPrintLayout, QgsProject, QgsReadWriteContext

    try:
        from qgis.PyQt.QtXml import QDomDocument
    except ImportError:  # QGIS 4 / PyQt6
        from PyQt6.QtXml import QDomDocument

    doc = QDomDocument()
    with open(qpt_path, "r", encoding="utf-8") as f:
        ok = doc.setContent(f.read())
    if not ok:
        raise ValueError("Template QPT tidak bisa dibaca: {}".format(qpt_path))
    layout = QgsPrintLayout(project or QgsProject.instance())
    if not layout.loadFromTemplate(doc, QgsReadWriteContext()):
        raise ValueError("Template QPT gagal dimuat ke layout: {}".format(qpt_path))
    return layout


def _find_item_by_id_ci(layout, wanted):
    wanted = wanted.lower()
    for item in layout.items():
        try:
            if (item.id() or "").lower() == wanted:
                return item
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue
    return None


def _snapshot_label_texts(layout):
    """Simpan teks asli semua label layout (bentuk template, masih berisi
    token [%"..."%]). Dipakai untuk mengembalikan label ke bentuk template
    di tiap lembar sebelum _apply_label_values — tanpa ini, lembar 1 akan
    mengganti token `lembar` menjadi "1" dan lembar 2..10 tidak lagi punya
    token untuk diganti (semuanya akan tertulis "Lembar 1")."""
    from qgis.core import QgsLayoutItemLabel

    snap = []
    for item in layout.items():
        try:
            if isinstance(item, QgsLayoutItemLabel):
                snap.append((item, item.text()))
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue
    return snap


def _restore_label_texts(snapshot):
    for item, text in snapshot:
        try:
            item.setText(text)
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue


# Sistem koordinat Indonesia (teks yang ditulis ke frame — bukan CRS peta;
# CRS peta mengikuti data GPKG). TM-3 adalah standar kadaster BPN;
# UTM dan geografis disertakan sebagai pilihan.
COORD_SYSTEMS = (
    ["WGS 1984"]
    + ["WGS 1984 TM3 Zona {}.{}".format(z, s) for z in range(46, 55) for s in (1, 2)]
    + ["WGS 1984 UTM Zona {}{}".format(z, h) for z in range(46, 55) for h in ("N", "S")]
)
DEFAULT_COORD_SYSTEM = "WGS 1984 TM3 Zona 48.2"

# Nilai default isi frame = isi template contoh PBTF_Demo_YukTech.qpt
# (nama demo/promosi ig:@yuktech + PT Kebakaran Jenggot, BUKAN nama asli
# Cianjur — plugin ini dibagikan ke publik). Nama tempat tetap Cianjur.
FRAME_DEFAULTS = {
    "coord_system": DEFAULT_COORD_SYSTEM,
    "area_kind": "Desa",
    "area_name": "Gudang",
    "admin_kind": "Kabupaten",
    "admin_name": "Cianjur",
    "kecamatan": "Cikalongkulon",
    "provinsi": "Jawa Barat",
    "surveyor_name": "ig:@yuktech",
    "surveyor_license": "9-6969-69",
    "leader_org": "PT Kebakaran Jenggot",
    "leader_name": "ig:@yuktech",
    "leader_position": "Direktur Utama",
    "usage_role": "Wakil Raja Iblis",
    "usage_name": "ig:@yuktech",
    "usage_nip": "123456789",
    "executor_pt": "PT Kebakaran Jenggot",
    "executor_address": "Jl. Kebakaran Jenggot No. 69, Jakarta Selatan",
}


def _frame_values(opts):
    """Nilai isi frame: dari opts, dilengkapi default template."""
    frame = dict(FRAME_DEFAULTS)
    for key in FRAME_DEFAULTS:
        val = opts.get(key)
        if isinstance(val, str) and val.strip():
            frame[key] = val.strip()
    return frame


def _apply_frame_texts(layout, frame):
    """Tulis 9 butir isi frame ke label layout.

    Label di template tidak punya id — dikenali dari isi teks bawaannya
    (dan posisi y untuk label yang kembar). Jangkar teks menerima DUA
    versi template: PBTF_WARDOY.qpt (nama asli Cianjur) dan
    PBTF_Demo_YukTech.qpt (nama demo ig:@yuktech / PT Kebakaran Jenggot).
    Dua label PT yang kembar dibedakan lewat posisi y (kecil = pimpinan,
    besar = pelaksana); tiga label "ig:@yuktech" yang kembar juga
    dibedakan lewat y (kecil = petugas ukur, tengah = pimpinan,
    besar = penggunaan). Dipanggil pada layout yang masih berisi teks
    template, SEBELUM _apply_label_values, supaya token [%"b"%] /
    [%"tglF"%] di label yang sama tetap utuh dan diganti nilainya
    sesudahnya. Mengembalikan daftar peringatan untuk butir yang tidak
    ketemu (template lain / template sudah diubah).
    """
    from qgis.core import QgsLayoutItemLabel

    def _y(item):
        # Posisi y label DI LAYOUT (mm, membesar ke bawah) — dipakai untuk
        # membedakan label kembar (tiga "ig:@yuktech", dua PT).
        # BUG v0.6.3: rect().top() SELALU 0.0 — rect() adalah koordinat
        # LOKAL item, bukan posisi di layout — sehingga sort-y jadi no-op
        # dan urutan penugasan = urutan layout.items() (sembarang):
        # nama surveyor/penggunaan + dua PT tertukar. scenePos().y()
        # (fallback pos().y()) mengembalikan koordinat layout yang benar
        # (terbukti di sandbox 3.22: 177.97 / 218.76 / 259.15 dst).
        # Ditulis tanpa try-except-continue (Bandit B112) — validator
        # plugins.qgis.org memblokir pola itu; fallback dicek dengan
        # getattr + callable, bukan try di dalam loop.
        try:
            for getter in ("scenePos", "pos"):
                fn = getattr(item, getter, None)
                if callable(fn):
                    return fn().y()
            return item.rect().top()
        except Exception:
            return 0.0

    labels = []
    for item in layout.items():
        try:
            if isinstance(item, QgsLayoutItemLabel):
                labels.append(item)
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue

    # Dua label PT yang kembar — bedakan lewat posisi y.
    pt_items = sorted(
        [it for it in labels
         if it.text() in ("PT. SANGGA BUANA NUSANTARA", "PT Kebakaran Jenggot")],
        key=_y,
    )
    leader_org_item = pt_items[0] if pt_items else None
    executor_pt_item = pt_items[1] if len(pt_items) > 1 else None

    # Tiga label "ig:@yuktech" (template demo) — bedakan lewat posisi y.
    ig_items = sorted(
        [it for it in labels if it.text() == "ig:@yuktech"],
        key=_y,
    )
    ig_surveyor_item = ig_items[0] if ig_items else None
    ig_leader_item = ig_items[1] if len(ig_items) > 1 else None
    ig_usage_item = ig_items[2] if len(ig_items) > 2 else None

    found = set()
    for item in labels:
        text = item.text()
        try:
            if text.startswith("Sistem Koordinat "):
                item.setText("Sistem Koordinat {}".format(frame["coord_system"]))
                found.add("coord_system")
            elif text.startswith("  Blok") and "Kecamatan" in text and "Provinsi" in text:
                # Kolom kiri: Blok / Desa|Kelurahan / Kecamatan /
                # Kabupaten|Kota / Provinsi.
                item.setText(
                    "  Blok\n  {}\n  Kecamatan\n  {}\n  Provinsi".format(
                        frame["area_kind"], frame["admin_kind"]
                    )
                )
                found.add("area_kind")
            elif text.startswith(":  [%") and text.count("\n") == 4:
                # Kolom kanan nilai: Blok (token) / Desa / Kecamatan /
                # Kabupaten / Provinsi. Baris 1 (token b) dipertahankan.
                lines = text.split("\n")
                item.setText(
                    "\n".join(
                        [
                            lines[0],
                            ":  {}".format(frame["area_name"]),
                            ":  {}".format(frame["kecamatan"]),
                            ":  {}".format(frame["admin_name"]),
                            ":  {}".format(frame["provinsi"]),
                        ]
                    )
                )
                found.add("area_values")
            elif (text.startswith("Kabupaten : ") or text.startswith("Kota : ")) and _y(item) < 10:
                # Header atas frame.
                item.setText("{} : {}".format(frame["admin_kind"], frame["admin_name"]))
                found.add("admin_top")
            elif text.startswith("Provinsi : ") and _y(item) < 10:
                # Header atas frame.
                item.setText("Provinsi : {}".format(frame["provinsi"]))
                found.add("provinsi_top")
            elif "Untuk Pembuatannya" in text:
                # "Cianjur, [tglF] / Untuk Pembuatannya, / Petugas Ukur"
                # — ganti nama tempat sebelum tanggal.
                lines = text.split("\n")
                lines[0] = re.sub(
                    r"^.*?,", frame["admin_name"] + ",", lines[0], count=1
                )
                item.setText("\n".join(lines))
                found.add("place_date_surveyor")
            elif "Untuk Penggunaannya" in text:
                # "Cianjur, [tglF] / Untuk Penggunaannya, / <peran>"
                lines = text.split("\n")
                lines[0] = re.sub(
                    r"^.*?,", frame["admin_name"] + ",", lines[0], count=1
                )
                if len(lines) > 2:
                    lines[2] = frame["usage_role"]
                item.setText("\n".join(lines))
                found.add("place_date_usage")
                found.add("usage_role")
            elif text == "Moch Ikhsan Panca Utama":
                item.setText(frame["surveyor_name"])
                found.add("surveyor_name")
            elif text in ("2-1501-19", "9-6969-69"):
                item.setText(frame["surveyor_license"])
                found.add("surveyor_license")
            elif text == "Ir. Rudy Themonady L":
                item.setText(frame["leader_name"])
                found.add("leader_name")
            elif text == "Direktur Utama":
                item.setText(frame["leader_position"])
                found.add("leader_position")
            elif text == "Dede Kuswana S.SIT":
                item.setText(frame["usage_name"])
                found.add("usage_name")
            elif text in ("NIP. 197306141994031002", "NIP. 123456789"):
                item.setText("NIP. {}".format(frame["usage_nip"]))
                found.add("usage_nip")
            elif text in ("Jl. Kalibata Timur No. 12 Jakarta Selatan",
                          "Jl. Kebakaran Jenggot No. 69, Jakarta Selatan"):
                item.setText(frame["executor_address"])
                found.add("executor_address")
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue
    if ig_surveyor_item is not None:
        try:
            ig_surveyor_item.setText(frame["surveyor_name"])
            found.add("surveyor_name")
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
    if ig_leader_item is not None:
        try:
            ig_leader_item.setText(frame["leader_name"])
            found.add("leader_name")
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
    if ig_usage_item is not None:
        try:
            ig_usage_item.setText(frame["usage_name"])
            found.add("usage_name")
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
    if leader_org_item is not None:
        try:
            leader_org_item.setText(frame["leader_org"])
            found.add("leader_org")
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
    if executor_pt_item is not None:
        try:
            executor_pt_item.setText(frame["executor_pt"])
            found.add("executor_pt")
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass

    wanted = {
        "coord_system", "area_kind", "area_values", "admin_top",
        "provinsi_top", "place_date_surveyor", "place_date_usage",
        "usage_role", "surveyor_name", "surveyor_license", "leader_org",
        "leader_name", "leader_position", "usage_name", "usage_nip",
        "executor_pt", "executor_address",
    }
    missing = sorted(wanted - found)
    if missing:
        return [
            "Isi frame tidak ketemu di template (label tidak diubah): {}".format(
                ", ".join(missing)
            )
        ]
    return []


def _apply_label_values(layout, values):
    """Tulis nilai layout (tgl/tglF/pbt/b/lembar) sebagai teks literal ke
    semua QgsLayoutItemLabel — cerminan replace_layout_token() di Rust.

    setLayoutVariables() saja TIDAK cukup di QGIS 3.22: variabel memang
    tersimpan (customProperties variableNames/variableValues), tetapi
    layoutScope() tidak mengeksposnya ke ekspresi — [%"pbt"%] di-evaluasi
    sebagai field dan gagal ("Field 'pbt' not found") sehingga label
    menampilkan teks [%...%] mentah. Karena itu token diganti langsung
    dengan nilainya, persis seperti yang dilakukan aplikasi desktop.
    """
    from qgis.core import QgsLayoutItemLabel

    for item in layout.items():
        try:
            if not isinstance(item, QgsLayoutItemLabel):
                continue
            text = item.text()
            new = text
            for token, value in values.items():
                pat = re.compile(
                    r"\[%\s*(?:\"|&quot;)?\s*"
                    + re.escape(token)
                    + r"\s*(?:\"|&quot;)?\s*%\]"
                )
                new = pat.sub(value, new)
            if new != text:
                item.setText(new)
        except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
            continue


def _layer_has_features(layer):
    """True bila layer (dengan subset aktif) menghasilkan >=1 fitur.
    featureCount() bisa -1 bila hitung gagal (mis. subset SQL invalid) —
    konfirmasi lewat getFeatures(). Dipakai untuk memverifikasi subset
    per-lembar sebelum render (lihat render_batch)."""
    try:
        if layer.featureCount() > 0:
            return True
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass
    try:
        return next(layer.getFeatures(), None) is not None
    except Exception:
        return False


def _set_sheet_subset(layer, pk_col, ids, group_id, log):
    """Pasang subset per-lembar dengan verifikasi + fallback (QGIS 4.2):
    subset bisa gagal diam-diam (0 fitur) sehingga lembar kosong tanpa
    error. Bila kosong padahal grup berisi fitur, coba kolom 'fid', lalu
    lepas subset (semua fitur, dibatasi extent lembar). Dipakai loop PDF
    dan builder .qgs supaya perilakunya sama."""
    if pk_col:
        subset = '"{}" IN ({})'.format(pk_col, ",".join(str(i) for i in ids))
    else:
        subset = ""
    layer.setSubsetString(subset)
    if subset and ids and not _layer_has_features(layer):
        log("PERINGATAN lembar {}: subset '{}' menghasilkan 0 fitur; mencoba kolom fid.".format(group_id, subset))
        layer.setSubsetString('"fid" IN ({})'.format(",".join(str(i) for i in ids)))
        if not _layer_has_features(layer):
            log("PERINGATAN lembar {}: subset tetap 0 fitur; subset dilepas (semua fitur, dibatasi extent lembar).".format(group_id))
            layer.setSubsetString("")
    return layer.subsetString()


def _apply_map_grid(map_item, denominator):
    """Atur grid peta per lembar (v0.7.2, opsi B — port PBTK v0.2.1).

    Interval tanah = denominator * 0,1 m (jarak layout tetap 100 mm)
    + offset supaya satu garis lewat titik jangkar PBT (pusat frame —
    lihat GRID_ANCHOR_X_MM/GRID_ANCHOR_Y_MM; asumsi, dinyatakan di
    laporan). Dijalankan per layout di _build_qgs_project (Preview +
    Generate memakai jalur yang sama) DAN di loop PDF render_batch
    (render_batch membangun layout sendiri, bukan via
    _build_qgs_project), SETELAH map_item.setExtent — extent + ukuran
    frame lembar menentukan offset, jadi dibaca dari map_item yang
    bersangkutan (bukan dari group).
    annotationPrecision diatur 0 (label bilangan bulat, seperti PBTK)
    bila API tersedia — template PBTF_WARDOY.qpt memakai 2 (label
    desimal, cth. 68140,25); 0 dipilih supaya konsisten dengan PBTK
    dan label lebih bersih. Best-effort: bila API grid tidak tersedia
    / gagal, grid template tetap dipakai; render tidak boleh gagal
    karena grid. Mengembalikan True bila interval + offset berhasil
    diatur.

    PRASYARAT: pemanggil HARUS sudah mengatur CRS peta dari layer
    (map_item.setCrs(layer.crs())) SEBELUM memanggil fungsi ini.
    Template PBTF_WARDOY.qpt tidak menyimpan CRS peta, sehingga tanpa
    setCrs skala peta terhitung 1:44 jt dan grid tidak ter-render
    (interval tanah jadi ~0 mm di layout) walau interval/offset
    sudah benar. (Template PBTK menyimpan CRS, jadi tidak kena.)

    CATATAN SANDBOX (QGIS 3.22, TEST-PBT-274): garis grid ter-render
    dan label menampilkan koordinat asli, TETAPI jarak antar garis
    yang terukur di PDF adalah ~50 mm, bukan 100 mm yang dimaksud
    (interval tanah efektif ~setengah dari yang diatur). Garis tetap
    lewat titik jangkar (posisi jangkar ada di antara garis-garis
    itu), hanya kerapatan garis 2x. Penyebab belum terisolasi:
    terjadi baik saat CRS dari setCrs maupun dari template yang
    sudah berisi CRS (PBTF_WARDOY v1.1), dan baik saat interval
    template 0 maupun 100 — sementara template PBTK v7.6 dengan kode
    yang sama ter-render tepat 100 mm. Diduga kekhasan QGIS 3.22
    terhadap template ini; uji live di QGIS 4.2.2 adalah gerbang
    untuk memastikan jarak sebenarnya. JANGAN menggandakan interval
    sebagai jalan pintas sebelum 4.2.2 teruji (bila 4.2.2 tidak
    membagi dua, gandaan itu justru jadi 200 mm).
    """
    try:
        ext = map_item.extent()
        extent = [ext.xMinimum(), ext.yMinimum(),
                  ext.xMaximum(), ext.yMaximum()]
        rect = map_item.rect()
        map_mm = (rect.width(), rect.height())
    except Exception:  # nosec B110
        return False
    offs = grid_offsets(extent, map_mm, denominator)
    interval = grid_interval_m(denominator)
    if offs is None or interval is None:
        return False
    grid = None
    try:
        grid = map_item.grid()
    except Exception:  # nosec B110
        grid = None
    if grid is None:
        try:
            grids = map_item.grids()
            grid = grids[0] if grids else None
        except Exception:  # nosec B110
            grid = None
    if grid is None:
        return False
    try:
        # Longgarkan dulu batas lebar interval template (min 50 /
        # maks 100 mm): jarak layout opsi B selalu 100 mm (= batas
        # maks) dan interval kecil (25 m di 1:250) tidak boleh diubah
        # QGIS. API ini ada di QGIS 3.22 dan 4.x; gagal diam-diam bila
        # tidak ada.
        for setter, value in (("setMaximumIntervalWidth", 10000.0),
                              ("setMinimumIntervalWidth", 0.0)):
            try:
                getattr(grid, setter)(value)
            except Exception:  # nosec B110
                pass
        grid.setIntervalX(interval)
        grid.setIntervalY(interval)
        try:
            grid.setOffsetX(offs[0])
            grid.setOffsetY(offs[1])
        except AttributeError:
            from qgis.PyQt.QtCore import QPointF
            grid.setOffset(QPointF(offs[0], offs[1]))
        # Label bilangan bulat (seperti PBTK v0.2.1); bila API tidak
        # ada, presisi template (2) tetap dipakai.
        try:
            grid.setAnnotationPrecision(0)
        except Exception:  # nosec B110
            pass
    except Exception:  # nosec B110
        return False
    return True


def _build_qgs_project(opts, groups, boxes, fields, pk_col, dividers, frame,
                     divider_geoms=None, return_project=False):
    """Bangun SATU proyek QGIS (.qgs) berisi SEMUA lembar sebagai layout.

    Proyek terpisah (bukan QgsProject.instance()) supaya tidak menyentuh
    proyek QGIS user yang sedang terbuka. Tiap lembar mendapat layer
    vektor sendiri (subset per-lembar — subset adalah properti layer,
    jadi satu layer tidak bisa melayani 10 layout) + layout sendiri dari
    template, dengan isi frame + nilai lembar yang sama seperti PDF.
    Mengembalikan path .qgs (PBTF_{batch}.qgs di folder output), atau
    (path, proyek) bila return_project=True (dipakai render_preview
    v0.6.2 untuk mengekspor PNG dari layout yang sudah dibangun)."""
    from qgis.core import (
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsProject,
        QgsRasterLayer,
        QgsRectangle,
        QgsVectorLayer,
    )

    log = opts.get("log") or (lambda msg: None)
    batch = batch_code(opts["gpkg_path"])
    output_dir = opts["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    qgs_path = os.path.join(output_dir, "PBTF_{}.qgs".format(batch))

    out_project = QgsProject()
    gpkg_path = opts["gpkg_path"]
    layer_name = opts["layer_name"]
    source = "{}|layername={}".format(gpkg_path, layer_name)
    probe = QgsVectorLayer(source, layer_name, "ogr")
    if not probe.isValid():
        raise ValueError("Layer GPKG tidak bisa dibuka: {} ({})".format(gpkg_path, layer_name))
    out_project.setCrs(probe.crs())

    # Geometri asli per pk (kunci str — FeatureBox.id berupa str) untuk
    # trim pembagi di Python (lihat _trimmed_divider_layers). Pembagi
    # garis (id 'div:<pk>') geometrinya dari divider_geoms.
    geom_by_pk = {}
    for feat in probe.getFeatures():
        key = feat.attribute(pk_col) if pk_col else feat.id()
        g = feat.geometry()
        if g is not None and not g.isNull():
            geom_by_pk[str(key)] = g
    if divider_geoms:
        geom_by_pk.update(divider_geoms)

    raster = None
    if opts["with_imagery"]:
        raster = QgsRasterLayer(opts["ecw_path"], "ECW", "gdal")
        if not raster.isValid():
            raise ValueError("ECW tidak bisa dibuka: {}".format(opts["ecw_path"]))
        out_project.addMapLayer(raster, False)

    outline_rgb = parcel_color_rgb(opts.get("parcel_color") or "hijau")
    text_rgb = text_color_rgb(opts.get("text_color") or "")

    frame_warned = False
    for index, group in enumerate(groups):
        # Subset layer persil: HANYA persil lembar ini. Pembagi TIDAK lagi
        # dimasukkan ke layer ini — mereka digambar dari layer memori
        # hasil _trimmed_divider_layers (trim di Python, bukan lewat
        # aggregate yang gagal di proyek terpisah ini).
        ids = list(group.feature_ids)
        sheet_layer = QgsVectorLayer(
            source, "{}_{}".format(layer_name, group.id), "ogr"
        )
        if not sheet_layer.isValid():
            raise ValueError("Layer lembar {} tidak bisa dibuat.".format(group.id))
        # Gaya label per lembar (v0.6.0): ukuran font mengikuti skala
        # lembar ini — di mode Auto campuran tiap lembar bisa beda skala.
        denominator = parse_scale(group.scale) or 1000.0
        apply_parcel_style(sheet_layer, outline_rgb, text_rgb, fields, denominator,
                           **_style_kwargs(opts))
        _set_sheet_subset(sheet_layer, pk_col, ids, group.id, log)
        out_project.addMapLayer(sheet_layer, False)

        # Pembagi (jalan/air) yang sudah di-trim di Python — layer memori
        # per lembar; [] bila tidak ada pembagi yang tersisa, atau bila
        # opsi "Tampilkan jalan/sungai" dimatikan (v0.6.4).
        div_layers = []
        if opts.get("show_dividers", True):
            div_layers = _trimmed_divider_layers(
                dividers, group, geom_by_pk, probe.crs(),
                "{}_{}".format(layer_name, group.id),
                road_width_mm=float(opts.get("road_width_mm") or 0.5),
                water_width_mm=float(opts.get("water_width_mm") or 0.5),
            )
        map_layers = [sheet_layer]
        for div_layer in div_layers:
            out_project.addMapLayer(div_layer, False)
            map_layers.append(div_layer)

        layout = load_layout(opts["qpt_path"], project=out_project)
        layout.setName("PBTF {} {}".format(batch, group.id))
        map_item = _find_item_by_id_ci(layout, "Map 1")
        if map_item is None or not isinstance(map_item, QgsLayoutItemMap):
            for item in layout.items():
                if isinstance(item, QgsLayoutItemMap):
                    map_item = item
                    break
        if map_item is None:
            raise ValueError("Item peta 'Map 1' tidak ditemukan di template QPT.")
        try:
            map_item.setKeepLayerSet(True)
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
        # CRS peta dari layer GPKG (v0.7.2): template PBTF_WARDOY.qpt
        # TIDAK menyimpan CRS peta (tidak ada elemen <crs>), sehingga
        # map_item.crs() kosong dan skala terhitung 1:44 jt — grid
        # tidak ter-render (interval tanah jadi ~0 mm di layout).
        # Set eksplisit dari CRS data supaya skala + grid benar.
        # (Template PBTK menyimpan CRS EPSG:23833, jadi tidak kena.)
        try:
            map_item.setCrs(probe.crs())
        except Exception:  # nosec B110  # best-effort
            pass
        map_item.setExtent(QgsRectangle(*group.extent))
        # Grid skala-bergantung v0.7.2 (opsi B) — per layout, setelah
        # setExtent (extent menentukan offset).
        _apply_map_grid(map_item, denominator)
        map_item.setLayers(
            map_layers + ([raster] if opts["with_imagery"] and raster else [])
        )
        warns = _apply_frame_texts(layout, frame)
        if warns and not frame_warned:
            for w in warns:
                log(w)
            frame_warned = True
        _apply_label_values(
            layout,
            {
                "tgl": opts.get("date", ""),
                "tglF": opts.get("date", ""),
                "pbt": opts.get("pbt_number", ""),
                "b": opts.get("block", ""),
                "lembar": str(index + 1),
            },
        )
        for item in layout.items():
            try:
                if isinstance(item, QgsLayoutItemLabel) and "map_scale" in item.text():
                    text = item.text()
                    m = re.search(r"\[%.*?map_scale.*?%\]", text, re.S)
                    if m:
                        item.setText(text[: m.start()] + group.scale + text[m.end():])
            except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
                continue
        for wanted, path in (
            ("logo", opts.get("logo_path")),
            ("ttd panca", opts.get("surveyor_path")),
            ("ttd rudy", opts.get("leader_path")),
        ):
            if path and os.path.exists(path):
                pic = _find_item_by_id_ci(layout, wanted)
                if pic is not None and isinstance(pic, QgsLayoutItemPicture):
                    pic.setPicturePath(path)
        out_project.layoutManager().addLayout(layout)

    if os.path.exists(qgs_path):
        os.remove(qgs_path)
    if not out_project.write(qgs_path):
        raise ValueError("Proyek QGIS gagal disimpan: {}".format(qgs_path))
    log("QGS: {} ({} layout)".format(
        os.path.basename(qgs_path), len(groups)
    ))
    if return_project:
        return qgs_path, out_project
    return qgs_path


def render_batch(opts):
    """Render semua lembar. opts: dict dengan kunci
    gpkg_path, layer_name, qpt_path, ecw_path (atau None), output_dir,
    scale ('Auto'/'1:1000'/...), parcel_color (nama), text_color (nama),
    with_imagery, without_imagery, output_format ('pdf'/'zip'),
    date, pbt_number, block, logo_path, surveyor_path, leader_path,
    log (callable(str) atau None), first_sheet_only (bool),
    export_shp (bool, v0.7.0; v0.7.2: per lembar + ZIP per lembar): tulis
    SHP persil saja (tanpa pembagi) — satu file ZIP per lembar
    (PBTF_{batch}_{Lxx}_{skala}_persil.zip, berisi 5 file komponen SHP;
    file lepas dihapus setelah ZIP terverifikasi).
    Mengembalikan dict {pdfs, zip, qgs, shp, groups, warnings} — "shp"
    kini DAFTAR path ZIP SHP per lembar (list, kosong bila export_shp
    mati)."""
    from qgis.core import (
        QgsExpressionContextUtils,
        QgsLayoutExporter,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsProject,
        QgsRasterLayer,
        QgsRectangle,
        QgsVectorLayer,
    )
    import re

    log = opts.get("log") or (lambda msg: None)
    err = validate_requested_scale(opts["scale"])
    if err:
        raise ValueError(err)
    if not opts["with_imagery"] and not opts["without_imagery"]:
        raise ValueError("Pilih minimal satu varian output (dengan citra atau tanpa citra).")
    if opts["with_imagery"] and not opts.get("ecw_path"):
        raise ValueError("Varian 'Dengan citra ECW' dipilih tetapi file ECW belum dipilih.")

    project = QgsProject.instance()
    gpkg_path = opts["gpkg_path"]
    layer_name = opts["layer_name"]
    layer = QgsVectorLayer(
        "{}|layername={}".format(gpkg_path, layer_name), layer_name, "ogr"
    )
    if not layer.isValid():
        raise ValueError("Layer GPKG tidak bisa dibuka: {} ({})".format(gpkg_path, layer_name))
    if layer.crs().isGeographic():
        raise ValueError(
            "CRS layer ini geografis (derajat). Reproyeksikan ke CRS proyeksi "
            "metrik (mis. TM-3) sebelum membuat lembar PBT."
        )
    project.addMapLayer(layer, False)
    log("Layer dimuat: {} ({} fitur)".format(layer_name, layer.featureCount()))

    raster = None
    if opts["with_imagery"]:
        raster = QgsRasterLayer(opts["ecw_path"], "ECW", "gdal")
        if not raster.isValid():
            raise ValueError("ECW tidak bisa dibuka: {}".format(opts["ecw_path"]))
        project.addMapLayer(raster, False)
        log("ECW dimuat: {}".format(os.path.basename(opts["ecw_path"])))

    pk_col = detect_pk_column(layer)
    boxes, fields = read_feature_boxes(layer, pk_col)
    if not boxes:
        raise ValueError("Tidak ada fitur dengan geometri yang bisa dibaca di layer ini.")
    log("Fitur terbaca: {} (pk: {})".format(len(boxes), pk_col or "fid internal"))
    # Pembagi garis (v0.6.4): layer 'dividers' di GPKG yang sama.
    line_dividers, div_geoms = read_line_dividers(gpkg_path)
    if line_dividers:
        log("Pembagi garis: {} (layer dividers)".format(len(line_dividers)))
    # Geometri untuk trim pembagi (v0.6.5): persil + pembagi garis.
    # BUG v0.6.4 (dilaporkan Derana 2026-11-26 — Generate tanpa
    # jalan/sungai): loop PDF memanggil _trimmed_divider_layers dengan
    # div_geoms SAJA sebagai geom_by_pk, sehingga parcel_geoms kosong
    # dan fungsi mengembalikan [] — layer pembagi tidak pernah dibuat
    # di jalur PDF (Preview selamat karena _build_qgs_project memakai
    # peta gabungan). Di sini petanya digabung dulu.
    geom_by_pk = {}
    for feat in layer.getFeatures():
        key = feat.attribute(pk_col) if pk_col else feat.id()
        g = feat.geometry()
        if g is not None and not g.isNull():
            geom_by_pk[str(key)] = g
    geom_by_pk.update(div_geoms)

    layout = load_layout(opts["qpt_path"])
    map_item = _find_item_by_id_ci(layout, "Map 1")
    if map_item is None or not isinstance(map_item, QgsLayoutItemMap):
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                map_item = item
                break
    if map_item is None:
        raise ValueError("Item peta 'Map 1' tidak ditemukan di template QPT.")
    # Kunci daftar layer peta ke daftar yang dipasang engine (setLayers).
    # Template PBTF_WARDOY.qpt menyimpan keepLayerSet="false" — di QGIS 4.2.2
    # peta yang tidak dikunci mengikuti layer tree kanvas, sehingga daftar
    # layer plugin (yang ditambah dengan addMapLayer(..., False)) dibuang saat
    # render dan persil tidak tampil kecuali layer GPKG/ECW ikut dibuka di
    # kanvas. Dengan keepLayerSet=True, plugin berdiri sendiri tanpa perlu
    # layer dibuka di kanvas.
    try:
        map_item.setKeepLayerSet(True)
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass
    # CRS peta dari layer GPKG (v0.7.2) — template PBTF_WARDOY.qpt tidak
    # menyimpan CRS peta (lihat _build_qgs_project); tanpa ini skala
    # terhitung 1:44 jt dan grid tidak ter-render.
    try:
        map_item.setCrs(layer.crs())
    except Exception:  # nosec B110  # best-effort
        pass
    rect = map_item.rect()
    map_mm = (rect.width(), rect.height())
    log("Template dimuat: peta {:.1f} x {:.1f} mm".format(*map_mm))

    groups = group_feature_boxes(list(boxes) + line_dividers, opts["scale"], map_mm)
    log("Grouping: {} lembar ({})".format(
        len(groups), ", ".join(str(len(g.feature_ids)) for g in groups)
    ))
    if opts.get("first_sheet_only"):
        groups = groups[:1]
        log("Mode uji: hanya lembar pertama")

    outline_rgb = parcel_color_rgb(opts.get("parcel_color") or "hijau")
    text_rgb = text_color_rgb(opts.get("text_color") or "")
    frame = _frame_values(opts)

    # Pembagi poligon (di layer utama) + pembagi garis (layer dividers).
    poly_dividers = [b for b in boxes if is_special_ket(b.ket) and b.rings]
    dividers = poly_dividers + line_dividers
    batch = batch_code(gpkg_path)
    output_dir = opts["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    # Peta id -> KET untuk filter SHP per lembar (v0.7.2): boxes berisi
    # persil + pembagi poligon; pembagi garis ('div:...') tidak ada di
    # sini sehingga terbuang oleh sheet_parcel_ids.
    ket_by_id = {b.id: b.ket for b in boxes}

    pdfs = []
    shp_paths = []
    warnings = []
    exporter = QgsLayoutExporter(layout)
    label_snapshot = _snapshot_label_texts(layout)
    for index, group in enumerate(groups):
        warnings.extend(group.warnings)
        ids = list(group.feature_ids)
        # Pembagi poligon TIDAK lagi masuk subset layer persil (v0.6.7)
        # — digambar dari layer memori hasil _trimmed_divider_layers
        # (cincin dibuka jadi garis terbuka), sama seperti pembagi
        # garis. Pembagi garis tidak bisa masuk subset (id 'div:...'
        # bukan pk layer ini).
        _set_sheet_subset(layer, pk_col, ids, group.id, log)
        # Gaya label per lembar (v0.6.0): ukuran font mengikuti skala
        # lembar ini — di mode Auto campuran tiap lembar bisa beda skala.
        denominator = parse_scale(group.scale) or 1000.0
        apply_parcel_style(layer, outline_rgb, text_rgb, fields, denominator,
                           **_style_kwargs(opts))
        # Pembagi (poligon + garis) lembar ini (trim di Python,
        # layer memori) — v0.6.7: pembagi poligon dan garis kini
        # sama-sama lewat sini (cincin dibuka), jadi jalur PDF dan
        # Preview/.qgs konsisten.
        div_line_layers = []
        if opts.get("show_dividers", True) and dividers:
            div_line_layers = _trimmed_divider_layers(
                dividers, group, geom_by_pk, layer.crs(),
                "{}_{}".format(layer_name, group.id),
                road_width_mm=float(opts.get("road_width_mm") or 0.5),
                water_width_mm=float(opts.get("water_width_mm") or 0.5),
            )
            for dl in div_line_layers:
                project.addMapLayer(dl, False)
        map_item.setExtent(QgsRectangle(*group.extent))
        # Grid skala-bergantung v0.7.2 (opsi B) — jalur PDF render_batch
        # membangun layout sendiri (bukan via _build_qgs_project), jadi
        # grid harus diatur di sini juga supaya PDF = Preview/.qgs.
        _apply_map_grid(map_item, denominator)
        map_item.setLayers([layer] + div_line_layers + ([raster] if raster else []))
        # Kembalikan label ke bentuk template dulu (lihat
        # _snapshot_label_texts), baru tulis nilai lembar ini.
        _restore_label_texts(label_snapshot)
        # Isi frame (9 butir) — pada teks template, sebelum token diganti.
        frame_warns = _apply_frame_texts(layout, frame)
        if frame_warns and index == 0:
            for w in frame_warns:
                log(w)
        QgsExpressionContextUtils.setLayoutVariables(
            layout,
            {
                "tgl": opts.get("date", ""),
                "tglF": opts.get("date", ""),
                "pbt": opts.get("pbt_number", ""),
                "b": opts.get("block", ""),
                "lembar": str(index + 1),
            },
        )
        # Nilai layout ditulis literal ke label (lihat _apply_label_values):
        # di QGIS 3.22 variabel layout tidak ter-evaluasi di [%"..."%].
        _apply_label_values(
            layout,
            {
                "tgl": opts.get("date", ""),
                "tglF": opts.get("date", ""),
                "pbt": opts.get("pbt_number", ""),
                "b": opts.get("block", ""),
                "lembar": str(index + 1),
            },
        )
        # Label skala ditulis literal seperti v17 (map_scale bisa salah
        # bila CRS proyek tidak terbaca — di plugin CRS sudah benar, tapi
        # literal ini menjaga hasil tetap sama dengan aplikasi desktop).
        for item in layout.items():
            try:
                from qgis.core import QgsLayoutItemLabel

                if isinstance(item, QgsLayoutItemLabel) and "map_scale" in item.text():
                    text = item.text()
                    m = re.search(r"\[%.*?map_scale.*?%\]", text, re.S)
                    if m:
                        item.setText(text[: m.start()] + group.scale + text[m.end():])
            except Exception:  # nosec B112  # best-effort: lanjut ke fitur berikutnya
                continue
        # Gambar logo / tanda tangan (id template huruf besar; cocokkan
        # tanpa memperhatikan huruf).
        for wanted, path in (
            ("logo", opts.get("logo_path")),
            ("ttd panca", opts.get("surveyor_path")),
            ("ttd rudy", opts.get("leader_path")),
        ):
            if path and os.path.exists(path):
                pic = _find_item_by_id_ci(layout, wanted)
                if pic is not None and isinstance(pic, QgsLayoutItemPicture):
                    pic.setPicturePath(path)
        for with_imagery in (True, False):
            if with_imagery and not opts["with_imagery"]:
                continue
            if not with_imagery and not opts["without_imagery"]:
                continue
            # v0.6.5: setLayers di sini MENIMPA setLayers sebelum loop —
            # pembagi garis HARUS ikut, kalau tidak PDF selalu tanpa
            # jalan/sungai (bug v0.6.4, dilaporkan Derana 2026-11-26).
            map_item.setLayers(
                [layer] + div_line_layers
                + ([raster] if with_imagery and raster else [])
            )
            pdf_path = os.path.join(
                output_dir,
                output_filename(batch, group.id, group.scale, with_imagery),
            )
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            pdf_settings = QgsLayoutExporter.PdfExportSettings()
            pdf_settings.dpi = 300
            result = exporter.exportToPdf(pdf_path, pdf_settings)
            success_code = getattr(QgsLayoutExporter, "Success", None)
            if success_code is None:
                success_code = getattr(
                    QgsLayoutExporter.ExportResult, "Success", 0
                )
            ok = result == success_code
            if not ok or not (os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0):
                raise ValueError(
                    "Render lembar {} gagal (kode {}).".format(group.id, result)
                )
            pdfs.append(pdf_path)
            log("PDF: {} ({:.0f} KB)".format(
                os.path.basename(pdf_path), os.path.getsize(pdf_path) / 1024.0
            ))
        # SHP persil PER LEMBAR + ZIP per lembar (v0.7.2): satu ZIP per
        # grup, hanya persil grup ini (termasuk SHM, tanpa pembagi).
        # Ditulis di dalam loop (subset layer masih aktif ke grup ini)
        # + filter id eksplisit supaya benar walau subset gagal/lepas.
        # Lembar 0 persil dilewati; file lepas dihapus setelah ZIP
        # terverifikasi (zip_sheet_shp).
        if opts.get("export_shp"):
            parcel_ids = sheet_parcel_ids(ids, ket_by_id)
            shp_path_g = os.path.join(
                output_dir, sheet_shp_filename(batch, group.id, group.scale)
            )
            _p, _n = export_parcels_shp(
                layer, shp_path_g, log, pk_col=pk_col,
                feature_ids=set(parcel_ids), skip_empty=True,
            )
            if _p:
                zip_path_g, _nz = zip_sheet_shp(_p, log)
                # Artefak SHP per lembar = ZIP-nya; bila ZIP gagal,
                # file .shp lepas tetap dipakai sebagai fallback.
                shp_paths.append(zip_path_g if zip_path_g else _p)

    layer.setSubsetString("")
    zip_path = None
    if (opts.get("output_format") or "pdf").lower() == "zip" and pdfs:
        zip_path = os.path.join(output_dir, "PBTF_{}.zip".format(batch))
        zip_pdfs(pdfs, zip_path)
        log("ZIP: {} ({:.0f} KB)".format(
            os.path.basename(zip_path), os.path.getsize(zip_path) / 1024.0
        ))

    # Daftarkan layout ke proyek agar bisa dibuka dari Layout Manager.
    manager = project.layoutManager()
    layout_name = "PBTF {}".format(batch)
    existing = manager.layoutByName(layout_name)
    if existing is not None:
        manager.removeLayout(existing)
    layout.setName(layout_name)
    manager.addLayout(layout)
    log("Layout '{}' terdaftar di Layout Manager".format(layout_name))

    # Proyek QGIS (.qgs) berisi SEMUA lembar sebagai layout — bisa dibuka
    # dan diedit di QGIS sebelum diekspor ke PDF.
    qgs_path = None
    if opts.get("save_qgs", True):
        qgs_path = _build_qgs_project(
            opts, groups, boxes, fields, pk_col, dividers, frame,
            divider_geoms=div_geoms,
        )
    return {"pdfs": pdfs, "zip": zip_path, "qgs": qgs_path, "shp": shp_paths, "groups": groups, "warnings": warnings}


def render_preview(opts, dpi=96):
    """Preview TANPA KUOTA (v0.6.2): grouping + bangun proyek .qgs
    (jalur yang sama dengan render_batch) + export SATU PNG resolusi
    rendah per lembar dari layout yang sudah dibangun.

    TIDAK menulis PDF final, TIDAK membuat ZIP, dan TIDAK menyentuh
    lisensi sama sekali (modul ini tidak mengimpor license — tidak
    ada jalur kode dari sini ke consume_generate; kuota hanya dipakai
    bila pengguna menekan Generate di dialog preview). Proyek QGIS
    instance pengguna TIDAK disentuh (layout dibangun di proyek
    terpisah lewat _build_qgs_project, sama seperti .qgs Generate).

    opts: sama seperti render_batch (gpkg_path, layer_name, qpt_path,
    ecw_path, scale, parcel_color, text_color, with_imagery,
    without_imagery, date, pbt_number, block, logo_path, surveyor_path,
    leader_path, first_sheet_only, log). output_dir DIABAIKAN — PNG +
    .qgs preview ditulis ke folder temp baru (temp_dir) yang dikembalikan
    supaya pemanggil bisa menghapusnya setelah dialog ditutup.
    Mengembalikan dict {images, groups, qgs, warnings, metrics,
    temp_dir} — images sejajar dengan groups (satu PNG per lembar)."""
    import tempfile

    from qgis.core import QgsLayoutExporter, QgsVectorLayer

    log = opts.get("log") or (lambda msg: None)
    err = validate_requested_scale(opts["scale"])
    if err:
        raise ValueError(err)
    if not opts["with_imagery"] and not opts["without_imagery"]:
        raise ValueError("Pilih minimal satu varian output (dengan citra atau tanpa citra).")
    if opts["with_imagery"] and not opts.get("ecw_path"):
        raise ValueError("Varian 'Dengan citra ECW' dipilih tetapi file ECW belum dipilih.")

    gpkg_path = opts["gpkg_path"]
    layer_name = opts["layer_name"]
    layer = QgsVectorLayer(
        "{}|layername={}".format(gpkg_path, layer_name), layer_name, "ogr"
    )
    if not layer.isValid():
        raise ValueError("Layer GPKG tidak bisa dibuka: {} ({})".format(gpkg_path, layer_name))
    if layer.crs().isGeographic():
        raise ValueError(
            "CRS layer ini geografis (derajat). Reproyeksikan ke CRS proyeksi "
            "metrik (mis. TM-3) sebelum membuat lembar PBT."
        )
    log("Layer dimuat: {} ({} fitur)".format(layer_name, layer.featureCount()))

    pk_col = detect_pk_column(layer)
    boxes, fields = read_feature_boxes(layer, pk_col)
    if not boxes:
        raise ValueError("Tidak ada fitur dengan geometri yang bisa dibaca di layer ini.")
    log("Fitur terbaca: {} (pk: {})".format(len(boxes), pk_col or "fid internal"))
    # Pembagi garis (v0.6.4): layer 'dividers' di GPKG yang sama.
    line_dividers, div_geoms = read_line_dividers(gpkg_path)
    if line_dividers:
        log("Pembagi garis: {} (layer dividers)".format(len(line_dividers)))

    layout = load_layout(opts["qpt_path"])
    map_item = _find_item_by_id_ci(layout, "Map 1")
    if map_item is None:
        from qgis.core import QgsLayoutItemMap

        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                map_item = item
                break
    if map_item is None:
        raise ValueError("Item peta 'Map 1' tidak ditemukan di template QPT.")
    rect = map_item.rect()
    map_mm = (rect.width(), rect.height())

    groups = group_feature_boxes(list(boxes) + line_dividers, opts["scale"], map_mm)
    log("Grouping: {} lembar ({})".format(
        len(groups), ", ".join(str(len(g.feature_ids)) for g in groups)
    ))
    if opts.get("first_sheet_only"):
        groups = groups[:1]
        log("Mode uji: hanya lembar pertama")

    metrics = sheet_group_metrics(groups, boxes, map_mm)
    warnings = []
    for g in groups:
        warnings.extend(g.warnings)

    dividers = [b for b in boxes if is_special_ket(b.ket) and b.rings] + line_dividers
    frame = _frame_values(opts)
    temp_dir = tempfile.mkdtemp(prefix="yuk-pbt-preview-")
    preview_opts = dict(opts)
    preview_opts["output_dir"] = temp_dir
    qgs_path, project = _build_qgs_project(
        preview_opts, groups, boxes, fields, pk_col, dividers, frame,
        divider_geoms=div_geoms, return_project=True,
    )

    # Export PNG per layout (layout dibangun _build_qgs_project dengan
    # nama "PBTF {batch} {group.id}" — cari per grup supaya urutan
    # images sejajar dengan groups, apa pun urutan layoutManager).
    by_name = {}
    for lay in project.layoutManager().layouts():
        by_name[lay.name()] = lay
    batch = batch_code(gpkg_path)
    images = []
    for group in groups:
        lay = by_name.get("PBTF {} {}".format(batch, group.id))
        if lay is None:
            raise ValueError(
                "Layout preview lembar {} tidak ditemukan di proyek.".format(group.id)
            )
        img_path = os.path.join(temp_dir, "preview_{}.png".format(group.id))
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi
        exporter = QgsLayoutExporter(lay)
        result = exporter.exportToImage(img_path, settings)
        success_code = getattr(QgsLayoutExporter, "Success", None)
        if success_code is None:
            success_code = getattr(
                QgsLayoutExporter.ExportResult, "Success", 0
            )
        if result != success_code or not (
            os.path.exists(img_path) and os.path.getsize(img_path) > 0
        ):
            raise ValueError(
                "Preview lembar {} gagal (kode {}).".format(group.id, result)
            )
        images.append(img_path)
        log("Preview: {} ({:.0f} KB)".format(
            os.path.basename(img_path), os.path.getsize(img_path) / 1024.0
        ))
    return {
        "images": images,
        "groups": groups,
        "qgs": qgs_path,
        "warnings": warnings,
        "metrics": metrics,
        "temp_dir": temp_dir,
    }
