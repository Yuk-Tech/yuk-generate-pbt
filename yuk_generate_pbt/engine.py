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
- labeling 3 baris single-expression (NAMA / NIB / L=...m2), satu warna,
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
  ditulis ke label layout (v0.3.0).
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


def parcel_color_rgb(name):
    """Palet bernama — sama dengan parcel_color_rgb() di Rust."""
    key = (name or "").strip().lower()
    table = {
        "putih": (255, 255, 255),
        "white": (255, 255, 255),
        "merah": (228, 26, 28),
        "red": (228, 26, 28),
        "ungu": (255, 0, 255),
        "magenta": (255, 0, 255),
        "purple": (255, 0, 255),
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
    return table.get(key, (0, 176, 80))  # hijau = default


def text_color_rgb(name):
    if not name:
        return (35, 35, 35)
    return parcel_color_rgb(name)


# ---------------------------------------------------------------------------
# Struktur data pengelompokan
# ---------------------------------------------------------------------------


class FeatureBox:
    """Satu fitur: id (pk sebagai string), bbox, cincin poligon, KET."""

    __slots__ = ("id", "bbox", "rings", "ket")

    def __init__(self, fid, bbox, rings, ket):
        self.id = str(fid)
        self.bbox = list(bbox)
        self.rings = rings
        self.ket = ket

    def center(self):
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )


class Acc:
    __slots__ = ("ids", "bbox")

    def __init__(self, ids, bbox):
        self.ids = list(ids)
        self.bbox = list(bbox)


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
            accs.append(Acc([feature.id], feature.bbox))
    return accs


def merge_small_accs(accs, map_mm, denominator):
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
            if n <= MAX_FEATURES_PER_SHEET and fits_at(bbox, map_mm, denominator):
                ids = work[i].ids + work[j].ids
                work[j] = Acc(ids, bbox)
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


def group_feature_boxes(features, requested_scale, map_mm):
    err = validate_requested_scale(requested_scale)
    if err:
        raise ValueError(err)
    features = sorted(
        features,
        key=lambda f: (-f.center()[1], f.center()[0], f.id),
    )
    parcels = [f for f in features if not (is_special_ket(f.ket) and f.rings)]
    dividers = [f for f in features if is_special_ket(f.ket) and f.rings]
    if not parcels:
        raise ValueError("Tidak ada fitur untuk dikelompokkan.")
    total = parcels[0].bbox[:]
    for p in parcels[1:]:
        total = union(total, p.bbox)
    if requested_scale == "Auto":
        denominator = next(
            (d for d in OFFICIAL_SCALES if fits_at(total, map_mm, d)),
            OFFICIAL_SCALES[-1],
        )
    else:
        denominator = parse_scale(requested_scale) or 1000.0
    win_w = map_mm[0] / 1000.0 * denominator * FILL_RATIO
    win_h = map_mm[1] / 1000.0 * denominator * FILL_RATIO
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
            accs.append(Acc([f.id for f in cell], merged))
        else:
            accs.extend(greedy_accs(cell, fixed_scale, map_mm))

    accs, small_leftovers = merge_small_accs(accs, map_mm, denominator)
    accs.sort(key=lambda a: (-((a.bbox[1] + a.bbox[3]) / 2.0), (a.bbox[0] + a.bbox[2]) / 2.0))

    width = max(2, len(str(max(1, len(accs)))))
    groups = []
    for index, acc in enumerate(accs):
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
        except AttributeError:
            continue
    return fallback


def _qgis_color(rgb):
    from qgis.PyQt.QtGui import QColor

    return QColor(rgb[0], rgb[1], rgb[2], 255)


def ket_ilike_expr(ket_field, keywords):
    k = 'coalesce("{}", \'\')'.format(ket_field)
    return " OR ".join("{} ILIKE '%{}%'".format(k, w) for w in keywords)


def trim_expression(ket_field):
    road = ket_ilike_expr(ket_field, ROAD_WORDS)
    water = ket_ilike_expr(ket_field, WATER_WORDS)
    return (
        "intersection($geometry, buffer(aggregate(@layer_id, 'collect', "
        "$geometry, filter:= NOT (({}) OR ({}))), {}))".format(
            road, water, TRIM_BUFFER_M
        )
    )


