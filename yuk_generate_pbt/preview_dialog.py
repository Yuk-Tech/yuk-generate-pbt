"""Dialog Preview plugin Yuk Generate PBT! (v0.6.2).

Menampilkan hasil render_preview TANPA memakai kuota: tabel lembar
(skala, jumlah bidang, fill, rasio label, peringatan) + gambar preview
tiap lembar (PNG resolusi rendah) yang bisa digeser.

Tombol "Generate (pakai 1 kuota)" menutup dialog dengan Accepted —
panel yang memanggil lalu menjalankan alur Generate yang sudah ada
(validate fresh + consume 1 + export PDF + ZIP). Tombol "Tutup"
menutup dengan Rejected — kuota tetap utuh.

Dialog ini TIDAK memanggil fungsi lisensi apa pun (tidak ada
consume/validate di sini); sisa generate yang ditampilkan berasal
dari argumen `remaining` (hasil validate terakhir yang tersimpan).
"""
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


def _enum_value(cls, scoped_name, member, fallback):
    """Konstanta enum Qt yang berpindah nama di PyQt6 (scoped) vs PyQt5
    (flat) — pola yang sama dengan panel.py."""
    scoped = getattr(cls, scoped_name, None)
    if scoped is not None:
        return getattr(scoped, member, fallback)
    return getattr(cls, member, fallback)


ALIGN_CENTER = _enum_value(Qt, "AlignmentFlag", "AlignCenter", 0x0004)
KEEP_ASPECT = _enum_value(Qt, "AspectRatioMode", "KeepAspectRatio", 1)
SMOOTH = _enum_value(Qt, "TransformationMode", "SmoothTransformation", 1)
NO_EDIT = _enum_value(QAbstractItemView, "EditTrigger", "NoEditTriggers", 0)


class PreviewDialog(QDialog):
    """Dialog preview lembar PBT (tanpa kuota).

    preview: dict hasil engine.render_preview (images, groups, metrics,
    warnings, qgs, temp_dir). remaining: sisa generate tersimpan
    (int) atau None bila mode lokal (generate tidak dihitung)."""

    def __init__(self, preview, remaining, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.remaining = remaining
        self._index = 0
        self.setWindowTitle("Preview — Yuk Generate PBT!")
        self.setMinimumSize(760, 620)
        self._build_ui()
        self._fill_table()
        self._show_image(0)

    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QLabel("<b>PREVIEW — belum pakai kuota</b>")
        header.setAlignment(ALIGN_CENTER)
        root.addWidget(header)
        if self.remaining is None:
            info = "Mode lokal — generate tidak dihitung."
        else:
            info = (
                "Sisa generate: {} — tombol Generate di bawah memakai 1 kuota."
            ).format(self.remaining)
        self.info_label = QLabel(info)
        self.info_label.setAlignment(ALIGN_CENTER)
        self.info_label.setWordWrap(True)
        root.addWidget(self.info_label)

        metrics = self.preview["metrics"]
        self.sheet_table = QTableWidget()
        self.sheet_table.setColumnCount(6)
        self.sheet_table.setHorizontalHeaderLabels(
            ["Lembar", "Skala", "Bidang", "Fill", "Rasio label", "Peringatan"]
        )
        self.sheet_table.setRowCount(len(metrics))
        self.sheet_table.setEditTriggers(NO_EDIT)
        self.sheet_table.setSelectionBehavior(
            _enum_value(
                QAbstractItemView, "SelectionBehavior", "SelectRows", 0
            )
        )
        self.sheet_table.cellClicked.connect(self._on_table_click)
        root.addWidget(self.sheet_table)

        self.image_label = QLabel("Memuat gambar preview…")
        self.image_label.setAlignment(ALIGN_CENTER)
        self.image_label.setMinimumSize(640, 400)
        root.addWidget(self.image_label)

        nav = QHBoxLayout()
        self.prev_button = QPushButton("◀ Sebelumnya")
        self.prev_button.clicked.connect(self._on_prev)
        self.sheet_combo = QComboBox()
        for m in metrics:
            self.sheet_combo.addItem(
                "{} — {} ({} bidang)".format(m["id"], m["scale"], m["count"])
            )
        self.sheet_combo.currentIndexChanged.connect(self._on_combo)
        self.next_button = QPushButton("Berikutnya ▶")
        self.next_button.clicked.connect(self._on_next)
        nav.addWidget(self.prev_button)
        nav.addWidget(self.sheet_combo, 1)
        nav.addWidget(self.next_button)
        root.addLayout(nav)

        self.caption_label = QLabel("")
        self.caption_label.setAlignment(ALIGN_CENTER)
        self.caption_label.setWordWrap(True)
        root.addWidget(self.caption_label)

        buttons = QHBoxLayout()
        self.generate_button = QPushButton("Generate (pakai 1 kuota)")
        self.generate_button.clicked.connect(self.accept)
        self.close_button = QPushButton("Tutup")
        self.close_button.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)

    # ------------------------------------------------------------------
    def _fill_table(self):
        for row, m in enumerate(self.preview["metrics"]):
            warns = "; ".join(m["warnings"]) if m["warnings"] else "—"
            values = [
                m["id"],
                m["scale"],
                str(m["count"]),
                "{:.2f}".format(m["fill"]),
                "{:.2f}".format(m["ratio"]),
                warns,
            ]
            for col, value in enumerate(values):
                self.sheet_table.setItem(row, col, QTableWidgetItem(value))
        self.sheet_table.resizeColumnsToContents()

    def _show_image(self, index):
        images = self.preview["images"]
        metrics = self.preview["metrics"]
        if not images or not metrics:
            self.image_label.setText("Tidak ada lembar untuk di-preview.")
            self.caption_label.setText("")
            return
        index = max(0, min(index, len(images) - 1))
        self._index = index
        path = images[index]
        pix = QPixmap(path)
        if pix.isNull() or not os.path.exists(path):
            self.image_label.setText("Gambar preview tidak tersedia.")
        else:
            # Sebelum dialog tampil, size() label bisa (0,0) — pakai
            # minimumSize sebagai fallback supaya pixmap tidak 0 px.
            size = self.image_label.size()
            if size.width() < 100 or size.height() < 100:
                size = self.image_label.minimumSize()
            scaled = pix.scaled(size, KEEP_ASPECT, SMOOTH)
            self.image_label.setPixmap(scaled)
        m = metrics[index]
        self.caption_label.setText(
            "{} — {} · {} bidang · fill {:.2f} · rasio label {:.2f}".format(
                m["id"], m["scale"], m["count"], m["fill"], m["ratio"]
            )
        )
        if self.sheet_combo.currentIndex() != index:
            self.sheet_combo.setCurrentIndex(index)
        if self.sheet_table.currentRow() != index:
            self.sheet_table.selectRow(index)
        self.prev_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(images) - 1)

    def _on_table_click(self, row, _col):
        self._show_image(row)

    def _on_combo(self, index):
        if index >= 0:
            self._show_image(index)

    def _on_prev(self):
        self._show_image(self._index - 1)

    def _on_next(self):
        self._show_image(self._index + 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Gambar di-scale ulang mengikuti ukuran label (jendela diubah).
        if self.preview["images"]:
            self._show_image(self._index)
