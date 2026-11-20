"""Gerbang kode akses beta plugin Yuk Generate PBT! (v0.5.2).

Dua mode validasi:

1. MODE LOKAL (bila API lisensi dikosongkan): kode diperiksa terhadap
   hash SHA-256 di CODE_HASHES, seperti v0.4.x. Kuota generate TIDAK
   dihitung — mode ini hanya untuk pemakaian sendiri / darurat.
2. MODE SERVER (bawaan v0.5.1: server Supabase produksi — lihat
   DEFAULT_API_BASE_URL): kode divalidasi ke endpoint Supabase
   validate-code, dan SETIAP Generate memotong 1 generate lewat
   consume-generate. Kuota beta: 5 generate per kode, berlaku
   s.d. 31 Des 2026. Penghitungan di server — plugin tidak bisa
   mengakali kuota sendiri, karena plugin ini GPL dan kodenya terbuka.

PERBAIKAN KEAMANAN (v0.5.2): consume-generate WAJIB memakai kode ASLI.
Versi 0.5.0/0.5.1 mengirim hash tersimpan — padahal hash-nya tercantum
di kode plugin (terbuka), sehingga siapa pun bisa menguras kuota semua
kode beta tanpa tahu kodenya. Sekarang kode asli disimpan di QSettings
(mesin pengguna sendiri) dan dikirim ke server, yang menghitung
hash-nya di sana. Hash saja tidak cukup. Aktivasi lama (hanya hash,
tanpa kode) dianggap tidak aktif — pengguna memasukkan ulang kodenya
sekali (validasi tidak memotong kuota).

Yang disimpan di plugin: kode asli + hash SHA-256-nya, sisa generate,
tanggal kedaluwarsa, dan URL API. Daftar plaintext untuk dibagikan ada
di beta-codes-YYYY-MM-DD.txt (JANGAN masuk repo/zip).

Batasan yang jujur: gerbang ini gerbang lunak. Siapa pun bisa menghapus
pengecekan dari salinan pluginnya. Perlindungan sesungguhnya adalah
server (kuota dihitung di sana) — dan nanti langganan QRIS per lembar.

Fungsi murni (canonical/code_hash/validate_code) tidak butuh QGIS,
supaya bisa diuji tanpa QGIS. Penyimpanan status + panggilan API
memakai QSettings / urllib (stdlib saja).
"""

import hashlib
import json
import urllib.error
import urllib.request
from datetime import date

# Masa beta berakhir — setelah tanggal ini semua kode beta ditolak.
BETA_EXPIRES = "2026-12-31"

# Kuota beta per kode (generate). Satu generate = satu batch.
BETA_GENERATES_PER_CODE = 5

# Hash SHA-256 bentuk kanonik kode beta (huruf besar, tanpa tanda
# hubung). Dipakai HANYA untuk mode lokal. Dibangkitkan 2026-11-20,
# 10 kode. Untuk menambah kode: jalankan gen_beta_codes.py lalu tempel
# hash barunya di sini (dan/atau seed ke Supabase — lihat
# supabase-api/schema.sql).
CODE_HASHES = {
    "136a279c2364c7d02ea759e8239710d50d7e7b0d6156b9e73497bb3a0540b643",  # pragma: allowlist secret
    "32bf3d308e37d2afaf0f1c359e107509de5d49b456c1daa89216270524bd61ed",  # pragma: allowlist secret
    "3b8f19f9af0614948cc6dc591d2fb49aaebd92eb5239e2620225b88916cf5a22",  # pragma: allowlist secret
    "6fb638c2f60d17a25382aacf7d23e01ca959e248ecbb939f9322250822565014",  # pragma: allowlist secret
    "87b2cd963aa93abfa8001e49a0f4f64a383695e71782487642e9c01ae3855d96",  # pragma: allowlist secret
    "9beda863a473e925e058a7a78494f6648240be4e98e6fcca447cd3dd88a9a599",  # pragma: allowlist secret
    "a455038d3e3e2874d82beb8e17ddef6e18b5ed70a0cc2c2812f992528a897a38",  # pragma: allowlist secret
    "aab677228accfd360c4a4c69f19419903942db881af50ec57c2b915b13f7f3b8",  # pragma: allowlist secret
    "c76a4c48b3e1a042b70b0b4a56e6807b66ff78eec5b73b10a9486ad5d8de8565",  # pragma: allowlist secret
    "d77b8d867c449f8deb32873ad165399d01e5e7813ee4ca7f247a06362d89123a",  # pragma: allowlist secret
}

