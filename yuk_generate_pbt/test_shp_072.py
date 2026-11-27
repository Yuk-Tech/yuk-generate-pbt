#!/usr/bin/env python3
"""Uji murni PBT v0.7.2 (tanpa QGIS): SHP persil PER LEMBAR + ZIP per lembar.

- sheet_shp_filename: pola nama + sanitasi (ikut output_filename,
  tanpa sufiks CITRA/TANPA_CITRA).
- sheet_parcel_ids: filter per lembar (persil biasa + SHM lolos;
  KET spesial + 'div:...' terbuang; urutan grup dipertahankan).
- zip_sheet_shp: 5 file komponen -> 1 ZIP (isi tepat 5 file, tanpa
  folder); file lepas dihapus setelah ZIP terverifikasi; .cpg dibuat
  bila tidak ada; komponen tidak lengkap -> (None, 0), file lepas
  dibiarkan.
- Ujung-ke-ujung murni: grouping sintetis (persil + pembagi poligon +
  pembagi garis) -> tiap lembar tepat berisi persilnya, gabungan semua
  lembar = semua persil tepat 1x, tanpa pembagi.
"""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, ".")
import engine  # noqa: E402

FAILURES = []
COUNT = [0]


def check(name, cond):
    COUNT[0] += 1
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILURES.append(name)


def box(fid, x0, y0, ket=None, w=20, h=20):
    return engine.FeatureBox(fid, [x0, y0, x0 + w, y0 + h], [], ket,
                             label_len=5, label_lines=3)


def test_filename():
    check("nama: pola dasar",
          engine.sheet_shp_filename("2091", "L01", "1:1000")
          == "PBTF_2091_L01_1-1000_persil.shp")
    check("nama: skala 1:2500",
          engine.sheet_shp_filename("2091", "L09", "1:2500")
          == "PBTF_2091_L09_1-2500_persil.shp")
    check("nama: tanpa sufiks CITRA/TANPA_CITRA",
          "CITRA" not in engine.sheet_shp_filename("2091", "L01", "1:1000"))
    check("nama: group_id aneh disanitasi",
          engine.sheet_shp_filename("2091", "L 01/x", "1:500")
          == "PBTF_2091_L_01_x_1-500_persil.shp")
    check("nama: beda dari nama PDF (tanpa .pdf, ada _persil)",
          engine.sheet_shp_filename("2091", "L01", "1:1000")
          != engine.output_filename("2091", "L01", "1:1000", True))
    check("nama: zip = stem SHP yang sama",
          engine.sheet_shp_filename("2091", "L01", "1:1000").replace(
              ".shp", ".zip") == "PBTF_2091_L01_1-1000_persil.zip")


def test_parcel_ids():
    ket_by_id = {"1": None, "2": "", "3": "JALAN", "4": "IRIGASI",
                 "5": None, "6": "GANG", "7": None}
    check("persil biasa + SHM lolos, spesial terbuang",
          engine.sheet_parcel_ids(["1", "2", "3", "4", "5", "6", "7"],
                                  ket_by_id) == ["1", "2", "5", "7"])
    check("'div:...' (pembagi garis) terbuang",
          engine.sheet_parcel_ids(["1", "div:9", "div:10"], ket_by_id)
          == ["1"])
    check("id tak dikenal terbuang",
          engine.sheet_parcel_ids(["1", "99"], ket_by_id) == ["1"])
    check("urutan grup dipertahankan",
          engine.sheet_parcel_ids(["7", "5", "1"], ket_by_id)
          == ["7", "5", "1"])
    check("grup kosong -> []",
          engine.sheet_parcel_ids([], ket_by_id) == [])
    check("KET None dihitung persil (bukan spesial)",
          engine.sheet_parcel_ids(["1"], {"1": None}) == ["1"])


