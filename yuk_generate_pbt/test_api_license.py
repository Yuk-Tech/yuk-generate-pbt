#!/usr/bin/env python3
"""Uji lisensi server v0.5.0 lawan API TIRUAN (mock Supabase) — headless.

Mock (di dalam file ini, thread HTTP lokal) meniru persis semantik dua
Edge Function: validate-code dan consume-generate, dengan store
in-memory yang di-seed hash kode uji (5 generate) + satu hash kode beta
asli (5 generate).

Memeriksa:
  1. Mode lokal tetap jalan (validate_code terhadap CODE_HASHES).
  2. Mode server: aktivasi -> sisa 5; konsumsi 5x -> 4,3,2,1,0;
     konsumsi ke-6 ditolak; validasi saat habis ditolak; kode salah
     ditolak; habis kuota -> is_activated False + status "sudah habis".
  2b. Serangan hash-only (v0.5.2): consume-generate yang hanya
     membawa code_hash (hash publik dari kode plugin) DITOLAK dan
     kuota tidak berkurang.
  2c. Migrasi: aktivasi lama (hanya hash, tanpa kode tersimpan) tidak
     aktif; masukkan ulang kode -> aktif + kode tersimpan.
  3. Panel: kolom API tersimpan, aktivasi lewat panel menghidupkan
     tombol, status menampilkan sisa generate dari server.
  4. Server mati: validasi + konsumsi gagal dengan pesan yang jelas,
     tanpa exception (Generate harus ditolak, bukan jalan gratis).
"""
import hashlib
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/tmp/poc")

from qgis.core import QgsApplication

QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], True)  # GUI on (offscreen)
qgs.initQgis()

from qgis.PyQt.QtWidgets import QApplication

from yuk_generate_pbt import license as lic
from yuk_generate_pbt.panel import YukGeneratePbtPanel

TEST_CODE = "YUK-TEST-000001"
REAL_CODE = "YUK-4KEUCW-HP2W2S"  # salah satu dari 10 kode beta asli


def _canon(code):
    return (code or "").replace("-", "").replace(" ", "").upper()


def _hash(code):
    return hashlib.sha256(_canon(code).encode("ascii")).hexdigest()


# --- Mock API (semantik sama dengan Edge Function) ---
class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.codes = {
            _hash(TEST_CODE): {"remaining": 5, "expires": "2026-12-31"},
            _hash(REAL_CODE): {"remaining": 5, "expires": "2026-12-31"},
        }


STORE = Store()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send({"valid": False, "ok": False, "reason": "JSON rusak."}, 400)
        h = body.get("code_hash")
        if not h and body.get("code"):
            h = _hash(body["code"])
        if self.path.endswith("/validate-code"):
            if not h:
                return self._send({"valid": False, "reason": "Kode kosong."})
            row = STORE.codes.get(h)
            if not row:
                return self._send({"valid": False, "reason": "Kode tidak dikenal."})
            if row["expires"] < "2026-11-20":
                return self._send({"valid": False, "reason": "Masa beta berakhir 31 Des 2026."})
            if row["remaining"] <= 0:
                return self._send({"valid": False, "reason": "Kode ini sudah habis (0 generate tersisa)."})
            return self._send({
                "valid": True, "code_hash": h,
                "generates_remaining": row["remaining"],
                "expires_at": row["expires"],
            })
        if self.path.endswith("/consume-generate"):
            # v0.5.2: WAJIB kode asli. Hash saja ditolak — hash-nya publik
            # (ada di kode plugin), jadi hash tidak boleh cukup untuk
            # memakai kuota.
            if not body.get("code"):
                return self._send({"ok": False, "reason": "code wajib diisi."})
            h = _hash(body["code"])
            with STORE.lock:
                row = STORE.codes.get(h)
                if not row:
                    return self._send({"ok": False, "reason": "Kode tidak dikenal."})
                if row["expires"] < "2026-11-20":
                    return self._send({"ok": False, "reason": "Masa beta berakhir 31 Des 2026."})
                if row["remaining"] <= 0:
                    return self._send({"ok": False, "reason": "Kode ini sudah habis (0 generate tersisa)."})
                row["remaining"] -= 1
                return self._send({"ok": True, "generates_remaining": row["remaining"]})
        return self._send({"error": "unknown path"}, 404)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
MOCK_URL = "http://127.0.0.1:{}".format(port)
print("mock API di", MOCK_URL)

# --- Bersihkan state ---
lic.deactivate()
lic.set_api_base("")

# --- 1. mode lokal tetap jalan ---
ok, msg = lic.validate_code(REAL_CODE)
assert ok, "mode lokal: kode beta asli harus valid: {}".format(msg)
print("1. mode lokal OK")

# --- 2. mode server: aktivasi + konsumsi 5x + habis ---
lic.set_api_base(MOCK_URL)
lic._settings().setValue(lic.LICENSE_KEY_API, MOCK_URL)
ok, msg, info = lic.validate_code_server(TEST_CODE)
assert ok and info["generates_remaining"] == 5, "validasi server gagal: {}".format(msg)
ok, msg = lic.activate(TEST_CODE)
assert ok and "sisa 5 generate" in msg, "aktivasi server gagal: {}".format(msg)
assert lic.remaining_generates() == 5, "sisa tersimpan harus 5"
assert "sisa 5 generate" in lic.status_text(), "status salah: {}".format(lic.status_text())
for expect in (4, 3, 2, 1, 0):
    ok, msg, left = lic.consume_generate()
    assert ok and left == expect, "konsumsi -> {} gagal: {}".format(expect, msg)
