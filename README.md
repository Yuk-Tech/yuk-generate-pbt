# Yuk Generate PBT! — QGIS Plugin

QGIS plugin to generate **Peta Bidang Tanah (PBTF)** land parcel maps from a GeoPackage + QPT template. QGIS port of the desktop app "Yuk Generate PBT! by @Muhfadllah".

## Features

- Hybrid grouping (divider blocks + grid + greedy + min-10) — 115 parcels become 10 sheets @1:500
- 3-line labels (NAMA / NIB / L=...m2), single text color, no wrap
- PDF render per sheet (with/without ECW imagery variants) + ZIP
- **One QGIS project (.qgs) with all sheets** — editable in QGIS before exporting to PDF
- **9 frame fields**: coordinate system, village/subdistrict, regency/city, district, province, surveyor + license, leader, usage, executor
- **Beta: requires an access code** — Count sheets and Generate are locked until a beta access code is entered (valid until 31 Dec 2026)

## Installation

- **QGIS Plugin Manager** (after release on plugins.qgis.org): search "Yuk Generate PBT!" and install.
- **Manual / from ZIP**: download the release ZIP, in QGIS open `Plugins → Manage and Install Plugins → Install from ZIP`, and select the ZIP file. Or copy the `yuk_generate_pbt/` folder into the QGIS plugins folder (`%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` on Windows).

## Usage

1. Open the plugin sidebar (toolbar / Plugins menu).
2. Enter your beta access code ("Beta Access Code" section) and click Activate.
3. Pick a GeoPackage + layer + QPT template (+ ECW for imagery).
4. Set the scale, colors, and frame fields.
5. Generate — the PDFs + ZIP + `.qgs` file are saved to the output folder.

## Repository structure

```
yuk_generate_pbt/   plugin (metadata.txt, engine.py, panel.py, ...)
```

The `test_*.py` files are headless tests (QGIS 3.22 in an E2B sandbox).

## License

GPL-3.0 — see `LICENSE`.
