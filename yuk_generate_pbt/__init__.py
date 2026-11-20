"""Titik masuk plugin — QGIS memanggil classFactory() saat memuat plugin."""

from .yuk_generate_pbt import YukGeneratePbtPlugin


def classFactory(iface):
    return YukGeneratePbtPlugin(iface)