assert lic.remaining_generates() == 0
assert not lic.is_activated(), "habis kuota harus tidak aktif"
assert "sudah habis" in lic.status_text(), "status habis salah: {}".format(lic.status_text())
ok, msg, _ = lic.consume_generate()
assert not ok and "habis" in msg, "konsumsi ke-6 harus ditolak: {}".format(msg)
ok, msg, _ = lic.validate_code_server(TEST_CODE)
assert not ok and "habis" in msg, "validasi saat habis harus ditolak: {}".format(msg)
ok, msg, _ = lic.validate_code_server("YUK-SALAH-XXXXXX")
assert not ok and "tidak dikenal" in msg, "kode salah harus ditolak: {}".format(msg)
print("2. mode server OK (aktivasi + 5x konsumsi + habis + kode salah)")

# --- 2b. serangan hash-only: hash publik TIDAK boleh memakai kuota ---
import urllib.request
req = urllib.request.Request(
    MOCK_URL + "/consume-generate",
    data=json.dumps({"code_hash": _hash(TEST_CODE)}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=15) as resp:
    res = json.loads(resp.read().decode("utf-8"))
assert not res.get("ok") and "code wajib diisi" in res.get("reason", ""), (
    "serangan hash-only harus ditolak: {}".format(res)
)
# Sisa kuota kode uji tetap 0 karena sudah habis di langkah 2 — pakai
# kode asli untuk memastikan hash-only tidak mengurangi apa pun.
req = urllib.request.Request(
    MOCK_URL + "/consume-generate",
    data=json.dumps({"code_hash": _hash(REAL_CODE)}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=15) as resp:
    res = json.loads(resp.read().decode("utf-8"))
assert not res.get("ok"), "serangan hash-only harus ditolak: {}".format(res)
ok, msg, info = lic.validate_code_server(REAL_CODE)
assert ok and info["generates_remaining"] == 5, (
    "kuota kode asli harus utuh 5 setelah serangan hash-only: {}".format(msg)
)
print("2b. serangan hash-only OK (ditolak, kuota utuh)")

# --- 2c. migrasi: aktivasi lama (hanya hash, tanpa kode) tidak aktif ---
lic.deactivate()
lic._settings().setValue(lic.LICENSE_KEY_HASH, _hash(REAL_CODE))
lic._settings().setValue(lic.LICENSE_KEY_SERVER, "true")
lic._settings().setValue(lic.LICENSE_KEY_REMAINING, 5)
assert not lic.is_activated(), "aktivasi lama tanpa kode harus tidak aktif"
assert "Belum aktif" in lic.status_text(), "status migrasi salah: {}".format(lic.status_text())
ok, msg = lic.activate(REAL_CODE)
assert ok and "sisa 5 generate" in msg, "masukkan ulang kode harus aktif: {}".format(msg)
assert lic.stored_code() == REAL_CODE, "kode asli harus tersimpan"
print("2c. migrasi OK (aktivasi lama ditolak, masukkan ulang kode aktif)")

# --- 3. panel: aktivasi kode asli lewat UI, sisa tampil dari server ---
lic.deactivate()
panel = YukGeneratePbtPanel()
QApplication.processEvents()
assert panel.api_edit.text() == MOCK_URL, "kolom API harus berisi URL mock"
assert not panel.generate_button.isEnabled(), "Generate harus MATI sebelum aktivasi"
panel.code_edit.setText(REAL_CODE)
panel._on_activate()
QApplication.processEvents()
assert panel.generate_button.isEnabled(), "Generate harus HIDUP setelah aktivasi"
assert "sisa 5 generate" in panel.license_status.text(), (
    "status panel salah: {}".format(panel.license_status.text())
)
ok, msg, left = lic.consume_generate()
assert ok and left == 4, "konsumsi lewat panel gagal: {}".format(msg)
panel._refresh_license_ui()
assert "sisa 4 generate" in panel.license_status.text(), (
    "status panel harus 4: {}".format(panel.license_status.text())
)
print("3. panel OK (API tersimpan + aktivasi + status sisa 4)")

# --- 4. server mati: gagal jelas, tanpa exception ---
server.shutdown()
server.server_close()
ok, msg, _ = lic.validate_code_server(REAL_CODE)
assert not ok and "Tidak bisa terhubung" in msg, "server mati harus gagal jelas: {}".format(msg)
ok, msg, _ = lic.consume_generate()
assert not ok and "Tidak bisa terhubung" in msg, "konsumsi saat server mati harus gagal jelas: {}".format(msg)
print("4. server mati OK (pesan jelas, tanpa crash)")

# --- Bersihkan ---
lic.deactivate()
lic._settings().remove(lic.LICENSE_KEY_API)
lic.set_api_base("")
print("API LISENSI: LULUS — lokal + server + hash-only ditolak + migrasi + panel + server mati")
os._exit(0)
