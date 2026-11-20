"""
Yuk Generate PBT! — panel sidebar plugin QGIS (PoC).

Panel PyQt (lewat qgis.PyQt — otomatis PyQt5 di QGIS 3, PyQt6 di QGIS 4)
yang dipasang di QDockWidget sisi QGIS. Semua kontrol aplikasi desktop
di-port: pemilih GPKG/QPT/ECW, skala, warna persil, warna teks label,
varian citra, format output (PDF / PDF+ZIP), form pengesahan (tanggal /
No PBT / No Blok / logo / TTD), riwayat sederhana.

Dulu panel ini dialog melayang (QDialog) — diganti sidebar di v0.2.0
karena dialog terus bermasalah di Windows (diminimize lalu hilang,
tidak bisa dibuka lagi). Sidebar tidak punya masalah itu: tidak ada
minimize, tinggal toggle lewat tombol toolbar / tombol Tutup di panel.

Catatan PoC: render berjalan di thread utama (dengan processEvents agar
log tetap jalan). Untuk port penuh, pindahkan ke QgsTask agar UI tidak
membeku selama render batch.
"""

import configparser
import json
import os
import sqlite3

from qgis.PyQt.QtCore import QSettings, Qt, pyqtSignal


def _enum_value(cls, scoped_name, member, fallback):
    """Konstanta enum Qt yang berpindah nama di PyQt6 (scoped) vs PyQt5
    (flat). Contoh: Qt.AlignCenter (PyQt5) vs
    Qt.AlignmentFlag.AlignCenter (PyQt6)."""
    scoped = getattr(cls, scoped_name, None)
    if scoped is not None:
        return getattr(scoped, member, fallback)
    return getattr(cls, member, fallback)


# Qt.AlignCenter (PyQt5) vs Qt.AlignmentFlag.AlignCenter (PyQt6).
# Bentuk flat tidak ada di PyQt6 — dialog crash di sana (AttributeError,
# dilaporkan 2026-11-20 19:56 WIB).
ALIGN_CENTER = _enum_value(Qt, "AlignmentFlag", "AlignCenter", 0x0004)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# QFormLayout.WrapAllRows — label di atas field, untuk panel sempit.
WRAP_ALL_ROWS = _enum_value(QFormLayout, "RowWrapPolicy", "WrapAllRows", 2)

from . import engine
from . import license as lic

SCALES = ["Auto", "1:250", "1:500", "1:1000", "1:1500", "1:2000", "1:2500"]
PARCEL_COLORS = [
    "Hijau",
    "Putih",
    "Merah",
    "Ungu",
    "Biru",
    "Kuning",
    "Oranye",
    "Hitam",
    "Abu gelap",
]
TEXT_COLORS = [
    "Abu gelap",
    "Hijau",
    "Putih",
    "Merah",
    "Ungu",
    "Biru",
    "Kuning",
    "Oranye",
    "Hitam",
]
HISTORY_KEY = "yuk-generate-pbt/history"
HISTORY_MAX = 20


def gpkg_layers(path):
    """Daftar layer fitur di sebuah GeoPackage (baca gpkg_contents)."""
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(path), uri=True)
        rows = conn.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def plugin_version():
    """Versi plugin dari metadata.txt (satu sumber kebenaran)."""
    try:
        cp = configparser.ConfigParser()
        cp.read(
            os.path.join(os.path.dirname(__file__), "metadata.txt"),
            encoding="utf-8",
        )
        return cp.get("general", "version", fallback="?")
    except Exception:
        return "?"


