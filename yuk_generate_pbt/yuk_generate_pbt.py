"""Yuk Generate PBT! — By @muhfadllah — kelas plugin QGIS (PoC).

Menambahkan tombol toolbar + entri menu "Yuk Generate PBT! — By @muhfadllah"
yang membuka/menutup panel sidebar (QDockWidget). Semua logika ada di
engine.py (PyQGIS) + panel.py (PyQt).

Dulu UI-nya dialog melayang (QDialog) — diganti sidebar di v0.2.0 karena
dialog terus bermasalah di Windows (diminimize lalu hilang, tidak bisa
dibuka lagi). Sidebar tidak punya masalah itu: tidak ada minimize,
tinggal toggle lewat tombol toolbar, tombol Tutup di panel, atau tombol
X di judul dock.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QScrollArea

from .panel import YukGeneratePbtPanel

PLUGIN_TITLE = "Yuk Generate PBT! — By @muhfadllah"


def _enum_value(cls, scoped_name, member, fallback):
    """Konstanta enum Qt yang berpindah nama di PyQt6 (scoped) vs PyQt5
    (flat)."""
    scoped = getattr(cls, scoped_name, None)
    if scoped is not None:
        return getattr(scoped, member, fallback)
    return getattr(cls, member, fallback)


# Qt.RightDockWidgetArea (PyQt5) vs Qt.DockWidgetArea.RightDockWidgetArea
# (PyQt6). Qt::RightDockWidgetArea = 2.
RIGHT_DOCK_AREA = _enum_value(Qt, "DockWidgetArea", "RightDockWidgetArea", 2)
# Qt.ScrollBarAlwaysOff (PyQt5) vs Qt.ScrollBarPolicy.ScrollBarAlwaysOff
# (PyQt6). Qt::ScrollBarAlwaysOff = 1.
SCROLLBAR_OFF = _enum_value(Qt, "ScrollBarPolicy", "ScrollBarAlwaysOff", 1)


class YukGeneratePbtPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.panel = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, PLUGIN_TITLE, self.iface.mainWindow())
        self.action.setObjectName("yukGeneratePbt")
        # Tombol toggle: tampil tertekan saat sidebar terbuka.
        self.action.setCheckable(True)
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(PLUGIN_TITLE, self.action)

    def unload(self):
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu(PLUGIN_TITLE, self.action)
            self.action = None
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
            self.panel = None

    def run(self):
        if self.dock is None:
            self.panel = YukGeneratePbtPanel()
            self.panel.close_requested.connect(self._hide_dock)
            scroll = QScrollArea()
            scroll.setWidget(self.panel)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(SCROLLBAR_OFF)
            self.dock = QDockWidget(PLUGIN_TITLE, self.iface.mainWindow())
            self.dock.setObjectName("yukGeneratePbtDock")
            self.dock.setWidget(scroll)
            # Sinkronkan tombol toolbar saat dock ditutup lewat X-nya.
            self.dock.visibilityChanged.connect(self._on_dock_visibility)
            self.iface.addDockWidget(RIGHT_DOCK_AREA, self.dock)
        # Toggle: tampilkan bila tersembunyi, sembunyikan bila tampil.
        self.dock.setVisible(not self.dock.isVisible())
        if self.dock.isVisible():
            self.dock.raise_()
            self.dock.activateWindow()
        if self.action is not None:
            self.action.setChecked(self.dock.isVisible())

    def _hide_dock(self):
        # Tombol Tutup di panel.
        if self.dock is not None:
            self.dock.hide()

    def _on_dock_visibility(self, visible):
        if self.action is not None:
            self.action.setChecked(visible)
