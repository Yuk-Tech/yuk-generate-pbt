#!/usr/bin/env python3
"""Uji murni v0.7.5 (tanpa QGIS): gabung potongan pembagi poligon.

Model (Derana 2026-11-27): persil jalan/sungai yang dipotong
pendek-pendek saat disetorkan terpisah-pisah di GPKG; potongan yang
KET-nya sama DAN bersentuhan adalah satu jalan yang nyambung dan harus
digabung (union) sebelum _open_ring + trim, supaya garis potongan di
sambungan tidak ikut kegambar. Ujung yang tidak menyentuh potongan
se-KET lain = mentok beneran (tetap sendiri). Dua jalan paralel
terpisah (jarak > MERGE_TOL_M) dan KET berbeda tidak digabung.

Yang diuji di sini: _rings_min_dist + _group_touching_divider_polys
(logika pengelompokan murni). Union geometri (QgsGeometry.combine)
butuh QGIS — diverifikasi lewat render sandbox (TEST-PBT-277).
"""
import sys

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


# Strip 10x2 m; B berbagi tepi kanan A; C berbagi tepi kanan B (rantai);
# D paralel 8 m di atas A; E celah 0,03 m dari A (<= MERGE_TOL_M);
# F celah 0,98 m dari A (> MERGE_TOL_M; pasangan se-KET terdekat yang
# BUKAN sambungan di PBT_2091 adalah 0,98 m — IRIGASI 20-89).
A = [(0, 0), (10, 0), (10, 2), (0, 2), (0, 0)]
B = [(10, 0), (20, 0), (20, 2), (10, 2), (10, 0)]
C = [(20, 0), (30, 0), (30, 2), (20, 2), (20, 0)]
D = [(0, 10), (10, 10), (10, 12), (0, 12), (0, 10)]
E = [(10.03, 0), (20.03, 0), (20.03, 2), (10.03, 2), (10.03, 0)]
F = [(10.98, 0), (20.98, 0), (20.98, 2), (10.98, 2), (10.98, 0)]


def test_rings_min_dist():
    check("jarak cincin berbagi tepi = 0",
          engine._rings_min_dist([A], [B]) == 0.0)
    check("jarak cincin paralel 8 m",
          abs(engine._rings_min_dist([A], [D]) - 8.0) < 1e-9)
    check("jarak cincin celah 0,03 m",
          abs(engine._rings_min_dist([A], [E]) - 0.03) < 1e-9)
    check("jarak cincin celah 0,98 m",
          abs(engine._rings_min_dist([A], [F]) - 0.98) < 1e-9)


def test_group_shared_edge():
    # A+B se-KET berbagi tepi -> satu grup.
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("B", "JALAN", [B])], engine.MERGE_TOL_M)
    check("dua potongan berbagi tepi se-KET: satu grup", res == [["A", "B"]])


def test_group_diff_ket():
    # A+B berbagi tepi tapi KET beda (jalan vs sungai di persimpangan)
    # -> tidak digabung.
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("B", "IRIGASI", [B])], engine.MERGE_TOL_M)
    check("berbagi tepi tapi KET beda: dua grup", res == [["A"], ["B"]])


def test_group_parallel_separate():
    # A+D paralel 8 m, KET sama -> tidak digabung.
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("D", "JALAN", [D])], engine.MERGE_TOL_M)
    check("dua jalan paralel terpisah: dua grup", res == [["A"], ["D"]])


def test_group_chain_transitive():
    # A-B-C rantai (A menyentuh B, B menyentuh C, A tidak menyentuh C)
    # -> satu grup (transitif).
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("B", "JALAN", [B]), ("C", "JALAN", [C])],
        engine.MERGE_TOL_M)
    check("rantai 3 potongan: satu grup", res == [["A", "B", "C"]])


def test_group_small_gap():
    # Celah 0,03 m <= MERGE_TOL_M (0,05) -> satu grup (toleransi
    # noise digitasi).
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("E", "JALAN", [E])], engine.MERGE_TOL_M)
    check("celah 0,03 m (<= tol): satu grup", res == [["A", "E"]])


def test_group_big_gap():
    # Celah 0,98 m > MERGE_TOL_M (0,05) -> dua grup (bukan sambungan).
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A]), ("F", "JALAN", [F])], engine.MERGE_TOL_M)
    check("celah 0,98 m (> tol): dua grup", res == [["A"], ["F"]])


def test_group_singleton_and_empty():
    res = engine._group_touching_divider_polys(
        [("A", "JALAN", [A])], engine.MERGE_TOL_M)
    check("satu potongan: grup sendiri", res == [["A"]])
    check("kosong: []",
          engine._group_touching_divider_polys([], engine.MERGE_TOL_M) == [])


if __name__ == "__main__":
    test_rings_min_dist()
    test_group_shared_edge()
    test_group_diff_ket()
    test_group_parallel_separate()
    test_group_chain_transitive()
    test_group_small_gap()
    test_group_big_gap()
    test_group_singleton_and_empty()
    total = 12
    print("test_divider_merge: {}/{} PASS".format(
        total - len(FAILURES), total))
    if FAILURES:
        print("GAGAL:", FAILURES)
        sys.exit(1)
