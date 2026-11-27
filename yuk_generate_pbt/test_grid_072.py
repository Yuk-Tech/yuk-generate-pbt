#!/usr/bin/env python3
"""Uji murni PBT v0.7.2 (tanpa QGIS): grid peta skala-bergantung (opsi B).

- grid_interval_m: interval tanah = denominator x 0,1 m (jarak layout
  tetap 100 mm).
- grid_offsets / grid_line_layout_positions: garis di posisi jangkar
  yang SAMA di semua skala (vertikal [54,30 / 154,30 / 254,30] mm,
  horizontal [38,37 / 138,37 / 238,37] mm dari tepi frame).
- Jangkar PBT = PUSAT frame (50% lebar, 50% tinggi) — ASUMSI (tidak
  ada referensi grid PBT yang bisa diukur; template interval 0).
  Frame PBT 308,594 x 276,749 mm (Map 1 PBTF_WARDOY.qpt).
"""
import sys

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []
COUNT = [0]
MAP_MM = (308.594, 276.749)
EXP_X = [54.30, 154.30, 254.30]
EXP_Y = [38.37, 138.37, 238.37]


def check(name, cond):
    COUNT[0] += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


def close(a, b, tol=0.01):
    return abs(a - b) <= tol


def close_list(got, exp, tol=0.01):
    return (len(got) == len(exp)
            and all(close(g, e, tol) for g, e in zip(sorted(got), sorted(exp))))


def extent_for(denominator, x0=68000.0, y0=1435000.0):
    """Extent yang TEPAT mengisi frame pada skala itu (seperti
    layout_extent dari pusat extent)."""
    w = MAP_MM[0] * denominator / 1000.0
    h = MAP_MM[1] * denominator / 1000.0
    return [x0, y0, x0 + w, y0 + h]


def test_interval():
    cases = [(250, 25.0), (500, 50.0), (1000, 100.0),
             (1500, 150.0), (2000, 200.0), (2500, 250.0)]
    for denom, exp in cases:
        check("interval 1:{} -> {} m".format(denom, exp),
              engine.grid_interval_m(denom) == exp)
    check("interval '1:1000' string -> None (denominator angka)",
          engine.grid_interval_m("1:1000") is None)
    for bad in (0, -100, None, "x"):
        check("interval tidak valid {!r} -> None".format(bad),
              engine.grid_interval_m(bad) is None)


def test_anchor_constants():
    # Jangkar = pusat frame (ASUMSI v0.7.2 — lihat docstring modul grid).
    check("jangkar X = 154,30 (50% lebar frame)",
          close(engine.GRID_ANCHOR_X_MM, 154.30))
    check("jangkar Y = 138,37 (50% tinggi frame)",
          close(engine.GRID_ANCHOR_Y_MM, 138.37))
    check("jarak layout tetap 100 mm",
          engine.GRID_LAYOUT_SPACING_MM == 100.0)


def test_positions_same_across_scales():
    for denom in (250, 500, 1000, 1500, 2000, 2500):
        xs, ys = engine.grid_line_layout_positions(
            extent_for(denom), MAP_MM, denom)
        check("1:{} -> 3 garis vertikal di jangkar".format(denom),
              close_list(xs, EXP_X))
        check("1:{} -> 3 garis horizontal di jangkar".format(denom),
              close_list(ys, EXP_Y))


def test_offsets_in_range():
    for denom in (250, 500, 1000, 1500, 2000, 2500):
        offs = engine.grid_offsets(extent_for(denom), MAP_MM, denom)
        interval = engine.grid_interval_m(denom)
        check("1:{} offset dalam [0, interval)".format(denom),
              offs is not None
              and 0 <= offs[0] < interval
              and 0 <= offs[1] < interval)
    # Kasus 1:1000 yang dihitung tangan: offsetX 54,30, offsetY 38,379.
    offs = engine.grid_offsets(extent_for(1000), MAP_MM, 1000)
    check("1:1000 offsetX = 54,30", close(offs[0], 54.30))
    check("1:1000 offsetY = 38,379", close(offs[1], 38.379, 0.001))


def test_invalid():
    check("offsets denominator 0 -> None",
          engine.grid_offsets(extent_for(1000), MAP_MM, 0) is None)
    check("offsets extent kosong -> None",
          engine.grid_offsets([0, 0, 0, 0], MAP_MM, 1000) is None)
    check("offsets frame 0 -> None",
          engine.grid_offsets(extent_for(1000), (0, 0), 1000) is None)
    check("posisi denominator 0 -> ([], [])",
          engine.grid_line_layout_positions(extent_for(1000), MAP_MM, 0)
          == ([], []))
    check("posisi extent kosong -> ([], [])",
          engine.grid_line_layout_positions([0, 0, 0, 0], MAP_MM, 1000)
          == ([], []))


if __name__ == "__main__":
    test_interval()
    test_anchor_constants()
    test_positions_same_across_scales()
    test_offsets_in_range()
    test_invalid()
    print("---")
    print("TOTAL: {} checks, {} failures".format(COUNT[0], len(FAILURES)))
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(" -", f)
        sys.exit(1)
    print("SEMUA LULUS")
