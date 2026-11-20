#!/usr/bin/env python3
"""Uji resolusi enum label v0.2.1 — QGIS 4 vs QGIS 3.

Memeriksa: jalur Qgis.* (QGIS 4) gagal diam-diam di QGIS 3.22 (tidak
ada Qgis.LabelPlacement di 3.22), lalu jalur QgsPalLayerSettings.*
dipakai dan nilainya sama dengan anggota enum QGIS 3 yang benar:
placement = OverPoint (1), multilineAlign = MultiCenter (1),
quad = QuadrantCenter (4), size_key = Property.Size (0).

Dijalankan di sandbox E2B (QGIS 3.22 / PyQt5, tanpa GUI).
"""
import os
import sys

sys.path.insert(0, "/tmp/poc")

from qgis.core import QgsApplication

QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)
qgs.initQgis()

from qgis.core import QgsPalLayerSettings

from yuk_generate_pbt import engine

# Jalur QGIS 4 harus gagal diam-diam di 3.22 (bukan crash, bukan nilai salah).
nope = engine._qgis_enum("Qgis.LabelPlacement.OverPoint", fallback="NOPE")
assert nope == "NOPE", "jalur QGIS 4 malah ketemu di 3.22: {!r}".format(nope)
nope = engine._qgis_enum("Qgis.LabelMultiLineAlignment.Center", fallback="NOPE")
assert nope == "NOPE", "jalur QGIS 4 malah ketemu di 3.22: {!r}".format(nope)

# Resolusi penuh seperti di blok labeling — harus sama dengan enum QGIS 3.
placement = engine._qgis_enum(
    "Qgis.LabelPlacement.OverPoint",
    "QgsPalLayerSettings.LabelPlacement.OverPoint",
    "QgsPalLayerSettings.Placement.OverPoint",
    "QgsPalLayerSettings.OverPoint",
    fallback=1,
)
print("placement:", repr(placement), "int:", int(placement))
assert placement == QgsPalLayerSettings.Placement.OverPoint, repr(placement)
assert int(placement) == 1, int(placement)

multi = engine._qgis_enum(
    "Qgis.LabelMultiLineAlignment.Center",
    "QgsPalLayerSettings.LabelMultiLineAlignment.Center",
    "QgsPalLayerSettings.MultiLineAlign.MultiCenter",
    "QgsPalLayerSettings.MultiCenter",
    fallback=1,
)
print("multilineAlign:", repr(multi), "int:", int(multi))
assert multi == QgsPalLayerSettings.MultiLineAlign.MultiCenter, repr(multi)
assert int(multi) == 1, int(multi)

quad = engine._qgis_enum(
    "Qgis.LabelQuadrantPosition.Over",
    "QgsPalLayerSettings.LabelQuadrantPosition.Over",
    "QgsPalLayerSettings.QuadrantPosition.QuadrantCenter",
    "QgsPalLayerSettings.QuadrantCenter",
    fallback=4,
)
# QuadrantCenter TIDAK PUNYA anggota Python di 3.22 (enum-nya lompat
# dari QuadrantLeft = 3 ke QuadrantRight = 5) — nilai tengah = 4 (int),
# sama seperti fallback lama. Di QGIS 4 anggotanya bernama Over
# (Qgis.LabelQuadrantPosition.Over), nilainya juga 4.
print("quad:", repr(quad), "int:", int(quad))
assert int(quad) == 4, int(quad)

size_key = engine._qgis_enum(
    "QgsPalLayerSettings.Property.Size",
    "QgsPalLayerSettings.Size",
    fallback=None,
)
print("size_key:", repr(size_key), "int:", int(size_key))
assert size_key == QgsPalLayerSettings.Property.Size, repr(size_key)
assert int(size_key) == 0, int(size_key)

# Nilai-nilai itu harus bisa dipasang ke QgsPalLayerSettings tanpa error.
settings = QgsPalLayerSettings()
settings.placement = placement
settings.multilineAlign = multi
settings.quadOffset = quad
print("ENUM: LULUS — QGIS 4 gagal diam-diam, QGIS 3 benar (1/1/4/0)")
sys.stdout.flush()
os._exit(0)
