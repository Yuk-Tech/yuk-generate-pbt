#!/usr/bin/env python3
"""Uji render DENGAN citra (raster opaque) di sandbox (QGIS 3.22).

Tujuan: memastikan urutan layer di map_item.setLayers() benar — persil
harus tergambar DI ATAS citra, bukan tertutup raster opaque.
Membuat GeoTIFF tan solid menutupi bbox GPKG (pengganti ECW — sandbox
tidak punya driver ECW), lalu render lembar pertama varian CITRA dan
ekspor 2 pratinjau PNG: A = [layer, raster] (urutan engine saat ini),
B = [raster, layer] (urutan terbalik). Bandingkan dengan mata.

Jalankan di sandbox dengan:
  LD_LIBRARY_PATH=/lib/x86_64-linux-gnu PYTHONHOME=/usr \
  PYTHONPATH=/usr/lib/python3/dist-packages QT_QPA_PLATFORM=offscreen \
  python3 -u test_citra.py --gpkg /tmp/poc/PBT_2091.gpkg \
  --qpt /tmp/poc/PBTF_WARDOY.qpt --out /tmp/poc/out
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def make_tan_tiff(path, bbox, epsg=23834):
    """GeoTIFF RGB solid (230,180,120) menutupi bbox, 1 m/px."""
    from osgeo import gdal, osr

    xmin, ymin, xmax, ymax = bbox
    w = max(10, int(round(xmax - xmin)))
    h = max(10, int(round(ymax - ymin)))
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(path, w, h, 3, gdal.GDT_Byte)
    ds.SetGeoTransform((xmin, 1.0, 0.0, ymax, 0.0, -1.0))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)
    ds.SetProjection(srs.ExportToWkt())
    import numpy as np

    for band, val in ((1, 230), (2, 180), (3, 120)):
        ds.GetRasterBand(band).WriteArray(
            np.full((h, w), val, dtype=np.uint8)
        )
    ds.FlushCache()
    ds = None
    print("TIFF citra:", path, w, "x", h, "px,", os.path.getsize(path), "B")


def preview_png(layout_qpt, group, layer, raster, order, out_path, scale="1:500"):
    from qgis.core import (
        QgsExpressionContextUtils,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsRectangle,
    )
    import re as _re

    layout = engine.load_layout(layout_qpt)
    map_item = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            map_item = item
            break
    map_item.setExtent(QgsRectangle(*group.extent))
    map_item.setLayers(order)
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
                item.setText(text[: m.start()] + scale + text[m.end():])
    img_settings = QgsLayoutExporter.ImageExportSettings()
    img_settings.dpi = 150
    exporter = QgsLayoutExporter(layout)
    res = exporter.exportToImage(out_path, img_settings)
    print("PNG:", out_path, os.path.getsize(out_path), "B, result:", res)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--qpt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from qgis.core import (
        Qgis,
        QgsApplication,
        QgsProject,
        QgsRasterLayer,
        QgsVectorLayer,
    )

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        print("QGIS_VERSION:", Qgis.QGIS_VERSION)
        layer = QgsVectorLayer(
            "{}|layername=PBT_2091".format(args.gpkg), "PBT_2091", "ogr"
        )
        assert layer.isValid(), "GPKG tidak bisa dibuka"
        pk = engine.detect_pk_column(layer)
        boxes, fields = engine.read_feature_boxes(layer, pk)
        assert len(boxes) == 124, "harus 124 fitur"
        bbox = (
            min(b[0] for b in [x.bbox for x in boxes]),
            min(b[1] for b in [x.bbox for x in boxes]),
            max(b[2] for b in [x.bbox for x in boxes]),
            max(b[3] for b in [x.bbox for x in boxes]),
        )
        tiff = os.path.join(args.out, "citra-tan.tif")
        make_tan_tiff(tiff, bbox)
        raster = QgsRasterLayer(tiff, "ECW", "gdal")
        assert raster.isValid(), "TIFF citra tidak bisa dibuka"
        print("raster valid:", raster.isValid(), "CRS:", raster.crs().authid())

        result = engine.render_batch(
            {
                "gpkg_path": args.gpkg,
                "layer_name": "PBT_2091",
                "qpt_path": args.qpt,
                "ecw_path": tiff,
                "output_dir": args.out,
                "scale": "1:500",
                "parcel_color": "Hijau",
                "text_color": "Abu gelap",
                "with_imagery": True,
                "without_imagery": False,
                "output_format": "pdf",
                "date": "20 November 2026",
                "pbt_number": "2091",
                "block": "004",
                "logo_path": None,
                "surveyor_path": None,
                "leader_path": None,
                "first_sheet_only": True,
                "log": print,
            }
        )
        print("PDF CITRA:", result["pdfs"])
        assert result["pdfs"], "tidak ada PDF CITRA"
        assert os.path.getsize(result["pdfs"][0]) > 50_000, "PDF CITRA terlalu kecil"

        group0 = result["groups"][0]
        layer2 = QgsProject.instance().mapLayersByName("PBT_2091")[0]
        raster2 = QgsProject.instance().mapLayersByName("ECW")[0]
        layer2.setSubsetString(
            '"{}" IN ({})'.format(pk, ",".join(str(i) for i in group0.feature_ids))
        )
        preview_png(args.qpt, group0, layer2, raster2,
                    [layer2, raster2],
                    os.path.join(args.out, "L01-citra-A.png"))
        preview_png(args.qpt, group0, layer2, raster2,
                    [raster2, layer2],
                    os.path.join(args.out, "L01-citra-B.png"))
        print("CITRA: SELESAI — bandingkan A ([layer, raster]) vs B ([raster, layer])")
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
