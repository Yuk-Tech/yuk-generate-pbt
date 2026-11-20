#!/usr/bin/env python3
"""Uji isi frame + proyek .qgs (v0.3.0) di sandbox (QGIS 3.22).

Render lembar pertama dengan nilai frame KUSTOM (Kelurahan, Kota,
UTM, nama-nama berbeda) + simpan .qgs, lalu muat ulang .qgs ke
QgsProject baru dan pastikan:
  1. .qgs berisi 1 layout (first_sheet_only),
  2. label-label frame berisi nilai kustom (bukan default template),
  3. label tanggal memakai nama kota/kabupaten kustom.
Jalankan via run_frame_test.py (mengunggah engine + data ke sandbox).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402


def label_texts(layout):
    from qgis.core import QgsLayoutItemLabel

    texts = []
    for item in layout.items():
        try:
            if isinstance(item, QgsLayoutItemLabel):
                texts.append(item.text())
        except Exception:
            continue
    return texts


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
        custom = {
            "coord_system": "WGS 1984 UTM Zona 48S",
            "area_kind": "Kelurahan",
            "area_name": "Sukamaju",
            "admin_kind": "Kota",
            "admin_name": "Bogor",
            "kecamatan": "Bogor Tengah",
            "provinsi": "Jawa Barat",
            "surveyor_name": "Budi Santoso",
            "surveyor_license": "9-9999-99",
            "leader_org": "PT. CONTOH MAJU",
            "leader_name": "Andi Wijaya",
            "leader_position": "Direktur",
            "usage_role": "Ketua Bidang Fisik",
            "usage_name": "Siti Rahma",
            "usage_nip": "198001012010011001",
            "executor_pt": "PT. PELAKSANA CONTOH",
            "executor_address": "Jl. Contoh No. 1 Jakarta",
        }
        log_lines = []
        result = engine.render_batch(
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
                "save_qgs": True,
                "log": lambda m: log_lines.append(m),
                **custom,
            }
        )
        print("PDF:", result["pdfs"])
        print("QGS:", result["qgs"], os.path.getsize(result["qgs"]), "B")
        assert result["qgs"] and os.path.exists(result["qgs"])
        frame_warns = [m for m in log_lines if "Isi frame tidak ketemu" in m]
        print("peringatan frame:", frame_warns)
        assert not frame_warns, "semua butir frame harus ketemu di template"

        # Muat ulang .qgs ke proyek baru dan periksa isi labelnya.
        proj = QgsProject()
        ok = proj.read(result["qgs"])
        assert ok, ".qgs gagal dibaca kembali"
        layouts = proj.layoutManager().layouts()
        print("layout di .qgs:", [l.name() for l in layouts])
        assert len(layouts) == 1, "first_sheet_only -> 1 layout"
        texts = label_texts(layouts[0])
        joined = "\n".join(texts)
        checks = {
            "Sistem Koordinat WGS 1984 UTM Zona 48S": "sistem koordinat",
            "Kelurahan": "jenis wilayah (kiri)",
            "Sukamaju": "nama kelurahan",
            "Kota : Bogor": "kota (panel + header atas)",
            "Bogor Tengah": "kecamatan",
            "Bogor, 20 November 2026": "nama tempat di tanggal",
            "Budi Santoso": "petugas ukur",
            "9-9999-99": "lisensi",
            "PT. CONTOH MAJU": "pimpinan dari",
            "Andi Wijaya": "nama pimpinan",
            "Direktur": "jabatan pimpinan",
            "Ketua Bidang Fisik": "peran penggunaan",
            "Siti Rahma": "nama penggunaan",
            "NIP. 198001012010011001": "NIP",
            "PT. PELAKSANA CONTOH": "pelaksana",
            "Jl. Contoh No. 1 Jakarta": "alamat pelaksana",
        }
        for needle, label in checks.items():
            assert needle in joined, "tidak ketemu di .qgs: {} ({})".format(needle, label)
            print("  OK:", label, "->", needle)
        # Nilai default template TIDAK boleh tersisa di label frame.
        for stale in ["Gudang", "Cikalongkulon", "Moch Ikhsan", "Dede Kuswana",
                      "SANGGA BUANA", "Kalibata Timur", "Wakil Ketua Bidang Fisik",
                      "Direktur Utama"]:
            assert stale not in joined, "nilai default masih ada di .qgs: {}".format(stale)
        print("FRAME + QGS: LULUS")
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
