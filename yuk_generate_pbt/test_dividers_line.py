"""Uji murni (tanpa QGIS) untuk pembagi garis v0.6.4.

- parse_width_mm: koma/titik/'mm' ditoleransi, gagal -> default 0.5.
- Pembagi garis (FeatureBox.lines) BUKAN persil: tidak masuk grouping
  persil, tapi dipakai detect_blocks sebagai pemisah blok.
- point_lines_dist TIDAK menutup garis (tanpa segmen penutup):
  jarak ke garis A-B-C tidak memakai diagonal C->A.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def test_parse_width_mm():
    assert engine.parse_width_mm("0,5") == 0.5
    assert engine.parse_width_mm("0.25") == 0.25
    assert engine.parse_width_mm("1") == 1.0
    assert engine.parse_width_mm("1,5 mm") == 1.5
    assert engine.parse_width_mm("xx") == 0.5
    assert engine.parse_width_mm("") == 0.5
    assert engine.parse_width_mm(None) == 0.5


def test_point_lines_dist_no_wrap():
    # Garis A(0,0)-B(10,0)-C(10,10). Titik (0,10): jarak ke segmen
    # nyata = 10 (ke A-B maupun B-C); diagonal penutup C->A (y=x)
    # akan memberi 7.07 — itu yang TIDAK boleh terjadi.
    d = engine.point_lines_dist(0, 10, [[(0, 0), (10, 0), (10, 10)]])
    assert abs(d - 10.0) < 1e-9, d
    assert engine.point_lines_dist(15, 5, [[(15, 0), (15, 10)]]) == 0.0


def test_line_divider_not_a_parcel():
    p1 = engine.FeatureBox(1, [0, 0, 10, 10], [[(0, 0), (10, 0), (10, 10), (0, 10)]], None)
    p2 = engine.FeatureBox(2, [20, 0, 30, 10], [[(20, 0), (30, 0), (30, 10), (20, 10)]], None)
    div = engine.FeatureBox("div:1", [15, 0, 15, 10], [], "JALAN", lines=[[(15, 0), (15, 10)]])
    groups = engine.group_feature_boxes([p1, p2, div], "1:1000", (200.0, 140.0))
    assert sum(len(g.feature_ids) for g in groups) == 2
    assert not any("div:1" in g.feature_ids for g in groups)


def test_detect_blocks_line_divider():
    # Dua persil bersebelahan (tanpa celah): tanpa pembagi = 1 blok,
    # dengan garis pembagi di antaranya = 2 blok.
    p1 = engine.FeatureBox(1, [0, 0, 10, 10], [[(0, 0), (10, 0), (10, 10), (0, 10)]], None)
    p2 = engine.FeatureBox(2, [10, 0, 20, 10], [[(10, 0), (20, 0), (20, 10), (10, 10)]], None)
    assert len(engine.detect_blocks([p1, p2], [])) == 1
    div = engine.FeatureBox("div:1", [10, 0, 10, 10], [], "JALAN", lines=[[(10, 0), (10, 10)]])
    assert len(engine.detect_blocks([p1, p2], [div])) == 2


if __name__ == "__main__":
    test_parse_width_mm()
    test_point_lines_dist_no_wrap()
    test_line_divider_not_a_parcel()
    test_detect_blocks_line_divider()
    print("test_dividers_line: 4/4 PASS")
