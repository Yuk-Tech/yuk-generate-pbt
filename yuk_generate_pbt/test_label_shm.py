#!/usr/bin/env python3
"""Uji murni v0.6.6 (tanpa QGIS): label persil SHM hanya NIB + No Hak.

- label_expression: persil SHM (080203 terisi) -> NIB + No Hak saja
  (2 baris); No SU (080202) tidak dipakai lagi di mana pun.
- label_fits: tinggi label memakai label_lines (3 biasa, 2 SHM).
"""
import sys

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


def test_expression_shm_branch():
    fields = ["080201", "NAMA", "LUAS", "M2", "080202", "080203", "KET"]
    expr = engine.label_expression(fields)
    assert expr is not None
    check("expr ada 080203 (No Hak)", '"080203"' in expr)
    check("expr TIDAK ada 080202 (No SU dihapus)", '"080202"' not in expr)
    check("expr ada NAMA", '"NAMA"' in expr)
    check("expr ada 080201 (NIB)", '"080201"' in expr)
    check("expr ada cabang SHM (case when 080203 terisi)",
          "case when coalesce(\"080203\", '') != ''" in expr)


def test_expression_without_hak():
    fields = ["080201", "NAMA", "LUAS", "KET"]
    expr = engine.label_expression(fields)
    assert expr is not None
    check("tanpa field: 080203 tidak ada", '"080203"' not in expr)
    check("tanpa field: tidak ada cabang SHM",
          "coalesce(\"080203\", '') != ''" not in expr)
    check("tanpa field: NIB tetap ada", '"080201"' in expr)


def test_label_fits_lines():
    # Persil 20x3 m di 1:500: kertas 40x6 mm, batas tinggi 5,1 mm.
    # 2 baris = 4,23 mm (muat), 3 baris = 6,35 mm (tidak muat).
    b2 = engine.FeatureBox(1, [0, 0, 20, 3], [], None,
                           label_len=10, label_lines=2)
    b3 = engine.FeatureBox(2, [0, 0, 20, 3], [], None,
                           label_len=10, label_lines=3)
    check("2 baris (SHM) muat di 1:500", engine.label_fits(b2, 500))
    check("3 baris tidak muat di 1:500 (persil 20x3)",
          not engine.label_fits(b3, 500))
    check("default label_lines = 3",
          engine.FeatureBox(3, [0, 0, 20, 10], [], None).label_lines == 3)


if __name__ == "__main__":
    test_expression_shm_branch()
    test_expression_without_hak()
    test_label_fits_lines()
    print("test_label_shm: {}/{} PASS".format(
        10 - len(FAILURES), 10))
    if FAILURES:
        print("GAGAL:", FAILURES)
        sys.exit(1)