class YukGeneratePbtPanel(QWidget):
    # Dipancarkan saat tombol Tutup ditekan — plugin menyembunyikan dock.
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("YukGeneratePBT", "YukGeneratePBT")
        # API lisensi (v0.5.0, bawaan v0.5.1): bila belum pernah diatur,
        # pakai server bawaan (DEFAULT_API_BASE_URL) dan simpan sebagai
        # nilai awal — penguji tidak perlu mengisi apa pun. Nilai ""
        # yang tersimpan sengaja berarti mode lokal.
        _stored_api = self.settings.value(lic.LICENSE_KEY_API, None)
        if _stored_api is None:
            _stored_api = lic.DEFAULT_API_BASE_URL
            self.settings.setValue(lic.LICENSE_KEY_API, _stored_api)
        lic.set_api_base(_stored_api or "")
        self._build_ui()
        self._load_history()
        # Bila API baru diisi dan ada aktivasi lokal tersimpan, konfirmasi
        # sekali ke server supaya kuota terhitung (tanpa minta kode ulang).
        lic.ensure_server_activation()
        self._refresh_license_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # Header vertikal (logo di atas, judul di bawah) — panel sidebar
        # itu sempit, header horizontal tidak muat.
        header = QVBoxLayout()
        logo_path = os.path.join(os.path.dirname(__file__), "yuk-logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setAlignment(ALIGN_CENTER)
            pix = QPixmap(logo_path)
            if not pix.isNull():
                logo.setPixmap(pix.scaledToWidth(110))
            header.addWidget(logo)
        title = QLabel("<b>YUK GENERATE PBT!</b><br/>By @muhfadllah")
        title.setAlignment(ALIGN_CENTER)
        title.setWordWrap(True)
        header.addWidget(title)
        root.addLayout(header)

        # Gerbang kode akses beta (v0.4.0, API server v0.5.0): Hitung
        # lembar / Generate terkunci sampai kode beta yang valid
        # dimasukkan. Status aktif disimpan di QSettings, jadi cukup
        # sekali per mesin. Kolom API lisensi: isi URL dasar Supabase
        # (.../functions/v1) untuk mode server (kuota 5 generate/kode
        # dihitung di server); kosong = mode lokal (tanpa hitungan).
        access_box = QGroupBox("Kode Akses Beta")
        access = QVBoxLayout(access_box)
        access_row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("cth. YUK-XXXXXX-XXXXXX")
        self.activate_button = QPushButton("Aktifkan")
        self.activate_button.clicked.connect(self._on_activate)
        access_row.addWidget(self.code_edit)
        access_row.addWidget(self.activate_button)
        access.addLayout(access_row)
        self.license_status = QLabel(lic.status_text())
        self.license_status.setWordWrap(True)
        access.addWidget(self.license_status)
        api_row = QHBoxLayout()
        api_label = QLabel("API lisensi:")
        self.api_edit = QLineEdit()
        self.api_edit.setPlaceholderText(
            "https://xxxxx.supabase.co/functions/v1 (kosong = lokal)"
        )
        self.api_edit.setText(lic.get_api_base())
        self.api_edit.editingFinished.connect(self._on_api_changed)
        api_row.addWidget(api_label)
        api_row.addWidget(self.api_edit)
        access.addLayout(api_row)
        root.addWidget(access_box)

        form = QFormLayout()
        form.setRowWrapPolicy(WRAP_ALL_ROWS)
        self.gpkg_edit = QLineEdit()
        self.gpkg_edit.setPlaceholderText("Pilih file .gpkg …")
        self.gpkg_edit.textChanged.connect(self._on_gpkg_changed)
        form.addRow("GeoPackage:", self._picker(self.gpkg_edit, "Pilih GeoPackage", "GeoPackage (*.gpkg)"))
        self.layer_combo = QComboBox()
        form.addRow("Layer:", self.layer_combo)
        self.qpt_edit = QLineEdit()
        self.qpt_edit.setPlaceholderText("Pilih template .qpt (PBTF_WARDOY.qpt) …")
        form.addRow("Template QPT:", self._picker(self.qpt_edit, "Pilih template QPT", "QGIS Print Template (*.qpt)"))
        self.ecw_edit = QLineEdit()
        self.ecw_edit.setPlaceholderText("Opsional — citra ECW untuk varian CITRA …")
        form.addRow("Citra ECW:", self._picker(self.ecw_edit, "Pilih citra ECW", "ECW (*.ecw);;Semua file (*)"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(SCALES)
        form.addRow("Skala:", self.scale_combo)
        self.parcel_color_combo = QComboBox()
        self.parcel_color_combo.addItems(PARCEL_COLORS)
        form.addRow("Warna persil:", self.parcel_color_combo)
        self.text_color_combo = QComboBox()
        self.text_color_combo.addItems(TEXT_COLORS)
        form.addRow("Warna teks:", self.text_color_combo)
        root.addLayout(form)

        variants = QHBoxLayout()
        self.with_imagery_check = QCheckBox("Dengan citra ECW")
        self.without_imagery_check = QCheckBox("Tanpa citra")
        self.without_imagery_check.setChecked(True)
        variants.addWidget(self.with_imagery_check)
        variants.addWidget(self.without_imagery_check)
        variants.addStretch(1)
        root.addLayout(variants)

        sign = QFormLayout()
        sign.setRowWrapPolicy(WRAP_ALL_ROWS)
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("cth. 20 November 2026")
        sign.addRow("Tanggal:", self.date_edit)
        self.pbt_edit = QLineEdit()
        self.pbt_edit.setPlaceholderText("cth. 2091")
        sign.addRow("No PBT:", self.pbt_edit)
        self.block_edit = QLineEdit()
        self.block_edit.setPlaceholderText("cth. 004")
        sign.addRow("No Blok:", self.block_edit)
        self.logo_edit = QLineEdit()
        sign.addRow("Logo:", self._picker(self.logo_edit, "Pilih logo", "Gambar (*.png *.jpg *.jpeg)"))
        self.surveyor_edit = QLineEdit()
        sign.addRow("TTD Petugas Ukur:", self._picker(self.surveyor_edit, "Pilih TTD Petugas Ukur", "Gambar (*.png *.jpg *.jpeg)"))
        self.leader_edit = QLineEdit()
        sign.addRow("TTD Pimpinan:", self._picker(self.leader_edit, "Pilih TTD Pimpinan", "Gambar (*.png *.jpg *.jpeg)"))
        root.addLayout(sign)

        # Isi frame (teks) — 9 butir. Pilihan Desa/Kelurahan dan
        # Kabupaten/Kota memakai radio (satu harus dipilih) + isian nama.
        frame_box = QGroupBox("Isi Frame")
        frame = QFormLayout()
        frame.setRowWrapPolicy(WRAP_ALL_ROWS)
        self.coord_combo = QComboBox()
        self.coord_combo.addItems(engine.COORD_SYSTEMS)
        self.coord_combo.setCurrentText(engine.DEFAULT_COORD_SYSTEM)
        frame.addRow("Sistem Koordinat:", self.coord_combo)

        area_row = QHBoxLayout()
        self.area_desa_radio = QRadioButton("Desa")
        self.area_desa_radio.setChecked(True)
        self.area_kel_radio = QRadioButton("Kelurahan")
        self.area_group = QButtonGroup(self)
        self.area_group.addButton(self.area_desa_radio)
        self.area_group.addButton(self.area_kel_radio)
        area_row.addWidget(self.area_desa_radio)
        area_row.addWidget(self.area_kel_radio)
        area_row.addStretch(1)
        frame.addRow("Desa / Kelurahan:", area_row)
        self.area_edit = QLineEdit()
        self.area_edit.setText("Gudang")
        frame.addRow("Nama desa / kelurahan:", self.area_edit)

        admin_row = QHBoxLayout()
        self.admin_kab_radio = QRadioButton("Kabupaten")
        self.admin_kab_radio.setChecked(True)
        self.admin_kota_radio = QRadioButton("Kota")
        self.admin_group = QButtonGroup(self)
        self.admin_group.addButton(self.admin_kab_radio)
        self.admin_group.addButton(self.admin_kota_radio)
        admin_row.addWidget(self.admin_kab_radio)
        admin_row.addWidget(self.admin_kota_radio)
        admin_row.addStretch(1)
        frame.addRow("Kabupaten / Kota:", admin_row)
        self.admin_edit = QLineEdit()
        self.admin_edit.setText("Cianjur")
        frame.addRow("Nama kabupaten / kota:", self.admin_edit)

        self.kecamatan_edit = QLineEdit()
        self.kecamatan_edit.setText("Cikalongkulon")
        frame.addRow("Kecamatan:", self.kecamatan_edit)
        self.provinsi_edit = QLineEdit()
        self.provinsi_edit.setText("Jawa Barat")
        frame.addRow("Provinsi:", self.provinsi_edit)

        self.surveyor_name_edit = QLineEdit()
        self.surveyor_name_edit.setText("ig:@yuktech")
        frame.addRow("Petugas Ukur:", self.surveyor_name_edit)
        self.surveyor_license_edit = QLineEdit()
        self.surveyor_license_edit.setText("9-6969-69")
        frame.addRow("No Lisensi Petugas Ukur:", self.surveyor_license_edit)

        self.leader_org_edit = QLineEdit()
        self.leader_org_edit.setText("PT Kebakaran Jenggot")
        frame.addRow("Pimpinan dari:", self.leader_org_edit)
        self.leader_name_edit = QLineEdit()
        self.leader_name_edit.setText("ig:@yuktech")
        frame.addRow("Nama Pimpinan:", self.leader_name_edit)
        self.leader_position_edit = QLineEdit()
        self.leader_position_edit.setText("Direktur Utama")
        frame.addRow("Jabatan Pimpinan:", self.leader_position_edit)

        self.usage_role_edit = QLineEdit()
        self.usage_role_edit.setText("Wakil Raja Iblis")
        frame.addRow("Penggunaan sebagai:", self.usage_role_edit)
        self.usage_name_edit = QLineEdit()
        self.usage_name_edit.setText("ig:@yuktech")
        frame.addRow("Nama (penggunaan):", self.usage_name_edit)
        self.usage_nip_edit = QLineEdit()
        self.usage_nip_edit.setText("123456789")
        frame.addRow("NIP (penggunaan):", self.usage_nip_edit)

        self.executor_pt_edit = QLineEdit()
        self.executor_pt_edit.setText("PT Kebakaran Jenggot")
        frame.addRow("Pelaksana (PT):", self.executor_pt_edit)
        self.executor_address_edit = QLineEdit()
        self.executor_address_edit.setText("Jl. Kebakaran Jenggot No. 69, Jakarta Selatan")
        frame.addRow("Alamat pelaksana:", self.executor_address_edit)
        frame_box.setLayout(frame)
        root.addWidget(frame_box)

        out = QFormLayout()
        out.setRowWrapPolicy(WRAP_ALL_ROWS)
        self.output_edit = QLineEdit()
        out.addRow("Folder output:", self._picker_dir(self.output_edit))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PDF", "PDF+ZIP"])
        out.addRow("Format:", self.format_combo)
        root.addLayout(out)

        self.first_only_check = QCheckBox("Hanya lembar pertama (uji cepat)")
        root.addWidget(self.first_only_check)
        self.save_qgs_check = QCheckBox("Simpan proyek QGIS (.qgs, semua lembar)")
        self.save_qgs_check.setChecked(True)
        root.addWidget(self.save_qgs_check)

        buttons = QHBoxLayout()
        self.count_button = QPushButton("Hitung lembar")
        self.count_button.clicked.connect(self._on_count)
        self.generate_button = QPushButton("Generate")
        self.generate_button.clicked.connect(self._on_generate)
        close_button = QPushButton("Tutup")
        # Tutup di panel sidebar = sembunyikan dock (bukan close widget).
        close_button.clicked.connect(self.close_requested.emit)
        buttons.addWidget(self.count_button)
        buttons.addWidget(self.generate_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        root.addWidget(self.log)

        history_box = QGroupBox("Batch sebelumnya (klik 2x = pakai folder ini)")
        history_layout = QVBoxLayout(history_box)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._on_history_double_click)
        history_layout.addWidget(self.history_list)
        clear_button = QPushButton("Bersihkan riwayat")
        clear_button.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_button)
        root.addWidget(history_box)

        # Watermark di dalam plugin (footer) + stempel versi — supaya
        # terlihat langsung versi berapa yang sedang berjalan.
        footer = QLabel(
            "Yuk Generate PBT! v{} — By @muhfadllah".format(plugin_version())
        )
        footer.setAlignment(ALIGN_CENTER)
        footer.setStyleSheet("color: #888888;")
        root.addWidget(footer)

    # ------------------------------------------------------------------
    def _picker(self, edit, caption, file_filter):
        row = QHBoxLayout()
        row.addWidget(edit)
        button = QPushButton("Pilih…")
        button.clicked.connect(
            lambda: self._pick_file(edit, caption, file_filter)
        )
        row.addWidget(button)
        return row

    def _picker_dir(self, edit):
        row = QHBoxLayout()
        row.addWidget(edit)
        button = QPushButton("Pilih…")
        button.clicked.connect(
            lambda: self._pick_dir(edit)
        )
        row.addWidget(button)
        return row

    def _pick_file(self, edit, caption, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, caption, edit.text(), file_filter)
        if path:
            edit.setText(path)

    def _pick_dir(self, edit):
        path = QFileDialog.getExistingDirectory(self, "Pilih folder output", edit.text())
        if path:
            edit.setText(path)

    # ------------------------------------------------------------------
    def _on_gpkg_changed(self):
        path = self.gpkg_edit.text().strip()
        self.layer_combo.clear()
        if path and os.path.exists(path):
            layers = gpkg_layers(path)
            self.layer_combo.addItems(layers)

    def _log(self, message):
        self.log.append(message)
        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()

    def _opts(self):
        return {
            "gpkg_path": self.gpkg_edit.text().strip(),
            "layer_name": self.layer_combo.currentText(),
            "qpt_path": self.qpt_edit.text().strip(),
            "ecw_path": self.ecw_edit.text().strip() or None,
            "output_dir": self.output_edit.text().strip(),
            "scale": self.scale_combo.currentText(),
            "parcel_color": self.parcel_color_combo.currentText(),
            "text_color": self.text_color_combo.currentText(),
            "with_imagery": self.with_imagery_check.isChecked(),
            "without_imagery": self.without_imagery_check.isChecked(),
            "output_format": "zip" if self.format_combo.currentText() == "PDF+ZIP" else "pdf",
            "date": self.date_edit.text().strip(),
            "pbt_number": self.pbt_edit.text().strip(),
            "block": self.block_edit.text().strip(),
            "logo_path": self.logo_edit.text().strip() or None,
            "surveyor_path": self.surveyor_edit.text().strip() or None,
            "leader_path": self.leader_edit.text().strip() or None,
            "first_sheet_only": self.first_only_check.isChecked(),
            "save_qgs": self.save_qgs_check.isChecked(),
            "coord_system": self.coord_combo.currentText(),
            "area_kind": "Desa" if self.area_desa_radio.isChecked() else "Kelurahan",
            "area_name": self.area_edit.text().strip(),
            "admin_kind": "Kabupaten" if self.admin_kab_radio.isChecked() else "Kota",
            "admin_name": self.admin_edit.text().strip(),
            "kecamatan": self.kecamatan_edit.text().strip(),
            "provinsi": self.provinsi_edit.text().strip(),
            "surveyor_name": self.surveyor_name_edit.text().strip(),
            "surveyor_license": self.surveyor_license_edit.text().strip(),
            "leader_org": self.leader_org_edit.text().strip(),
            "leader_name": self.leader_name_edit.text().strip(),
            "leader_position": self.leader_position_edit.text().strip(),
            "usage_role": self.usage_role_edit.text().strip(),
            "usage_name": self.usage_name_edit.text().strip(),
            "usage_nip": self.usage_nip_edit.text().strip(),
            "executor_pt": self.executor_pt_edit.text().strip(),
            "executor_address": self.executor_address_edit.text().strip(),
            "log": self._log,
        }

    def _validate_common(self):
        opts = self._opts()
        if not opts["gpkg_path"] or not os.path.exists(opts["gpkg_path"]):
            raise ValueError("Pilih file GeoPackage yang ada.")
        if not opts["layer_name"]:
            raise ValueError("Pilih layer di dalam GeoPackage.")
        if not opts["qpt_path"] or not os.path.exists(opts["qpt_path"]):
            raise ValueError("Pilih template QPT yang ada.")
        if not opts["output_dir"]:
            raise ValueError("Pilih folder output.")
        return opts

    def _refresh_license_ui(self):
        active = lic.is_activated()
        self.license_status.setText(lic.status_text())
        self.code_edit.setEnabled(not active)
        self.activate_button.setEnabled(not active)
        self.count_button.setEnabled(active)
        self.generate_button.setEnabled(active)

    def _on_api_changed(self):
        """Simpan URL API lisensi; ganti mode validasi. Bila API baru
        diisi dan ada aktivasi lokal, konfirmasi sekali ke server."""
        url = self.api_edit.text().strip()
        lic.set_api_base(url)
        self.settings.setValue(lic.LICENSE_KEY_API, url)
        if url:
            lic.ensure_server_activation()
            self._log("API lisensi: mode server.")
        else:
            self._log("API lisensi: mode lokal.")
        self._refresh_license_ui()

    def _on_activate(self):
        code = self.code_edit.text().strip()
        if not code:
            self._log("Gagal: masukkan kode akses beta.")
            return
        ok, msg = lic.activate(code)
        self._log(("Aktif: " if ok else "Gagal: ") + msg)
        self._refresh_license_ui()

    def _on_count(self):
        if not lic.is_activated():
            self._log("Gagal: masukkan kode akses beta dulu.")
            return
        try:
            opts = self._validate_common()
            from qgis.core import QgsVectorLayer

            layer = QgsVectorLayer(
                "{}|layername={}".format(opts["gpkg_path"], opts["layer_name"]),
                opts["layer_name"],
                "ogr",
            )
            if not layer.isValid():
                raise ValueError("Layer tidak bisa dibuka.")
            if layer.crs().isGeographic():
                raise ValueError("CRS layer geografis (derajat) — reproyeksikan dulu.")
            boxes, _fields = engine.read_feature_boxes(
                layer, engine.detect_pk_column(layer)
            )
            layout = engine.load_layout(opts["qpt_path"])
            map_item = engine._find_item_by_id_ci(layout, "Map 1")
            if map_item is None:
                from qgis.core import QgsLayoutItemMap

                for item in layout.items():
                    if isinstance(item, QgsLayoutItemMap):
                        map_item = item
                        break
            rect = map_item.rect()
            groups = engine.group_feature_boxes(
                list(boxes), opts["scale"], (rect.width(), rect.height())
            )
            self._log(
                "Lembar: {} — jumlah bidang per lembar: {}".format(
                    len(groups),
                    ", ".join(str(len(g.feature_ids)) for g in groups),
                )
            )
            for g in groups:
                for w in g.warnings:
                    self._log("Peringatan {}: {}".format(g.id, w))
        except Exception as exc:
            self._log("Gagal: {}".format(exc))

    def _on_generate(self):
        if not lic.is_activated():
            self._log("Gagal: masukkan kode akses beta dulu.")
            return
        # v0.5.0: 1 Generate = 1 generate kuota. Potong DULU di server
        # (mode server) supaya generate yang gagal di tengah jalan tetap
        # terhitung — kuota tidak bisa diakali dengan membatalkan.
        ok, msg, _remaining = lic.consume_generate()
        if not ok:
            self._log("Gagal: {}".format(msg))
            self._refresh_license_ui()
            return
        self._log("Kuota: {}".format(msg))
        try:
            opts = self._validate_common()
            self.generate_button.setEnabled(False)
            result = engine.render_batch(opts)
            self._log(
                "Selesai: {} PDF{}".format(
                    len(result["pdfs"]),
                    " + ZIP {}".format(os.path.basename(result["zip"]))
                    if result["zip"]
                    else "",
                )
                + (
                    " + QGS {}".format(os.path.basename(result["qgs"]))
                    if result.get("qgs")
                    else ""
                )
            )
            for w in result["warnings"]:
                self._log("Peringatan: {}".format(w))
            self._save_history(opts, result)
        except Exception as exc:
            self._log("Gagal: {}".format(exc))
        finally:
            self.generate_button.setEnabled(lic.is_activated())
            self._refresh_license_ui()

    # ------------------------------------------------------------------
    def _load_history(self):
        try:
            raw = self.settings.value(HISTORY_KEY, "[]")
            entries = json.loads(raw)
        except Exception:
            entries = []
        self.history_list.clear()
        for entry in entries:
            self.history_list.addItem(
                "{} — {} lembar, {} PDF — {}".format(
                    entry.get("date", "?"),
                    entry.get("sheets", "?"),
                    entry.get("pdfCount", "?"),
                    entry.get("gpkgName", "?"),
                )
            )
        self._history_entries = entries

    def _save_history(self, opts, result):
        entries = getattr(self, "_history_entries", [])
        from datetime import datetime

        entries.insert(
            0,
            {
                "date": datetime.now().isoformat(timespec="seconds"),
                "gpkgName": os.path.basename(opts["gpkg_path"]),
                "sheets": len(result["groups"]),
                "pdfCount": len(result["pdfs"]),
                "zipName": os.path.basename(result["zip"]) if result["zip"] else None,
                "outputDir": opts["output_dir"],
                "scale": opts["scale"],
            },
        )
        entries = entries[:HISTORY_MAX]
        self.settings.setValue(HISTORY_KEY, json.dumps(entries))
        self._load_history()

    def _on_history_double_click(self, item):
        entries = getattr(self, "_history_entries", [])
        index = self.history_list.row(item)
        if 0 <= index < len(entries):
            self.output_edit.setText(entries[index].get("outputDir", ""))

    def _clear_history(self):
        self.settings.setValue(HISTORY_KEY, "[]")
        self._load_history()
