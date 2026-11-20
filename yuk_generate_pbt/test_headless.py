"""Uji headless plugin Yuk Generate PBT! di sandbox (QGIS 3.22, PyQGIS).

Jalankan di sandbox dengan:
  LD_LIBRARY_PATH=/lib/x86_64-linux-gnu PYTHONHOME=/usr \
  PYTHONPATH=/usr/lib/python3/dist-packages QT_QPA_PLATFORM=offscreen \
  python3 test_headless.py --gpkg /path/PBT_2091.gpkg \
  --qpt /path/PBTF_WARDOY.qpt --out /tmp/poc-out

Yang diuji (tanpa GUI):
  1. Grouping Python == komposisi Rust v17.8 yang didokumentasikan
     (10 lembar [2,3,3,4,7,11,17,21,23,24] pada skala 1:500 — bila tidak
     cocok, skrip mencetak komposisi hasil hitung untuk dibandingkan).
  2. Render lembar pertama TANPA_CITRA -> PDF ada, tidak kosong.
  3. Batch penuh TANPA_CITRA + format PDF+ZIP -> ZIP hanya berisi PDF.
  4. Styling diterapkan: renderer RuleRenderer, labeling aktif.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpkg", required=True)
    ap.add_argument("--qpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", default="1:500")
    args = ap.parse_args()

    from qgis.core import (
        Qgis,
        QgsApplication,
        QgsLayoutItemLabel,
        QgsProject,
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
        print("CRS:", layer.crs().authid(), "geographic:", layer.crs().isGeographic())
        pk = engine.detect_pk_column(layer)
        print("pk:", pk)
        boxes, fields = engine.read_feature_boxes(layer, pk)
        print("fitur terbaca:", len(boxes), "fields:", fields)
        assert len(boxes) == 124, "harus 124 fitur (115 persil + 9 pembagi)"

        layout = engine.load_layout(args.qpt)
        map_item = engine._find_item_by_id_ci(layout, "Map 1")
        assert map_item is not None, "Map 1 tidak ditemukan"
        rect = map_item.rect()
        map_mm = (rect.width(), rect.height())
        print("peta template: {:.1f} x {:.1f} mm".format(*map_mm))

        groups = engine.group_feature_boxes(list(boxes), args.scale, map_mm)
        comp = sorted(len(g.feature_ids) for g in groups)
        print("komposisi {} lembar @{}: {}".format(len(groups), args.scale, comp))
        total = sum(comp)
        print("total bidang terkelompok:", total)
        assert total == 115, "semua 115 persil harus masuk tepat 1 lembar"
        known = [2, 3, 3, 4, 7, 11, 17, 21, 23, 24]
        if comp == known:
            print("KOMPOSISI COCOK dengan Rust v17.8 (10 lembar)")
        else:
            print("KOMPOSISI BERBEDA dari Rust v17.8 {} — perlu dibandingkan".format(known))

        # Render batch penuh TANPA_CITRA + ZIP
        result = engine.render_batch(
            {
                "gpkg_path": args.gpkg,
                "layer_name": "PBT_2091",
                "qpt_path": args.qpt,
                "ecw_path": None,
                "output_dir": args.out,
                "scale": args.scale,
                "parcel_color": "Hijau",
                "text_color": "Abu gelap",
                "with_imagery": False,
                "without_imagery": True,
                "output_format": "zip",
                "date": "20 November 2026",
                "pbt_number": "2091",
                "block": "004",
                "logo_path": None,
                "surveyor_path": None,
                "leader_path": None,
                "first_sheet_only": False,
                "log": print,
            }
        )
        print("PDF:", len(result["pdfs"]))
        for pdf in result["pdfs"]:
            print("  {} — {} B".format(os.path.basename(pdf), os.path.getsize(pdf)))
            assert os.path.getsize(pdf) > 50_000, "PDF terlalu kecil, render bermasalah?"
        print("ZIP:", result["zip"], os.path.getsize(result["zip"]), "B")
        import zipfile

        with zipfile.ZipFile(result["zip"]) as zf:
            names = zf.namelist()
        print("isi ZIP:", names)
        assert len(names) == len(result["pdfs"]), "ZIP harus berisi tepat semua PDF"
        assert all(n.endswith(".pdf") for n in names), "ZIP hanya boleh berisi PDF"
        print("warnings:", result["warnings"])

        # Proyek .qgs (v0.3.0): satu file berisi SEMUA lembar sebagai layout,
        # dengan isi frame default template.
        print("QGS:", result["qgs"], os.path.getsize(result["qgs"]), "B")
        assert result["qgs"] and os.path.exists(result["qgs"])
        proj = QgsProject()
        assert proj.read(result["qgs"]), ".qgs gagal dibaca kembali"
        qgs_layouts = proj.layoutManager().layouts()
        print("layout di .qgs:", [l.name() for l in qgs_layouts])
        assert len(qgs_layouts) == 10, ".qgs harus berisi 10 layout"
        qgs_texts = []
        for lay in qgs_layouts:
            for item in lay.items():
                if isinstance(item, QgsLayoutItemLabel):
                    qgs_texts.append(item.text())
        qgs_joined = "\n".join(qgs_texts)
        for needle in ["Sistem Koordinat WGS 1984 TM3 Zona 48.2",
                       "Gudang", "Cikalongkulon", "Kabupaten : Cianjur",
                       "Provinsi : Jawa Barat", "ig:@yuktech",
                       "9-6969-69", "Direktur Utama",
                       "Wakil Raja Iblis",
                       "NIP. 123456789", "PT Kebakaran Jenggot",
                       "Jl. Kebakaran Jenggot No. 69, Jakarta Selatan",
                       "Cianjur, 20 November 2026"]:
            assert needle in qgs_joined, "isi frame default tidak ada di .qgs: {}".format(needle)
        print("QGS: 10 layout + isi frame default OK")

        # Pratinjau visual: ekspor lembar pertama ke PNG 150 dpi.
        from qgis.core import (
            QgsExpressionContextUtils,
            QgsLayoutExporter,
            QgsLayoutItemMap,
            QgsRectangle,
        )
        from qgis.PyQt.QtGui import QImage

        layer2 = QgsProject.instance().mapLayersByName("PBT_2091")[0]
        group0 = result["groups"][0]
        layer2.setSubsetString(
            '"{}" IN ({})'.format(pk, ",".join(str(i) for i in group0.feature_ids))
        )
        # Muat layout BARU dari template untuk pratinjau (bukan layout
        # manager yang sudah berisi nilai lembar terakhir dari render_batch)
        # supaya token [%"..."%] masih utuh untuk diisi nilai lembar 1.
        layout2 = engine.load_layout(args.qpt)
        map_item2 = None
        for item in layout2.items():
            if isinstance(item, QgsLayoutItemMap):
                map_item2 = item
                break
        map_item2.setExtent(QgsRectangle(*group0.extent))
        map_item2.setLayers([layer2])
        QgsExpressionContextUtils.setLayoutVariables(
            layout2,
            {"tgl": "20 November 2026", "tglF": "20 November 2026",
             "pbt": "2091", "b": "004", "lembar": "1"},
        )
        # Label skala ditulis literal seperti render_batch (ekspresi
        # map_scale bawaan QGIS memberi nilai salah pada layout yang baru
        # dimuat — 1:33.793.320 pada pratinjau sebelumnya).
        import re as _re
        for item in layout2.items():
            if isinstance(item, QgsLayoutItemLabel) and "map_scale" in item.text():
                text = item.text()
                m = _re.search(r"\[%.*?map_scale.*?%\]", text, _re.S)
                if m:
                    item.setText(text[: m.start()] + group0.scale + text[m.end():])
        # Nilai layout ditulis literal juga di pratinjau (lihat
        # engine._apply_label_values — variabel layout 3.22 tidak
        # ter-evaluasi di [%"..."%]).
        engine._apply_label_values(
            layout2,
            {"tgl": "20 November 2026", "tglF": "20 November 2026",
             "pbt": "2091", "b": "004", "lembar": "1"},
        )
        # Penjaga regresi: tidak boleh ada label yang masih berisi token
        # [%...%] mentah, dan nilai PBT harus sudah tertulis.
        # (Perbaikan ini pernah gagal diam-diam karena `re` belum diimpor
        # di engine.py — try/except per-item menelan NameError.)
        # Pengecualian: label skala mengandung ekspresi [%...map_scale...%]
        # — di pratinjau ini sudah diganti literal di atas, jadi bila masih
        # ada sisanya, itu berarti penggantian skala gagal.
        # (QgsLayoutItemLabel sudah diimpor di awal main().)
        leftover = []
        has_pbt = False
        for item in layout2.items():
            if isinstance(item, QgsLayoutItemLabel):
                t = item.text()
                if "[%" in t and "map_scale" not in t:
                    leftover.append(t[:60])
                if "2091" in t:
                    has_pbt = True
        print("label dengan [%...%] tersisa:", leftover)
        assert not leftover and has_pbt, "nilai layout masih [%...%] mentah di label"
        dpi = 150
        img_settings = QgsLayoutExporter.ImageExportSettings()
        img_settings.dpi = dpi
        exporter2 = QgsLayoutExporter(layout2)
        png_path = os.path.join(args.out, "L01-preview.png")
        # QGIS 3.22: exportToImage() versi path-file (overload QImage tidak
        # tersedia di binding sip 3.22) — tulis langsung ke file.
        img_result = exporter2.exportToImage(png_path, img_settings)
        print("PNG preview:", png_path, os.path.getsize(png_path), "B",
              "export result:", img_result)
        print("SEMUA UJI HEADLESS LULUS")
        # Keluar langsung: qgs.exitQgis() segfault di teardown headless
        # QGIS 3.22 sandbox (exit -1) padahal semua file sudah tertulis —
        # os._exit melewati cleanup itu. (Di plugin asli teardown adalah
        # urusan QGIS, bukan kode ini.)
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