LICENSE_KEY_HASH = "license/code_hash"
LICENSE_KEY_CODE = "license/code"
LICENSE_KEY_DATE = "license/activated_on"
LICENSE_KEY_REMAINING = "license/generates_remaining"
LICENSE_KEY_EXPIRES = "license/expires_at"
LICENSE_KEY_SERVER = "license/server_validated"
LICENSE_KEY_API = "license/api_base"
SETTINGS_ORG = "YukGeneratePBT"
SETTINGS_APP = "YukGeneratePBT"

# URL dasar API lisensi bawaan (v0.5.1): server Supabase produksi.
# Penguji beta tidak perlu mengisi kolom API lagi — cukup masukkan kode.
# Kolom API di panel tetap ada sebagai override (mis. pindah server);
# mengosongkannya berarti mode lokal. URL ini BUKAN rahasia (endpoint
# publik; yang jadi kredensial adalah kode aksesnya).
DEFAULT_API_BASE_URL = "https://hjqmyjrjiktvdqgjkrvp.supabase.co/functions/v1"

# URL dasar API lisensi aktif (tanpa garis miring di akhir).
# Diatur panel dari QSettings saat startup (lihat panel.py); bila belum
# pernah diatur, dipakai DEFAULT_API_BASE_URL.
API_BASE_URL = DEFAULT_API_BASE_URL

API_TIMEOUT = 15  # detik


def set_api_base(url):
    """Atur URL dasar API lisensi ("" = mode lokal)."""
    global API_BASE_URL
    API_BASE_URL = (url or "").strip().rstrip("/")


def get_api_base():
    """URL dasar API lisensi saat ini ("" bila mode lokal)."""
    return API_BASE_URL


def canonical(code):
    """Bentuk kanonik kode: huruf besar, tanpa tanda hubung/spasi."""
    return (code or "").replace("-", "").replace(" ", "").upper()


def code_hash(code):
    """SHA-256 hex bentuk kanonik kode."""
    return hashlib.sha256(canonical(code).encode("ascii")).hexdigest()


def is_expired(today=None):
    """True bila masa beta sudah lewat (pakai tanggal kedaluwarsa
    tersimpan bila ada, kalau tidak pakai BETA_EXPIRES)."""
    today = today or date.today().isoformat()
    expires = BETA_EXPIRES
    try:
        stored = _settings().value(LICENSE_KEY_EXPIRES, "")
        if stored:
            expires = stored
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass
    return today > expires


def validate_code(code, today=None):
    """Periksa kode beta MODE LOKAL. Kembali (ok, pesan)."""
    if is_expired(today):
        return False, "Masa beta berakhir 31 Des 2026."
    if code_hash(code) in CODE_HASHES:
        return True, "Kode valid."
    return False, "Kode tidak dikenal."


# ------------------------------------------------------------------
# Mode server (Supabase Edge Functions)
# ------------------------------------------------------------------
def _api_post(path, payload):
    """POST JSON ke API lisensi. Kembali dict hasil. Raise bila
    jaringan/server bermasalah (pemanggil yang mengubahnya jadi pesan)."""
    url = "{}{}".format(API_BASE_URL, path)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "YukGeneratePBT/0.5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:  # nosec B310  # hanya HTTPS ke endpoint API lisensi (Supabase); sertifikat diverifikasi default urllib
        return json.loads(resp.read().decode("utf-8"))


def validate_code_server(code):
    """Validasi kode ke server. Kembali (ok, pesan, info) — info berisi
    code_hash / generates_remaining / expires_at bila valid."""
    try:
        res = _api_post("/validate-code", {"code": code})
    except urllib.error.URLError as exc:
        return False, "Tidak bisa terhubung ke server lisensi: {}".format(exc.reason), None
    except Exception as exc:
        return False, "Tidak bisa terhubung ke server lisensi: {}".format(exc), None
    if res.get("valid"):
        return True, "Kode valid.", res
    return False, res.get("reason", "Kode tidak dikenal."), None


