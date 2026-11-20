#!/usr/bin/env python3
"""Uji gerbang kode akses beta v0.5.4 — headless di sandbox E2B.

Memeriksa (tanpa GUI):
  1. license.validate_code: kode salah ditolak, kode valid diterima,
     kode kedaluwarsa ditolak, normalisasi (huruf kecil / tanpa tanda
     hubung) tetap valid.
  2. Panel: baru dibuka Generate + Hitung lembar MATI + status
     "Belum aktif"; kode valid -> Aktifkan -> kedua tombol HIDUP +
     status aktif; panel baru (proses sama) tetap aktif (QSettings
     tersimpan); deactivate -> tombol MATI lagi.
  3. Footer stempel versi v0.5.4.

Kode uji disuntik hash-nya saat jalan (bukan kode beta asli — kode
asli sudah diverifikasi lokal: 10/10 valid, lihat license.py).
"""
import os
import sys

sys.path.insert(0, "/tmp/poc")

from qgis.core import QgsApplication

QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], True)  # GUI on (offscreen)
qgs.initQgis()

from qgis.PyQt.QtWidgets import QApplication, QLabel

from yuk_generate_pbt import license as lic
from yuk_generate_pbt.panel import YukGeneratePbtPanel

# Bersihkan status aktif dari run sebelumnya (deterministik).
lic.deactivate()
# Paksa mode lokal: panel v0.5.4 memakai URL API bawaan bila kunci
# belum ada di QSettings — uji ini harus jalan tanpa server.
lic._settings().setValue(lic.LICENSE_KEY_API, "")
lic.set_api_base("")

# --- 1. logika validasi (hash uji disuntik) ---
TEST_CODE = "YUK-TEST12-345678"
lic.CODE_HASHES.add(lic.code_hash(TEST_CODE))
ok, msg = lic.validate_code("YUK-AAAAAA-BBBBBB")
assert not ok and "tidak dikenal" in msg, "kode salah harus ditolak: {}".format(msg)
ok, msg = lic.validate_code(TEST_CODE)
assert ok, "kode uji harus valid: {}".format(msg)
ok, _ = lic.validate_code(TEST_CODE.lower().replace("-", ""))
assert ok, "normalisasi huruf kecil/tanpa hubung harus valid"
ok, msg = lic.validate_code(TEST_CODE, today="2027-01-01")
assert not ok and "berakhir" in msg, "kode kedaluwarsa harus ditolak: {}".format(msg)
assert not lic.is_activated(), "belum ada aktivasi tersimpan"
print("LICENSE: validasi OK (tolak salah + kedaluwarsa, terima benar)")

# --- 2. panel: terkunci -> aktif -> tersimpan -> lepas ---
panel = YukGeneratePbtPanel()
QApplication.processEvents()
assert not panel.generate_button.isEnabled(), "Generate harus MATI sebelum aktivasi"
assert not panel.count_button.isEnabled(), "Hitung lembar harus MATI sebelum aktivasi"
assert "Belum aktif" in panel.license_status.text(), (
    "status awal salah: {}".format(panel.license_status.text())
)
footer_texts = [w.text() for w in panel.findChildren(QLabel)]
assert any("v0.5.4" in t and "By @muhfadllah" in t for t in footer_texts), (
    "stempel versi v0.5.4 tidak ada di footer: {}".format(footer_texts)
)

# Kode salah dulu: tetap terkunci.
panel.code_edit.setText("YUK-AAAAAA-BBBBBB")
panel._on_activate()
QApplication.processEvents()
assert not panel.generate_button.isEnabled(), "Generate hidup padahal kode salah"
assert "tidak dikenal" in panel.log.toPlainText(), "log harus mencatat kode salah"

# Kode benar: terbuka.
panel.code_edit.setText(TEST_CODE)
panel._on_activate()
QApplication.processEvents()
assert panel.generate_button.isEnabled(), "Generate harus HIDUP setelah aktivasi"
assert panel.count_button.isEnabled(), "Hitung lembar harus HIDUP setelah aktivasi"
assert "Aktif" in panel.license_status.text(), (
    "status harus aktif: {}".format(panel.license_status.text())
)
assert not panel.code_edit.isEnabled(), "isian kode harus terkunci setelah aktif"

# Panel baru: status aktif bertahan (QSettings).
panel2 = YukGeneratePbtPanel()
QApplication.processEvents()
assert panel2.generate_button.isEnabled(), "aktivasi tidak tersimpan di QSettings"
assert "Aktif" in panel2.license_status.text(), "panel baru harus tetap aktif"

# Lepas aktivasi: terkunci lagi.
lic.deactivate()
panel3 = YukGeneratePbtPanel()
QApplication.processEvents()
assert not panel3.generate_button.isEnabled(), "Generate harus MATI setelah deactivate"

print("AKSES BETA: LULUS — kunci + aktivasi + tersimpan + lepas + stempel v0.5.4")
sys.stdout.flush()
os._exit(0)
