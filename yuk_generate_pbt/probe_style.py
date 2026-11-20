"""Probe diagnostik gaya + variabel layout di sandbox (QGIS 3.22).

Menjawab dua hal dari render L01:
  1. Kenapa isian persil biru (0,0,255) padahal simbol ELSE transparan?
  2. Kenapa variabel layout [%"pbt"%] tampil literal (tidak ter-evaluasi)?
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
        QgsProject,
        QgsVectorLayer,
    )
    from qgis.core import Qgis

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        print("QGIS:", Qgis.QGIS_VERSION, flush=True)
        layer = QgsVectorLayer(
            "/tmp/poc/PBT_2091.gpkg|layername=PBT_2091", "PBT_2091", "ogr"
        )
        assert layer.isValid()
        fields = [f.name() for f in layer.fields()]
        engine.apply_parcel_style(layer, (0, 176, 80), (35, 35, 35), fields, 500.0)
        renderer = layer.renderer()
        print("renderer type:", renderer.type(), flush=True)
        root = renderer.rootRule()
        for rule in root.children():
            print("RULE label={!r} filter={!r} isElse={}".format(
                rule.label(), rule.filterExpression(), rule.isElse()), flush=True)
            sym = rule.symbol()
            print("  symbol type:", sym.type(), "layers:", sym.symbolLayerCount(), flush=True)
            for li in range(sym.symbolLayerCount()):
                sl = sym.symbolLayer(li)
                print("  layer {}: class={} props={}".format(
                    li, sl.layerType(), sl.properties()), flush=True)
                sub = getattr(sl, "subSymbol", lambda: None)()
                if sub is not None:
                    print("    subSymbol: type={} layers={}".format(
                        sub.type(), sub.symbolLayerCount()), flush=True)
                    for si in range(sub.symbolLayerCount()):
                        ssl = sub.symbolLayer(si)
                        print("    sublayer {}: class={} props={}".format(
                            si, ssl.layerType(), ssl.properties()), flush=True)
        # Evaluasi filter pada satu persil (fid 1) dan satu pembagi (fid 6)
        feats = {f.id(): f for f in layer.getFeatures()}
        for fid in (1, 6):
            feat = feats[fid]
            ctx = QgsExpressionContext()
            ctx.setFeature(feat)
            for name, expr_text in (
                ("road", engine.ket_ilike_expr("KET", engine.ROAD_WORDS)),
                ("water", engine.ket_ilike_expr("KET", engine.WATER_WORDS)),
            ):
                expr = QgsExpression(expr_text)
                val = expr.evaluate(ctx)
                print("fid {} KET={!r} filter {} -> {} (err={!r})".format(
                    fid, feat.attribute("KET"), name, val, expr.evalErrorString()), flush=True)
        # Variabel layout
        layout = engine.load_layout("/tmp/poc/PBTF_WARDOY.qpt")
        QgsExpressionContextUtils.setLayoutVariables(
            layout, {"tgl": "20 November 2026", "tglF": "20 November 2026",
                     "pbt": "2091", "b": "004", "lembar": "1"}
        )
        print("layoutVariables read-back:", QgsExpressionContextUtils.layoutVariables(layout), flush=True)
        print("customProperties:", layout.customProperties().keys(), flush=True)
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.layoutScope(layout))
        for expr_text in ('"pbt"', '"lembar"', '"tglF"'):
            expr = QgsExpression(expr_text)
            print("expr {} -> {!r} (err={!r})".format(
                expr_text, expr.evaluate(ctx), expr.evalErrorString()), flush=True)
        # Label item pertama yang mengandung pbt — apa isi text-nya setelah load?
        for item in layout.items():
            try:
                from qgis.core import QgsLayoutItemLabel
                if isinstance(item, QgsLayoutItemLabel) and "pbt" in item.text():
                    print("LABEL pbt text: {!r}".format(item.text()), flush=True)
                    break
            except Exception:
                continue
        print("PROBE SELESAI", flush=True)
    finally:
        QgsProject.instance().clear()
        qgs.exitQgis()


if __name__ == "__main__":
    main()
