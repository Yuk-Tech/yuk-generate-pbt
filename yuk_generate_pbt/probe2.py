"""Probe 2: uji hipotesis akar biru + variabel layout.

  A. Apakah simbol root rule (0,0,255) ikut ter-render? Uji: setSymbol(None)
     lalu render L01 ke PNG 72 dpi dan sampling 3 titik.
  B. Apakah setFilterExpression("ELSE") menjadikan rule sebagai else?
  C. Apakah setLayoutVariables() benar-benar menyimpan variabel?
     (QgsExpressionContextUtils.layoutVariables tidak ada di 3.22 —
      baca customProperties + evaluasi '"pbt"' dalam layout scope.)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine  # noqa: E402


def main():
    from qgis.core import (
        QgsApplication,
        QgsExpression,
        QgsExpressionContext,
        QgsExpressionContextUtils,
        QgsLayoutExporter,
        QgsLayoutItemMap,
        QgsProject,
        QgsRectangle,
        QgsVectorLayer,
    )
    from qgis.core import Qgis

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        layer = QgsVectorLayer(
            "/tmp/poc/PBT_2091.gpkg|layername=PBT_2091", "PBT_2091", "ogr"
        )
        assert layer.isValid()
        fields = [f.name() for f in layer.fields()]
        engine.apply_parcel_style(layer, (0, 176, 80), (35, 35, 35), fields, 500.0)
        renderer = layer.renderer()
        root = renderer.rootRule()
        sym = root.symbol()
        print("root symbol:", sym.symbolLayer(0).properties().get("color") if sym else None, flush=True)
        print("has setSymbol:", hasattr(root, "setSymbol"), flush=True)
        # Cari rule Bidang Tanah dan coba jadikan else
        else_rule = None
        for child in root.children():
            if child.label() == "Bidang Tanah":
                else_rule = child
        print("else_rule has setElse:", hasattr(else_rule, "setElse"), flush=True)
        else_rule.setFilterExpression("ELSE")
        print("Bidang Tanah isElse setelah setFilterExpression('ELSE'):", else_rule.isElse(), flush=True)
        root.setSymbol(None)
        print("root symbol sesudah setSymbol(None):", root.symbol(), flush=True)

        # Render L01 ke PNG 72 dpi
        layout = engine.load_layout("/tmp/poc/PBTF_WARDOY.qpt")
        map_item = None
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                map_item = item
                break
        boxes, _ = engine.read_feature_boxes(layer, "fid")
        groups = engine.group_feature_boxes(list(boxes), "1:500", (308.6, 276.7))
        g0 = groups[0]
        print("L01:", len(g0.feature_ids), "bidang", flush=True)
        layer.setSubsetString('"fid" IN ({})'.format(",".join(g0.feature_ids)))
        map_item.setExtent(QgsRectangle(*g0.extent))
        map_item.setLayers([layer])
        QgsExpressionContextUtils.setLayoutVariables(
            layout, {"tgl": "20 November 2026", "tglF": "20 November 2026",
                     "pbt": "2091", "b": "004", "lembar": "1"}
        )
        # C. baca balik variabel (3.22: customProperties() = daftar kunci)
        keys = layout.customProperties()
        print("customProperties keys:", [k for k in keys if "variable" in k.lower()], flush=True)
        for k in keys:
            if "variable" in k.lower():
                print("  {} = {!r}".format(k, layout.customProperty(k)), flush=True)
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.layoutScope(layout))
        for expr_text in ('"pbt"', '"lembar"', '"tglF"', '"b"'):
            expr = QgsExpression(expr_text)
            print("expr {} -> {!r} (err={!r})".format(
                expr_text, expr.evaluate(ctx), expr.evalErrorString()), flush=True)
        # Label pbt: apa isinya?
        for item in layout.items():
            try:
                from qgis.core import QgsLayoutItemLabel
                if isinstance(item, QgsLayoutItemLabel) and "pbt" in item.text():
                    print("LABEL pbt text: {!r}".format(item.text()), flush=True)
                    break
            except Exception:
                continue
        exporter = QgsLayoutExporter(layout)
        png_path = "/tmp/poc/out/L01-probe2.png"
        img_settings = QgsLayoutExporter.ImageExportSettings()
        img_settings.dpi = 72
        result = exporter.exportToImage(png_path, img_settings)
        print("export result:", result, "PNG bytes:", os.path.getsize(png_path), flush=True)
        # Sampling titik (72 dpi -> A3 1191x842; skala dari 150 dpi: /2.083)
        from qgis.PyQt.QtGui import QImage
        img = QImage(png_path)
        print("PNG size:", img.width(), "x", img.height(), flush=True)
        for name, (x, y) in (
            ("EMPAN interior", (720, 504)),
            ("SADILI interior", (432, 216)),
            ("ACUH interior", (144, 480)),
            ("background", (144, 144)),
        ):
            c = img.pixelColor(x, y)
            print("{} ({},{}) -> ({},{},{})".format(name, x, y, c.red(), c.green(), c.blue()), flush=True)
        print("PROBE2 SELESAI", flush=True)
    finally:
        QgsProject.instance().clear()
        qgs.exitQgis()


if __name__ == "__main__":
    main()
