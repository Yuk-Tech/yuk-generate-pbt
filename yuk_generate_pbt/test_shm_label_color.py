#!/usr/bin/env python3
"""Uji murni v0.7.3 (tanpa QGIS): warna label SHM data-defined.

- shm_label_color_expression: field 080203 ada + shm_rgb diberikan ->
  CASE WHEN coalesce("080203", '') != '' THEN '<hex SHM>' ELSE
  '<hex teks>' END; tanpa field 080203 atau shm_rgb None -> None
  (semua label pakai warna dasar text_rgb, perilaku lama).
- _rgb_hex: (r, g, b) -> '#RRGGBB' huruf besar.
"""
import sys

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


def test_rgb_hex():
    check("ungu FE01AE", engine._rgb_hex((254, 1, 174)) == "#FE01AE")
    check("putih FFFFFF", engine._rgb_hex((255, 255, 255)) == "#FFFFFF")
    check("abu gelap 232323", engine._rgb_hex((35, 35, 35)) == "#232323")
    check("hitam 000000", engine._rgb_hex((0, 0, 0)) == "#000000")
    check("hijau 00FB00", engine._rgb_hex((0, 251, 0)) == "#00FB00")


def test_expr_skenario_derana():
    # Skenario yang dilaporkan Derana: teks Putih + SHM Ungu ->
    # label SHM ungu, label biasa putih.
    fields = ["080201", "NAMA", "LUAS", "M2", "080203", "KET"]
    expr = engine.shm_label_color_expression(fields, (254, 1, 174),
                                             (255, 255, 255))
    assert expr is not None
    check("expr skenario Derana ada",
          expr == "CASE WHEN coalesce(\"080203\", '') != '' "
                  "THEN '#FE01AE' ELSE '#FFFFFF' END")
    check("expr ada cabang SHM (coalesce 080203)",
          "coalesce(\"080203\", '') != ''" in expr)
    check("expr ada hex SHM #FE01AE", "#FE01AE" in expr)
    check("expr ada hex teks #FFFFFF", "#FFFFFF" in expr)


def test_expr_skenario_default():
    # Teks default (Abu gelap) + SHM Ungu -> SHM ungu, biasa abu gelap.
    fields = ["080201", "NAMA", "LUAS", "M2", "080203", "KET"]
    expr = engine.shm_label_color_expression(fields, (254, 1, 174),
                                             (35, 35, 35))
    assert expr is not None
    check("expr default: SHM #FE01AE, biasa #232323",
          expr == "CASE WHEN coalesce(\"080203\", '') != '' "
                  "THEN '#FE01AE' ELSE '#232323' END")


def test_expr_tanpa_field():
    # Tanpa field 080203 -> None (tanpa data-defined, perilaku lama).
    fields = ["080201", "NAMA", "LUAS", "KET"]
    expr = engine.shm_label_color_expression(fields, (254, 1, 174),
                                             (255, 255, 255))
    check("tanpa field 080203 -> None", expr is None)


def test_expr_tanpa_shm_rgb():
    # shm_rgb None (opts tanpa shm_color) -> None.
    fields = ["080201", "NAMA", "LUAS", "M2", "080203", "KET"]
    expr = engine.shm_label_color_expression(fields, None, (255, 255, 255))
    check("shm_rgb None -> None", expr is None)


def test_expr_nama_field_case_insensitive():
    # Nama field "080203" dicari case-insensitive (konsisten dengan
    # label_expression).
    fields = ["080201", "NAMA", "080203"]
    expr = engine.shm_label_color_expression(fields, (254, 1, 174),
                                             (0, 0, 0))
    check("field 080203 dikenali", expr is not None
          and '"080203"' in expr)


if __name__ == "__main__":
    test_rgb_hex()
    test_expr_skenario_derana()
    test_expr_skenario_default()
    test_expr_tanpa_field()
    test_expr_tanpa_shm_rgb()
    test_expr_nama_field_case_insensitive()
    total = 5 + 4 + 1 + 1 + 1 + 1
    print("test_shm_label_color: {}/{} PASS".format(
        total - len(FAILURES), total))
    if FAILURES:
        print("GAGAL:", FAILURES)
        sys.exit(1)
