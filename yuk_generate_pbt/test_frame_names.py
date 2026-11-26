#!/usr/bin/env python3
"""Uji nama frame v0.6.3: nama Petugas Ukur vs Penggunaan (dan dua PT)
TIDAK BOLEH tertukar di frame kanan.

Regresi bug 2026-11-26 (Derana): nama surveyor dan usage tertukar di
template Demo — akar masalahnya `_y()` di `_apply_frame_texts` memakai
`item.rect().top()` yang SELALU 0.0 (rect() = koordinat lokal item),
sehingga sort-y label kembar jadi no-op dan urutan penugasan = urutan
`layout.items()` (sembarang). Perbaikan: `_y()` memakai
`scenePos().y()` (fallback `pos().y()`).

Uji: muat tiap template (WARDOY + Demo), jalankan `_apply_frame_texts`
dengan nama-nama BERBEDA, lalu baca balik tiap label dari posisi
scene-nya (y, mm): 177.97 = surveyor, 218.76 = leader, 259.15 = usage,
197.29 = PT org pimpinan, 276.36 = PT pelaksana.

Jalankan di sandbox (QGIS 3.22, offscreen):
  LD_LIBRARY_PATH=/lib/x86_64-linux-gnu PYTHONHOME=/usr \\
  PYTHONPATH=/usr/lib/python3/dist-packages QT_QPA_PLATFORM=offscreen \\
  python3 test_frame_names.py --wardoy /path/PBTF_WARDOY.qpt \\
  --demo /path/PBTF_Demo_YukTech.qpt
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402

FRAME = {
    "coord_system": "TM-3 ZONE 48.2",
    "area_kind": "Desa",
    "area_name": "Gudang",
    "admin_kind": "Kabupaten",
    "admin_name": "Cianjur",
    "kecamatan": "Cikalongkulon",
    "provinsi": "Jawa Barat",
    "surveyor_name": "AAA SURVEYOR",
    "surveyor_license": "1-1111-11",
    "leader_org": "PT ORG LEADER",
    "leader_name": "BBB LEADER",
    "leader_position": "Direktur Utama",
    "usage_role": "Wakil Ketua Bidang Fisik",
    "usage_name": "CCC USAGE",
    "usage_nip": "999999999",
    "executor_pt": "PT EXECUTOR",
    "executor_address": "Jl. Test No. 1 Jakarta",
}

# y (mm, scene) -> nama yang HARUS tertulis di label itu.
WANT = {
    177.97: "AAA SURVEYOR",   # blok "Untuk Pembuatannya" — Petugas Ukur
    218.76: "BBB LEADER",     # blok "Mengetahui" — Pimpinan
    259.15: "CCC USAGE",      # blok "Untuk Penggunaannya" — nama
    197.29: "PT ORG LEADER",  # PT kecil (y kecil) — org pimpinan
    276.36: "PT EXECUTOR",    # PT besar (y besar) — pelaksana
}


def check_template(qpt_path):
    from qgis.core import QgsLayoutItemLabel

    layout = engine.load_layout(qpt_path)
    warns = engine._apply_frame_texts(layout, dict(FRAME))
    assert not warns, "peringatan frame tak terduga: {}".format(warns)
    found = {}
    for item in layout.items():
        if not isinstance(item, QgsLayoutItemLabel):
            continue
        try:
            x = item.scenePos().x()
            y = item.scenePos().y()
        except Exception:
            continue
        if x < 300:
            continue
        for wy, wt in WANT.items():
            if abs(y - wy) < 1.0:
                found[wy] = item.text()
    missing = [wy for wy in WANT if wy not in found]
    assert not missing, "{}: label y={} tidak ketemu".format(qpt_path, missing)
    for wy, wt in sorted(WANT.items()):
        got = found[wy]
        assert got == wt, (
            "{}: y={:.2f} harus {!r}, dapat {!r} (NAMA TERTUKAR)".format(
                os.path.basename(qpt_path), wy, wt, got))
        print("  y={:7.2f} {!r} OK".format(wy, got))
    print("OK: {}".format(os.path.basename(qpt_path)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wardoy", required=True)
    ap.add_argument("--demo", required=True)
    args = ap.parse_args()

    from qgis.core import Qgis, QgsApplication

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        print("QGIS_VERSION:", Qgis.QGIS_VERSION)
        check_template(args.wardoy)
        check_template(args.demo)
        print("test_frame_names: LULUS (surveyor/leader/usage + 2 PT benar di kedua template)")
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    main()