def validate_hash_server(code_hash_value):
    """Validasi hash tersimpan ke server (untuk migrasi aktivasi lokal
    ke mode server tanpa memasukkan ulang kode)."""
    try:
        res = _api_post("/validate-code", {"code_hash": code_hash_value})
    except Exception as exc:
        return False, "Tidak bisa terhubung ke server lisensi: {}".format(exc), None
    if res.get("valid"):
        return True, "Kode valid.", res
    return False, res.get("reason", "Kode tidak dikenal."), None


def consume_generate():
    """Pakai 1 generate untuk satu kali Generate. Dipanggil panel
    SEBELUM render. Kembali (ok, pesan, sisa).
    - Mode lokal: selalu ok (tidak dihitung).
    - Mode server: potong di server; bila server tidak terjangkau atau
      kuota habis, Generate DITOLAK (kuota tidak boleh diakali).
      Server yang memutuskan habis/tidaknya (sisa lokal bisa basi bila
      kode dipakai di mesin lain), jadi di sini tidak ada gate
      is_activated() — hanya kode tersimpan + masa berlaku.
      v0.5.2: yang dikirim adalah kode ASLI (hash saja tidak cukup —
      lihat perbaikan keamanan di docstring). code_hash ikut dikirim
      hanya untuk kompatibilitas transisi dengan function lama."""
    if not API_BASE_URL:
        if not is_activated():
            return False, "Masukkan kode akses beta dulu.", None
        return True, "Mode lokal — generate tidak dihitung.", None
    try:
        code = stored_code()
        stored = stored_hash()
    except Exception:
        code, stored = "", ""
    if not code:
        return False, "Masukkan kode akses beta dulu.", None
    if is_expired():
        return False, "Masa beta berakhir 31 Des 2026.", None
    try:
        res = _api_post("/consume-generate", {"code": code, "code_hash": stored})
    except urllib.error.URLError as exc:
        return False, "Tidak bisa terhubung ke server lisensi: {}".format(exc.reason), None
    except Exception as exc:
        return False, "Tidak bisa terhubung ke server lisensi: {}".format(exc), None
    if res.get("ok"):
        remaining = res.get("generates_remaining")
        try:
            _settings().setValue(LICENSE_KEY_REMAINING, remaining)
        except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
            pass
        return True, "Sisa {} generate.".format(remaining), remaining
    return False, res.get("reason", "Gagal memakai generate."), None


# ------------------------------------------------------------------
# Penyimpanan status
# ------------------------------------------------------------------
def _settings():
    from qgis.PyQt.QtCore import QSettings

    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def stored_hash():
    """Hash kode yang tersimpan ("" bila belum aktivasi)."""
    try:
        return _settings().value(LICENSE_KEY_HASH, "") or ""
    except Exception:
        return ""


def stored_code():
    """Kode asli yang tersimpan ("" bila belum aktivasi / aktivasi lama
    v0.5.0-0.5.1 yang hanya menyimpan hash). Kode ini milik pengguna
    sendiri di mesinnya — dipakai untuk consume-generate (v0.5.2:
    server wajib menerima kode asli, bukan hash)."""
    try:
        return _settings().value(LICENSE_KEY_CODE, "") or ""
    except Exception:
        return ""


def remaining_generates():
    """Sisa generate tersimpan (None bila mode lokal / tidak ada)."""
    try:
        raw = _settings().value(LICENSE_KEY_REMAINING, "")
        return int(raw) if raw != "" and raw is not None else None
    except Exception:
        return None


def is_server_validated():
    """True bila aktivasi tersimpan sudah dikonfirmasi server."""
    try:
        return _settings().value(LICENSE_KEY_SERVER, "") in ("true", True, 1)
    except Exception:
        return False


def is_activated():
    """True bila ada kode aktif tersimpan dan masa beta belum lewat.
    Mode server: habis kuota (sisa 0) berarti tidak aktif lagi, dan
    aktivasi lama yang hanya menyimpan hash (tanpa kode, v0.5.0-0.5.1)
    dianggap tidak aktif — pengguna memasukkan ulang kodenya sekali."""
    if is_expired():
        return False
    try:
        stored = stored_hash()
        if not stored:
            return False
        if API_BASE_URL:
            # Mode server: hash apa pun yang tersimpan dianggap aktif
            # selama sudah dikonfirmasi server (ensure_server_activation
            # yang mengurus konfirmasinya), masih ada sisa generate,
            # dan kode aslinya tersimpan (wajib sejak v0.5.2).
            if not is_server_validated():
                return False
            if not stored_code():
                return False
            remaining = remaining_generates()
            if remaining is not None and remaining <= 0:
                return False
            return True
        return stored in CODE_HASHES
    except Exception:
        return False


