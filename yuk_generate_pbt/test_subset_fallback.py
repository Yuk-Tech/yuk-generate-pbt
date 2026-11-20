#!/usr/bin/env python3
"""Uji fallback subset di sandbox (QGIS 3.22).

Mensimulasikan dua cara subset gagal diam-diam (lembar kosong tanpa
error, seperti yang terjadi di QGIS 4.2.2 Derana):
  B. subset SQL valid tapi 0 cocok — id fitur digeser +10000.
  C. subset SQL invalid — kolom pk salah ('NAMA') sehingga nilai string
     tak dikutip -> GDAL gagal prepare (syntax error).
Yang diuji per mode: render_batch mencatat PERINGATAN, fallback
(coba 'fid', lalu lepas subset) tetap menghasilkan PDF lembar pertama
yang berisi persil (dicek via pratinjau PNG). Jalur normal (A) tidak
boleh memicu PERINGATAN.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def render_first_sheet(args, log_lines):
    return engine.render_batch(
        {
            "gpkg_path": args.gpkg,
            "layer_name": "PBT_2091",
            "qpt_path": args.qpt,
            "ecw_path": None,
            "output_dir": args.out,
            "scale": "1:500",
            "parcel_color": "Hijau",
            "text_color": "Abu gelap",
            "with_imagery": False,
            "without_imagery": True,
            "output_format": "pdf",
            "date": "20 November 2026",
            "pbt_number": "2091",
            "block": "004",
            "logo_path": None,
            "surveyor_path": None,
            "leader_path": None,
            "first_sheet_only": True,
            "log": lambda m: log_lines.append(m),
        }
    )


def preview_png(args, group, layer, out_path):
    from qgis.core import (
        QgsExpressionContextUtils,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsRectangle,
    )
    import re as _re

    layout = engine.load_layout(args.qpt)
    map_item = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            map_item = item
            break
    map_item.setExtent(QgsRectangle(*group.extent))
    map_item.setLayers([layer])
    QgsExpressionContextUtils.setLayoutVariables(
        layout,
        {"tgl": "20 November 2026", "tglF": "20 November 2026",
         "pbt": "2091", "b": "004", "lembar": "1"},
    )
    engine._apply_label_values(
        layout,
        {"tgl": "20 November 2026", "tglF": "20 November 2026",
         "pbt": "2091", "b": "004", "lembar": "1"},
    )
    for item in layout.items():
        if isinstance(item, QgsLayoutItemLabel) and "map_scale" in item.text():
            text = item.text()
            m = _re.search(r"\[%.*?map_scale.*?%\]", text, _re.S)
            if m:
                item.setText(text[: m.start()] + group.scale + text[m.end():])
    img_settings = QgsLayoutExporter.ImageExportSettings()
    img_settings.dpi = 150
    exporter = QgsLayoutExporter(layout)
    res = exporter.exportToImage(out_path, img_settings)
    print("PNG:", out_path, os.path.getsize(out_path), "B, result:", res)


def check_fallback(tag, log_lines, result, args, png_name):
    from qgis.core import QgsProject

    warn = [m for m in log_lines if "PERINGATAN" in m]
    print(tag, ": PDF", result["pdfs"])
    for m in warn:
        print("  LOG:", m)
    assert result["pdfs"] and os.path.getsize(result["pdfs"][0]) > 50_000, tag + " PDF kosong"
    assert warn, tag + " harus mencatat PERINGATAN"
    assert any("subset dilepas" in m for m in warn), tag + " harus sampai ke lepas-subset"
    layer = QgsProject.instance().mapLayersByName("PBT_2091")[0]
    print(tag, " subset akhir:", repr(layer.subsetString()),
          "| featureCount:", layer.featureCount())
    preview_png(args, result["groups"][0], layer,
                os.path.join(args.out, png_name))


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--qpt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from qgis.core import Qgis, QgsApplication, QgsProject

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        print("QGIS_VERSION:", Qgis.QGIS_VERSION)
        # A. Jalur normal: subset benar -> tanpa PERINGATAN.
        log_a = []
        res_a = render_first_sheet(args, log_a)
        warn_a = [m for m in log_a if "PERINGATAN" in m]
        print("A normal: PDF", res_a["pdfs"], "PERINGATAN:", warn_a)
        assert res_a["pdfs"] and os.path.getsize(res_a["pdfs"][0]) > 50_000
        assert not warn_a, "jalur normal tidak boleh memicu PERINGATAN"

        # B. Subset valid tapi 0 cocok: geser semua id +10000.
        QgsProject.instance().clear()
        orig_read = engine.read_feature_boxes

        def read_offset(layer, pk_col):
            boxes, fields = orig_read(layer, pk_col)
            # FeatureBox.id adalah string angka -> geser +10000.
            for b in boxes:
                try:
                    b.id = str(int(b.id) + 10000)
                except (TypeError, ValueError):
                    pass
            return boxes, fields

        engine.read_feature_boxes = read_offset
        log_b = []
        res_b = render_first_sheet(args, log_b)
        engine.read_feature_boxes = orig_read
        check_fallback("B 0-cocok", log_b, res_b, args, "L01-subset-fallback-B.png")

        # C. Subset SQL invalid: kolom pk 'NAMA' (nilai string tak dikutip).
        QgsProject.instance().clear()
        engine.detect_pk_column = lambda layer: "NAMA"
        log_c = []
        res_c = render_first_sheet(args, log_c)
        check_fallback("C SQL-invalid", log_c, res_c, args, "L01-subset-fallback-C.png")

        print("SUBSET FALLBACK: LULUS (A normal + B 0-cocok + C SQL-invalid)")
        sys.stdout.flush()
        os._exit(0)
    finally:
        try:
            QgsProject.instance().clear()
            qgs.exitQgis()
        except Exception:
            pass


if __name__ == "__main__":
    main()
