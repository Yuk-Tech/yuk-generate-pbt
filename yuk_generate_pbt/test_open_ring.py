#!/usr/bin/env python3
"""Uji murni v0.6.7 (tanpa QGIS): _open_ring — buka cincin tertutup
(jalan/sungai poligon) jadi 2 garis terbuka dengan membuang 2 segmen
'tutup ujung' (cap).

Aturan: 2 segmen terpendek yang tidak bersebelahan, masing-masing
< 20% keliling. Bukan strip -> None (cincin tetap tertutup).
"""
import sys

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


def test_rectangle_strip():
    # Strip 100x5 m: sisi 100, 5, 100, 5 -> cap 5 dan 5 dibuang.
    ring = [(0, 0), (100, 0), (100, 5), (0, 5), (0, 0)]
    res = engine._open_ring(ring)
    check("strip persegi: dibuka jadi 2 garis", res is not None and len(res) == 2)
    if res:
        lens = sorted(sum(
            ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for a, b in zip(ln, ln[1:])
        ) for ln in res)
        check("strip persegi: kedua garis 100 m", lens == [100.0, 100.0])
        check("strip persegi: tidak ada garis tertutup",
              all(ln[0] != ln[-1] for ln in res))


def test_bent_road():
    # Jalan berbelok: sisi atas 2 segmen, sisi bawah 2 segmen, cap 4 m.
    ring = [(0, 0), (50, 0), (100, 10), (100, 14), (50, 4), (0, 4), (0, 0)]
    res = engine._open_ring(ring)
    check("jalan berbelok: dibuka jadi 2 garis", res is not None and len(res) == 2)
    if res:
        total = sum(
            ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for ln in res for a, b in zip(ln, ln[1:])
        )
        # Keliling - 2 cap (4 + 4) = total sisi.
        check("jalan berbelok: panjang total = keliling - 2 cap",
              abs(total - (sum(
                  ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
                  for a, b in zip(ring, ring[1:])) - 8.0)) < 1e-6)


def test_square_stays_closed():
    # Persegi 10x10: tiap sisi 25% keliling -> bukan strip.
    ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    check("persegi: tetap tertutup (None)",
          engine._open_ring(ring) is None)


def test_triangle_stays_closed():
    ring = [(0, 0), (10, 0), (5, 8), (0, 0)]
    check("segitiga: tetap tertutup (None)",
          engine._open_ring(ring) is None)


def test_open_polyline_untouched():
    # Bukan cincin (tidak tertutup) -> None.
    pts = [(0, 0), (50, 0), (100, 5)]
    check("polyline terbuka: None", engine._open_ring(pts) is None)
    # Terlalu sedikit titik.
    check("cincin 3 titik: None",
          engine._open_ring([(0, 0), (5, 0), (0, 0)]) is None)


def test_jog_on_side():
    # Sisi panjang punya jog pendek (2 m) — cap (5 m) tetap yang dibuang,
    # bukan jognya. Strip 60x5, jog di tengah sisi atas.
    ring = [(0, 0), (30, 0), (32, 0), (60, 0), (60, 5), (0, 5), (0, 0)]
    res = engine._open_ring(ring)
    check("jog di sisi: tetap dibuka jadi 2 garis",
          res is not None and len(res) == 2)
    if res:
        # Cap 5 m hilang 2x; jog 2 m tetap ada di salah satu garis.
        total = sum(
            ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for ln in res for a, b in zip(ln, ln[1:])
        )
        perim = sum(
            ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            for a, b in zip(ring, ring[1:]))
        check("jog di sisi: total = keliling - 10 (2 cap)",
              abs(total - (perim - 10.0)) < 1e-6)


def _line_len(ln):
    return sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(ln, ln[1:]))


def test_folded_strip_stays_closed():
    # v0.7.4 (loop buntu): strip 100x2 dengan jog kecil (0,5 m) di
    # tengah sisi bawah — jog itu segmen terpendek + belok tajam,
    # jadi kriteria lama salah memilihnya sebagai cap dan membuka
    # cincin jadi garis 203 m + fragmen 1 m (rasio < 1/3). Bukaan
    # seperti itu salah: cincin harus tetap tertutup (None).
    ring = [(0, 0), (50, 0), (50, -0.5), (51, -0.5), (51, 0),
            (100, 0), (100, 2), (0, 2), (0, 0)]
    check("strip ber-jog (hairpin): tetap tertutup (None)",
          engine._open_ring(ring) is None)


def test_unbalanced_opening_rejected():
    # v0.7.4: cincin yang bila dibuka menghasilkan satu garis jauh
    # lebih pendek dari yang lain (< 1/3) harus tetap tertutup.
    # Bentuk: strip panjang dengan spur pendek di ujung — cap yang
    # terpilih memisahkan spur (12 m) dari sisi utama (88 m).
    ring = [(0, 0), (50, 0), (50, 6), (62, 6), (62, 0), (100, 0),
            (100, 2), (62, 2), (62, 4), (50, 4), (50, 2), (0, 2),
            (0, 0)]
    res = engine._open_ring(ring)
    # Apapun cap yang terpilih, bila hasilnya timpang (< 1/3) maka
    # harus None; bila seimbang maka boleh dibuka. Di sini konstruksi
    # menghasilkan bukaan timpang -> None.
    if res is not None:
        lens = sorted(_line_len(ln) for ln in res)
        check("bukaa timpang ditolak: rasio >= 1/3 bila dibuka",
              lens[0] >= (1.0 / 3.0) * lens[1])
    else:
        check("bukaa timpang ditolak: tetap tertutup (None)", True)


if __name__ == "__main__":
    test_rectangle_strip()
    test_bent_road()
    test_square_stays_closed()
    test_triangle_stays_closed()
    test_open_polyline_untouched()
    test_jog_on_side()
    test_folded_strip_stays_closed()
    test_unbalanced_opening_rejected()
    total = 14
    print("test_open_ring: {}/{} PASS".format(total - len(FAILURES), total))
    if FAILURES:
        print("GAGAL:", FAILURES)
        sys.exit(1)