def test_e2e_pure():
    # 2 lembar sintetis: lembar 1 = persil 1,2 + pembagi poligon 3 +
    # pembagi garis div:9; lembar 2 = persil 4,5 + pembagi poligon 6.
    boxes = [box("1", 0, 0), box("2", 30, 0), box("3", 60, 0, ket="JALAN"),
             box("4", 0, 100), box("5", 30, 100),
             box("6", 60, 100, ket="IRIGASI")]
    ket_by_id = {b.id: b.ket for b in boxes}
    groups = {"L01": ["1", "2", "3", "div:9"], "L02": ["4", "5", "6"]}
    got = {g: engine.sheet_parcel_ids(ids, ket_by_id)
           for g, ids in groups.items()}
    check("e2e: L01 = persil 1,2 saja", got["L01"] == ["1", "2"])
    check("e2e: L02 = persil 4,5 saja", got["L02"] == ["4", "5"])
    all_ids = [i for ids in got.values() for i in ids]
    check("e2e: gabungan = semua persil tepat 1x",
          sorted(all_ids) == ["1", "2", "4", "5"])
    check("e2e: tidak ada pembagi di SHP",
          all(i not in ("3", "6", "div:9") for i in all_ids))


def test_zip_sheet_shp():
    log_msgs = []

    def log(msg):
        log_msgs.append(msg)

    with tempfile.TemporaryDirectory() as d:
        stem = os.path.join(d, "PBTF_2091_L01_1-1000_persil")
        for ext, content in ((".shp", b"SHP"), (".shx", b"SHX"),
                             (".dbf", b"DBF"), (".prj", b"PRJ"),
                             (".cpg", b"UTF-8")):
            with open(stem + ext, "wb") as fh:
                fh.write(content)
        zp, n = engine.zip_sheet_shp(stem + ".shp", log)
        check("zip: terbentuk + 5 file",
              zp == stem + ".zip" and n == 5
              and os.path.exists(stem + ".zip"))
        with zipfile.ZipFile(stem + ".zip") as zf:
            names = sorted(zf.namelist())
        check("zip: isi tepat 5 komponen, tanpa folder",
              names == ["PBTF_2091_L01_1-1000_persil.cpg",
                        "PBTF_2091_L01_1-1000_persil.dbf",
                        "PBTF_2091_L01_1-1000_persil.prj",
                        "PBTF_2091_L01_1-1000_persil.shp",
                        "PBTF_2091_L01_1-1000_persil.shx"])
        check("zip: isi file benar (dbf)",
              zipfile.ZipFile(stem + ".zip").read(
                  "PBTF_2091_L01_1-1000_persil.dbf") == b"DBF")
        check("zip: file lepas dihapus semua",
              not any(os.path.exists(stem + e) for e in
                      (".shp", ".shx", ".dbf", ".prj", ".cpg")))
        check("zip: nama tidak bentrok dengan ZIP PDF (PBTF_2091.zip)",
              os.path.basename(stem + ".zip") != "PBTF_2091.zip")

        # .cpg tidak ada -> dibuat dulu, tetap 5 file.
        stem2 = os.path.join(d, "PBTF_2091_L02_1-500_persil")
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            with open(stem2 + ext, "wb") as fh:
                fh.write(b"x")
        zp2, n2 = engine.zip_sheet_shp(stem2 + ".shp", log)
        check("zip: .cpg dibuat bila tidak ada (tetap 5 file)",
              zp2 is not None and n2 == 5
              and "PBTF_2091_L02_1-500_persil.cpg" in
              zipfile.ZipFile(stem2 + ".zip").namelist())
        check("zip: .cpg berisi UTF-8",
              zipfile.ZipFile(stem2 + ".zip").read(
                  "PBTF_2091_L02_1-500_persil.cpg") == b"UTF-8")

        # Komponen tidak lengkap -> (None, 0), file lepas dibiarkan.
        stem3 = os.path.join(d, "PBTF_2091_L03_1-500_persil")
        for ext in (".shp", ".dbf"):
            with open(stem3 + ext, "wb") as fh:
                fh.write(b"x")
        zp3, n3 = engine.zip_sheet_shp(stem3 + ".shp", log)
        check("zip: komponen tidak lengkap -> (None, 0)",
              zp3 is None and n3 == 0)
        check("zip: file lepas dibiarkan bila ZIP gagal",
              os.path.exists(stem3 + ".shp")
              and os.path.exists(stem3 + ".dbf")
              and not os.path.exists(stem3 + ".zip"))


if __name__ == "__main__":
    test_filename()
    test_parcel_ids()
    test_e2e_pure()
    test_zip_sheet_shp()
    print("---")
    print("TOTAL: {} checks, {} failures".format(COUNT[0], len(FAILURES)))
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(" -", f)
        sys.exit(1)
    print("SEMUA LULUS")
