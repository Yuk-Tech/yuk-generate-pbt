#!/usr/bin/env python3
"""Uji sidebar (QDockWidget) v0.2.0 — menggantikan dialog melayang.

Memeriksa: run() pertama membuat dock + panel (footer stempel versi),
toggle run() menyembunyikan/menampilkan dock, tombol Tutup di panel
menyembunyikan dock, tombol X dock (close) juga menyembunyikan dan
status tombol toolbar ikut sinkron, unload() membersihkan dock.
Screenshot dock disimpan ke /tmp/poc/out/dock-preview.png.

Dijalankan di sandbox E2B (QGIS 3.22 / PyQt5, offscreen).
"""
import os
import sys

sys.path.insert(0, "/tmp/poc")

from qgis.core import QgsApplication

QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], True)  # GUI on (offscreen)
qgs.initQgis()

from qgis.PyQt.QtWidgets import QApplication, QLabel

from yuk_generate_pbt.panel import YukGeneratePbtPanel
from yuk_generate_pbt.yuk_generate_pbt import YukGeneratePbtPlugin


class FakeIface:
    def __init__(self):
        self.docks = []

    def mainWindow(self):
        return None

    def addToolBarIcon(self, action):
        pass

    def addPluginToMenu(self, title, action):
        pass

    def removeToolBarIcon(self, action):
        pass

    def removePluginMenu(self, title, action):
        pass

    def addDockWidget(self, area, dock):
        self.docks.append((area, dock))

    def removeDockWidget(self, dock):
        self.docks = [(a, d) for a, d in self.docks if d is not dock]


iface = FakeIface()
plugin = YukGeneratePbtPlugin(iface)
plugin.initGui()  # Siklus hidup asli QGIS: initGui() dulu, baru run().

# run() pertama: dock dibuat + tampil, panel di dalamnya.
plugin.run()
dock = plugin.dock
panel = plugin.panel
assert dock is not None, "dock tidak dibuat run() pertama"
assert isinstance(panel, YukGeneratePbtPanel), "panel bukan YukGeneratePbtPanel"
assert dock.isVisible(), "dock tidak tampil setelah run() pertama"
assert plugin.action.isChecked(), "tombol toolbar tidak tertekan saat dock tampil"
assert len(iface.docks) == 1, "dock tidak didaftarkan ke iface"
assert dock.windowTitle().startswith("Yuk Generate PBT!"), (
    "judul dock salah: {}".format(dock.windowTitle())
)
footer_texts = [w.text() for w in panel.findChildren(QLabel)]
assert any("v0.2.0" in t and "By @muhfadllah" in t for t in footer_texts), (
    "stempel versi tidak ada di footer: {}".format(footer_texts)
)

# Toggle: run() kedua menyembunyikan dock.
plugin.run()
QApplication.processEvents()
assert not dock.isVisible(), "dock masih tampil setelah run() kedua"
assert not plugin.action.isChecked(), "tombol toolbar masih tertekan saat dock sembunyi"

# run() ketiga menampilkan lagi.
plugin.run()
QApplication.processEvents()
assert dock.isVisible(), "dock tidak kembali setelah run() ketiga"

# Tombol Tutup di panel menyembunyikan dock.
panel.close_requested.emit()
QApplication.processEvents()
assert not dock.isVisible(), "dock tidak sembunyi setelah tombol Tutup"
assert not plugin.action.isChecked(), "tombol toolbar tidak sinkron setelah Tutup"

# Tampilkan lagi, lalu tutup lewat X dock (close) — tombol ikut sinkron.
plugin.run()
QApplication.processEvents()
assert dock.isVisible()
dock.close()
QApplication.processEvents()
assert not dock.isVisible(), "dock tidak sembunyi setelah close()"
assert not plugin.action.isChecked(), "tombol toolbar tidak sinkron setelah close()"

# Screenshot dock (tampilkan dulu).
plugin.run()
QApplication.processEvents()
pix = dock.grab()
ok = pix.save("/tmp/poc/out/dock-preview.png")
print("grab saved:", ok, "size:", dock.size().width(), "x", dock.size().height())

# unload() membersihkan dock.
plugin.unload()
assert plugin.dock is None and plugin.panel is None, "dock/panel tidak dibersihkan unload()"
assert len(iface.docks) == 0, "dock tidak dihapus dari iface"

print("SIDEBAR: LULUS — dock toggle + Tutup + X + stempel v0.2.0")
sys.stdout.flush()
os._exit(0)
