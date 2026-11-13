"""Structural test only: builds a tiny NetCDF laid out like an Argo multi-profile file (char arrays, JULD days since 1950)."""
import numpy as np, pandas as pd, pytest
nc = pytest.importorskip("netCDF4")
from convert_gdac import read_prof
from engine import REGIONS


def make(path):
    ds = nc.Dataset(path, "w")
    ds.createDimension("N_PROF", 3); ds.createDimension("N_LEVELS", 3); ds.createDimension("STRING8", 8); ds.createDimension("STRING1", 1)
    def chars(name, dims, rows):
        v = ds.createVariable(name, "S1", dims)
        w = dims[-1] == "STRING8"
        v[:] = nc.stringtochar(np.array(rows, dtype="S8" if w else "S1"))
    chars("PLATFORM_NUMBER", ("N_PROF", "STRING8"), ["2902745 ", "2902746 ", "2902747 "])
    ds.createVariable("CYCLE_NUMBER", "i4", ("N_PROF",))[:] = [12, 5, 7]
    juld = (pd.Timestamp("2024-01-03 06:00") - pd.Timestamp("1950-01-01")) / pd.Timedelta(days=1)
    ds.createVariable("JULD", "f8", ("N_PROF",))[:] = [juld, juld, juld]
    ds.createVariable("LATITUDE", "f8", ("N_PROF",))[:] = [15.0, 15.0, -30.0]   # third profile is outside the Arabian Sea
    ds.createVariable("LONGITUDE", "f8", ("N_PROF",))[:] = [65.0, 65.0, 80.0]
    chars("DIRECTION", ("N_PROF", "STRING1"), ["A", "D", "A"])                  # second is descending -> dropped
    for var, vals in [("PRES_ADJUSTED", [10, 500, 99999]), ("TEMP_ADJUSTED", [28, 12.5, 99999]), ("PSAL_ADJUSTED", [36, 35.1, 99999])]:
        v = ds.createVariable(var, "f4", ("N_PROF", "N_LEVELS"), fill_value=99999.0)
        v[:] = np.array([vals] * 3, dtype="f4")
        q = ds.createVariable(var + "_QC", "S1", ("N_PROF", "N_LEVELS"))
        q[:] = np.array([[b"1", b"1", b" "]] * 3, dtype="S1")
    ds.close()


def test_read_prof_matches_argo_layout(tmp_path):
    p = tmp_path / "20240103_prof.nc"
    make(p)
    df = read_prof(str(p), REGIONS["arabian sea"], pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01"))
    assert set(df.platform_number) == {"2902745"} and len(df) == 2          # outside box + descending dropped, fill level dropped
    assert df.time.iloc[0] == pd.Timestamp("2024-01-03 06:00")
    assert list(df.pres) == [10, 500] and list(df.temp) == [28, 12.5] and list(df.temp_qc) == [1, 1]
    assert df.cycle_number.iloc[0] == 12


# ===== NEW (v5): download errors, manual raw folder, files without adjusted data =====
def test_download_reports_every_server_error(tmp_path, monkeypatch):
    import urllib.error, fetch_gdac
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 500, "x", {}, None)
    monkeypatch.setattr(fetch_gdac.urllib.request, "urlopen", boom)
    monkeypatch.setattr(fetch_gdac.time, "sleep", lambda s: None)
    _, status = fetch_gdac.download(pd.Timestamp("2024-01-01"), str(tmp_path))
    assert status.startswith("FAILED") and "ifremer" in status and "usgodae" in status  # old code showed only the last server


def test_raw_folder_mode_builds_csv_without_network(tmp_path, monkeypatch):
    import sys, fetch_gdac
    raw = tmp_path / "raw"; raw.mkdir()
    make(raw / "20240103_prof.nc")
    out = tmp_path / "o.csv.gz"
    monkeypatch.setattr(sys, "argv", ["x", "--raw", str(raw), "--start", "2024-01-01", "--end", "2024-01-07", "--out", str(out)])
    monkeypatch.setattr(fetch_gdac.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in raw mode")))
    fetch_gdac.main()
    assert len(pd.read_csv(out)) == 2


def test_file_without_adjusted_variables_is_skipped(tmp_path):
    p = tmp_path / "20240103_prof.nc"
    make(p)
    ds = nc.Dataset(p, "a"); ds.renameVariable("PRES_ADJUSTED", "PRES_X"); ds.close()
    assert read_prof(str(p), REGIONS["arabian sea"], pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")) is None