def ensure_server_activation():
    """Bila API diisi dan ada aktivasi lokal tersimpan yang belum
    dikonfirmasi server: validasi hash-nya ke server sekali. Berhasil
    -> simpan sisa generate + tandai tervalidasi. Gagal (kode dicabut /
    habis / server mati) -> hapus aktivasi supaya pengguna memasukkan
    ulang kode. Dipanggil panel sekali saat startup."""
    if not API_BASE_URL:
        return
    try:
        stored = stored_hash()
        if not stored or is_server_validated():
            return
        ok, _msg, info = validate_hash_server(stored)
        if ok and info:
            settings = _settings()
            settings.setValue(LICENSE_KEY_REMAINING, info.get("generates_remaining"))
            settings.setValue(LICENSE_KEY_EXPIRES, info.get("expires_at", BETA_EXPIRES))
            settings.setValue(LICENSE_KEY_SERVER, "true")
        else:
            deactivate()
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass


def activate(code):
    """Validasi kode (server bila API diisi, lokal bila kosong) lalu
    simpan status aktif. Kembali (ok, pesan)."""
    if API_BASE_URL:
        ok, msg, info = validate_code_server(code)
        if not ok:
            return False, msg
        try:
            settings = _settings()
            settings.setValue(LICENSE_KEY_HASH, info.get("code_hash", code_hash(code)))
            settings.setValue(LICENSE_KEY_CODE, code)
            settings.setValue(LICENSE_KEY_DATE, date.today().isoformat())
            settings.setValue(LICENSE_KEY_REMAINING, info.get("generates_remaining"))
            settings.setValue(LICENSE_KEY_EXPIRES, info.get("expires_at", BETA_EXPIRES))
            settings.setValue(LICENSE_KEY_SERVER, "true")
        except Exception as exc:
            return False, "Gagal menyimpan aktivasi: {}".format(exc)
        return True, "Aktif — sisa {} generate (s.d. 31 Des 2026).".format(
            info.get("generates_remaining")
        )
    ok, msg = validate_code(code)
    if not ok:
        return False, msg
    try:
        settings = _settings()
        settings.setValue(LICENSE_KEY_HASH, code_hash(code))
        settings.setValue(LICENSE_KEY_CODE, code)
        settings.setValue(LICENSE_KEY_DATE, date.today().isoformat())
        settings.setValue(LICENSE_KEY_REMAINING, "")
        settings.setValue(LICENSE_KEY_EXPIRES, BETA_EXPIRES)
        settings.setValue(LICENSE_KEY_SERVER, "")
    except Exception as exc:
        return False, "Gagal menyimpan aktivasi: {}".format(exc)
    return True, "Aktif — berlaku sampai 31 Des 2026. (mode lokal)"


def deactivate():
    """Hapus status aktif (untuk uji / ganti kode)."""
    try:
        settings = _settings()
        for key in (
            LICENSE_KEY_HASH,
            LICENSE_KEY_CODE,
            LICENSE_KEY_DATE,
            LICENSE_KEY_REMAINING,
            LICENSE_KEY_EXPIRES,
            LICENSE_KEY_SERVER,
        ):
            settings.remove(key)
    except Exception:  # nosec B110  # best-effort: kegagalan opsional diabaikan
        pass


def status_text():
    """Teks status untuk panel."""
    if is_activated():
        remaining = remaining_generates()
        if API_BASE_URL and remaining is not None:
            return "Aktif — sisa {} generate (s.d. 31 Des 2026).".format(remaining)
        return "Aktif — berlaku sampai 31 Des 2026."
    if is_expired():
        return "Masa beta berakhir 31 Des 2026."
    if API_BASE_URL:
        remaining = remaining_generates()
        if remaining is not None and remaining <= 0:
            return "Kode ini sudah habis (0 generate tersisa) — masukkan kode baru."
    return "Belum aktif — masukkan kode akses beta."
