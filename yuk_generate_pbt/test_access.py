#!/usr/bin/env python3
"""Uji gerbang kode akses v0.7.6 — headless di sandbox E2B.

Memeriksa (tanpa GUI):
  1. license.validate_code: kode salah ditolak, kode valid diterima,
     kode kedaluwarsa ditolak, normalisasi (huruf kecil / tanpa tanda
     hubung) tetap valid.
  2. Panel: baru dibuka Generate + Hitung lembar MATI + status
     "Belum aktif" + tombol Nonaktifkan MATI; kode valid -> Aktifkan
     -> kedua tombol HIDUP + status aktif + tombol Nonaktifkan HIDUP
     + isian kode + tombol Aktifkan terkunci; panel baru (proses sama)
     tetap aktif (QSettings tersimpan); tombol Nonaktifkan ->
     kode terlepas, isian kode kosong + terbuka lagi, tombol
     Aktifkan HIDUP, Nonaktifkan MATI; kode kedua bisa diaktifkan
     (ganti kode tanpa restart).
  3. Footer stempel versi v0.7.6.
  4. Label checkbox buffer = "Buffer teks" (tanpa "(halo putih di label)").

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
# Paksa mode lokal: panel v0.5.9 memakai URL API bawaan bila kunci
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

# --- 2. panel: terkunci -> aktif -> tersimpan -> lepas via tombol -> ganti kode ---
panel = YukGeneratePbtPanel()
QApplication.processEvents()
assert not panel.generate_button.isEnabled(), "Generate harus MATI sebelum aktivasi"
assert not panel.count_button.isEnabled(), "Hitung lembar harus MATI sebelum aktivasi"
assert not panel.deactivate_button.isEnabled(), "Nonaktifkan harus MATI sebelum aktivasi"
assert panel.code_edit.isEnabled(), "isian kode harus terbuka sebelum aktivasi"
assert panel.activate_button.isEnabled(), "Aktifkan harus HIDUP sebelum aktivasi"
assert "Belum aktif" in panel.license_status.text(), (
    "status awal salah: {}".format(panel.license_status.text())
)
assert panel.text_buffer_check.text() == "Buffer teks", (
    "label buffer salah: {}".format(panel.text_buffer_check.text())
)
footer_texts = [w.text() for w in panel.findChildren(QLabel)]
assert any("v0.7.6" in t and "By @muhfadllah" in t for t in footer_texts), (
    "stempel versi v0.7.6 tidak ada di footer: {}".format(footer_texts)
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
assert not panel.activate_button.isEnabled(), "Aktifkan harus MATI setelah aktif"
assert panel.deactivate_button.isEnabled(), "Nonaktifkan harus HIDUP setelah aktif"

# Panel baru: status aktif bertahan (QSettings).
panel2 = YukGeneratePbtPanel()
QApplication.processEvents()
assert panel2.generate_button.isEnabled(), "aktivasi tidak tersimpan di QSettings"
assert "Aktif" in panel2.license_status.text(), "panel baru harus tetap aktif"
assert panel2.deactivate_button.isEnabled(), "Nonaktifkan harus HIDUP di panel baru"

# Lepas aktivasi VIA TOMBOL Nonaktifkan: terkunci lagi + isian kosong.
panel2._on_deactivate()
QApplication.processEvents()
assert not lic.is_activated(), "deactivate tombol harus menghapus status aktif"
assert not panel2.generate_button.isEnabled(), "Generate harus MATI setelah Nonaktifkan"
assert not panel2.count_button.isEnabled(), "Hitung lembar harus MATI setelah Nonaktifkan"
assert panel2.code_edit.isEnabled(), "isian kode harus terbuka lagi setelah Nonaktifkan"
assert panel2.code_edit.text() == "", "isian kode harus dikosongkan setelah Nonaktifkan"
assert panel2.activate_button.isEnabled(), "Aktifkan harus HIDUP lagi setelah Nonaktifkan"
assert not panel2.deactivate_button.isEnabled(), "Nonaktifkan harus MATI setelah Nonaktifkan"
assert "Belum aktif" in panel2.license_status.text(), (
    "status harus 'Belum aktif' setelah Nonaktifkan: {}".format(
        panel2.license_status.text())
)
assert not lic.stored_hash(), "hash kode harus terhapus dari QSettings"

# Ganti kode: kode kedua bisa diaktifkan (tanpa restart).
TEST_CODE2 = "YUK-TEST99-876543"
lic.CODE_HASHES.add(lic.code_hash(TEST_CODE2))
panel2.code_edit.setText(TEST_CODE2)
panel2._on_activate()
QApplication.processEvents()
assert panel2.generate_button.isEnabled(), "Generate harus HIDUP setelah ganti kode"
assert "Aktif" in panel2.license_status.text(), "status harus aktif setelah ganti kode"
assert lic.stored_hash() == lic.code_hash(TEST_CODE2), "hash tersimpan harus kode baru"

# Lepas aktivasi (langsung via license): terkunci lagi.
lic.deactivate()
panel3 = YukGeneratePbtPanel()
QApplication.processEvents()
assert not panel3.generate_button.isEnabled(), "Generate harus MATI setelah deactivate"

print("AKSES BETA: LULUS — kunci + aktivasi + tersimpan + Nonaktifkan + ganti kode + stempel v0.7.6 + label buffer")
sys.stdout.flush()
os._exit(0)