def label_expression(fields):
    """Ekspresi label 3 baris — sama persis dengan default_labeling Rust."""
    by_lower = {f.lower(): f for f in fields}

    def find(wanted):
        return by_lower.get(wanted.lower())

    special = None
    ket = find("KET")
    if ket:
        special = "({}) OR ({})".format(
            ket_ilike_expr(ket, ROAD_WORDS), ket_ilike_expr(ket, WATER_WORDS)
        )
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
    if not lines:
        return None
    return "array_to_string(array_filter(array({}), @element != ''), '\\n')".format(
        ", ".join(lines)
    )


def apply_parcel_style(layer, outline_rgb, text_rgb, fields, denominator):
    """Terapkan renderer aturan + labeling ke QgsVectorLayer (port
    build_project_xml: rule_renderer_polygon + default_labeling)."""
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
    # QGIS 3: QgsWkbTypes.PolygonGeometry == 2 ; QGIS 4: sama (enum stabil).
    is_polygon = geom_type == 2
    ket_field = next((f for f in fields if f.lower() == "ket"), None)

    if is_polygon and ket_field:
        road = ket_ilike_expr(ket_field, ROAD_WORDS)
        water = ket_ilike_expr(ket_field, WATER_WORDS)
        trim = trim_expression(ket_field)

        def gen_symbol(rgb):
            from qgis.core import QgsGeometryGeneratorSymbolLayer

            gen = QgsGeometryGeneratorSymbolLayer.create(
                {
                    "SymbolType": "Fill",
                    "geometryModifier": trim,
                    "units": "MapUnit",
                }
            )
            sub = QgsFillSymbol.createSimple(
                {
                    "color": "255,255,255,0",
                    "outline_color": "{},{},{},255".format(*rgb),
                    "outline_width": "0.5",
                    "outline_width_unit": "MM",
                    "outline_style": "solid",
                }
            )
            gen.setSubSymbol(sub)
            symbol = QgsFillSymbol()
            symbol.changeSymbolLayer(0, gen)
            return symbol

        def parcel_symbol(rgb):
            return QgsFillSymbol.createSimple(
                {
                    "color": "255,255,255,0",
                    "outline_color": "{},{},{},255".format(*rgb),
                    "outline_width": "0.5",
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

        root.appendChild(make_rule(gen_symbol((255, 63, 0)), road, "Jalan / Gang"))
        root.appendChild(
            make_rule(gen_symbol((0, 63, 255)), water, "Sungai / Irigasi / Saluran")
        )
        else_rule = QgsRuleBasedRenderer.Rule(parcel_symbol(outline_rgb))
        else_rule.setLabel("Bidang Tanah")
        # Jadikan rule ELSE: di QGIS 3.22 tidak ada setElse() —
        # setFilterExpression("ELSE") adalah cara kanonisnya (sama seperti
        # yang tertulis di XML: filter="ELSE").
        else_rule.setFilterExpression("ELSE")
        root.appendChild(else_rule)
        layer.setRenderer(renderer)
    else:
        symbol = QgsFillSymbol.createSimple(
            {
                "color": "255,255,255,0",
                "outline_color": "{},{},{},255".format(*outline_rgb),
                "outline_width": "0.5",
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
            settings.textColor = _qgis_color(text_rgb)
            settings.fontFamily = "Arial"
            size = label_font_size_pt(denominator)
            settings.fontSize = size
            try:
                from qgis.core import QgsUnitTypes

                settings.fontSizeUnit = QgsUnitTypes.RenderPoints
            except Exception:
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
                    dd = (
                        'CASE WHEN length("{f}") > 12 THEN greatest(12.0 / '
                        'length("{f}") * {s}, 3) ELSE {s} END'
                    ).format(f=nama, s=size)
                    # QGIS 3.22: tidak ada setDataDefinedProperty (tunggal) —
                    # pola resminya: ambil koleksi, set, kembalikan.
                    props = settings.dataDefinedProperties()
                    props.setProperty(size_key, QgsProperty.fromExpression(dd))
                    settings.setDataDefinedProperties(props)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def read_feature_boxes(layer, pk_col):
    """Baca fitur layer jadi FeatureBox (port load_feature_boxes)."""
    from qgis.core import QgsWkbTypes

    fields = [f.name() for f in layer.fields()]
    ket_field = next((f for f in fields if f.lower() == "ket"), None)
    boxes = []
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        rings = []
        if geom.type() == QgsWkbTypes.PolygonGeometry:
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
        boxes.append(
            FeatureBox(
                fid,
                [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum()],
                rings,
                ket,
            )
        )
    return boxes, fields


def detect_pk_column(layer):
    """Nama kolom primary key (port PRAGMA table_info; fallback 'fid')."""
    try:
        indices = layer.primaryKeyAttributes()
        if indices:
            return layer.fields().at(indices[0]).name()
    except Exception:
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
        except Exception:
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
        except Exception:
            continue
    return snap


def _restore_label_texts(snapshot):
    for item, text in snapshot:
        try:
            item.setText(text)
        except Exception:
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

# Nilai default isi frame = isi template PBTF_WARDOY.qpt saat ini.
FRAME_DEFAULTS = {
    "coord_system": DEFAULT_COORD_SYSTEM,
    "area_kind": "Desa",
    "area_name": "Gudang",
    "admin_kind": "Kabupaten",
    "admin_name": "Cianjur",
    "kecamatan": "Cikalongkulon",
    "provinsi": "Jawa Barat",
    "surveyor_name": "Moch Ikhsan Panca Utama",
    "surveyor_license": "2-1501-19",
    "leader_org": "PT. SANGGA BUANA NUSANTARA",
    "leader_name": "Ir. Rudy Themonady L",
    "leader_position": "Direktur Utama",
    "usage_role": "Wakil Ketua Bidang Fisik",
    "usage_name": "Dede Kuswana S.SIT",
    "usage_nip": "197306141994031002",
    "executor_pt": "PT. SANGGA BUANA NUSANTARA",
    "executor_address": "Jl. Kalibata Timur No. 12 Jakarta Selatan",
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
    """Tulis 9 butir isi frame ke label layout (template PBTF_WARDOY.qpt).

    Label di template tidak punya id — dikenali dari isi teks bawaannya
    (dan posisi y untuk dua label "PT. SANGGA BUANA NUSANTARA" yang
    kembar: y kecil = pimpinan, y besar = pelaksana). Dipanggil pada
    layout yang masih berisi teks template, SEBELUM _apply_label_values,
    supaya token [%"b"%] / [%"tglF"%] di label yang sama tetap utuh dan
    diganti nilainya sesudahnya. Mengembalikan daftar peringatan untuk
    butir yang tidak ketemu (template lain / template sudah diubah).
    """
    from qgis.core import QgsLayoutItemLabel

    def _y(item):
        try:
            return item.rect().top()
        except Exception:
            return 0.0

    labels = []
    for item in layout.items():
        try:
            if isinstance(item, QgsLayoutItemLabel):
                labels.append(item)
        except Exception:
            continue

    # Dua label PT yang kembar — bedakan lewat posisi y.
    pt_items = sorted(
        [it for it in labels if it.text() == "PT. SANGGA BUANA NUSANTARA"],
        key=_y,
    )
    leader_org_item = pt_items[0] if pt_items else None
    executor_pt_item = pt_items[1] if len(pt_items) > 1 else None

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
            elif text == "2-1501-19":
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
            elif text == "NIP. 197306141994031002":
                item.setText("NIP. {}".format(frame["usage_nip"]))
                found.add("usage_nip")
            elif text == "Jl. Kalibata Timur No. 12 Jakarta Selatan":
                item.setText(frame["executor_address"])
                found.add("executor_address")
        except Exception:
            continue
    if leader_org_item is not None:
        try:
            leader_org_item.setText(frame["leader_org"])
            found.add("leader_org")
        except Exception:
            pass
    if executor_pt_item is not None:
        try:
            executor_pt_item.setText(frame["executor_pt"])
            found.add("executor_pt")
        except Exception:
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
        except Exception:
            continue


def _layer_has_features(layer):
    """True bila layer (dengan subset aktif) menghasilkan >=1 fitur.
    featureCount() bisa -1 bila hitung gagal (mis. subset SQL invalid) —
    konfirmasi lewat getFeatures(). Dipakai untuk memverifikasi subset
    per-lembar sebelum render (lihat render_batch)."""
    try:
        if layer.featureCount() > 0:
            return True
    except Exception:
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


def _build_qgs_project(opts, groups, boxes, fields, pk_col, dividers, frame):
    """Bangun SATU proyek QGIS (.qgs) berisi SEMUA lembar sebagai layout.

    Proyek terpisah (bukan QgsProject.instance()) supaya tidak menyentuh
    proyek QGIS user yang sedang terbuka. Tiap lembar mendapat layer
    vektor sendiri (subset per-lembar — subset adalah properti layer,
    jadi satu layer tidak bisa melayani 10 layout) + layout sendiri dari
    template, dengan isi frame + nilai lembar yang sama seperti PDF.
    Mengembalikan path .qgs (PBTF_{batch}.qgs di folder output)."""
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

    raster = None
    if opts["with_imagery"]:
        raster = QgsRasterLayer(opts["ecw_path"], "ECW", "gdal")
        if not raster.isValid():
            raise ValueError("ECW tidak bisa dibuka: {}".format(opts["ecw_path"]))
        out_project.addMapLayer(raster, False)

    denominator = parse_scale(groups[0].scale) or 1000.0
    outline_rgb = parcel_color_rgb(opts.get("parcel_color") or "hijau")
    text_rgb = text_color_rgb(opts.get("text_color") or "")

    def bboxes_intersect(a, b):
        return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]

    frame_warned = False
    for index, group in enumerate(groups):
        ids = list(group.feature_ids)
        for d in dividers:
            if bboxes_intersect(d.bbox, group.extent):
                ids.append(d.id)
        sheet_layer = QgsVectorLayer(
            source, "{}_{}".format(layer_name, group.id), "ogr"
        )
        if not sheet_layer.isValid():
            raise ValueError("Layer lembar {} tidak bisa dibuat.".format(group.id))
        apply_parcel_style(sheet_layer, outline_rgb, text_rgb, fields, denominator)
        _set_sheet_subset(sheet_layer, pk_col, ids, group.id, log)
        out_project.addMapLayer(sheet_layer, False)

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
        except Exception:
            pass
        map_item.setExtent(QgsRectangle(*group.extent))
        map_item.setLayers(
            [sheet_layer] + ([raster] if opts["with_imagery"] and raster else [])
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
            except Exception:
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
    return qgs_path


def render_batch(opts):
    """Render semua lembar. opts: dict dengan kunci
    gpkg_path, layer_name, qpt_path, ecw_path (atau None), output_dir,
    scale ('Auto'/'1:1000'/...), parcel_color (nama), text_color (nama),
    with_imagery, without_imagery, output_format ('pdf'/'zip'),
    date, pbt_number, block, logo_path, surveyor_path, leader_path,
    log (callable(str) atau None), first_sheet_only (bool).
    Mengembalikan dict {pdfs, zip, qgs, groups, warnings}."""
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
    except Exception:
        pass
    rect = map_item.rect()
    map_mm = (rect.width(), rect.height())
    log("Template dimuat: peta {:.1f} x {:.1f} mm".format(*map_mm))

    groups = group_feature_boxes(list(boxes), opts["scale"], map_mm)
    log("Grouping: {} lembar ({})".format(
        len(groups), ", ".join(str(len(g.feature_ids)) for g in groups)
    ))
    if opts.get("first_sheet_only"):
        groups = groups[:1]
        log("Mode uji: hanya lembar pertama")

    denominator = parse_scale(groups[0].scale) or 1000.0
    outline_rgb = parcel_color_rgb(opts.get("parcel_color") or "hijau")
    text_rgb = text_color_rgb(opts.get("text_color") or "")
    apply_parcel_style(layer, outline_rgb, text_rgb, fields, denominator)
    frame = _frame_values(opts)

    dividers = [b for b in boxes if is_special_ket(b.ket) and b.rings]
    batch = batch_code(gpkg_path)
    output_dir = opts["output_dir"]
    os.makedirs(output_dir, exist_ok=True)

    def bboxes_intersect(a, b):
        return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]

    pdfs = []
    warnings = []
    exporter = QgsLayoutExporter(layout)
    label_snapshot = _snapshot_label_texts(layout)
    for index, group in enumerate(groups):
        warnings.extend(group.warnings)
        ids = list(group.feature_ids)
        for d in dividers:
            if bboxes_intersect(d.bbox, group.extent):
                ids.append(d.id)
        _set_sheet_subset(layer, pk_col, ids, group.id, log)
        map_item.setExtent(QgsRectangle(*group.extent))
        map_item.setLayers([layer] + ([raster] if raster else []))
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
            except Exception:
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
            map_item.setLayers([layer] + ([raster] if with_imagery and raster else []))
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
            opts, groups, boxes, fields, pk_col, dividers, frame
        )
    return {"pdfs": pdfs, "zip": zip_path, "qgs": qgs_path, "groups": groups, "warnings": warnings}
