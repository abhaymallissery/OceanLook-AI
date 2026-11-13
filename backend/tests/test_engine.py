# FILE: tests/test_engine.py - engine tests on a fixture with analytically known answers. CHANGED (v2): fixture slope 0.01 (physically plausible).
import numpy as np, pytest
from pydantic import ValidationError
from engine import Query, run, depth_m
from synth import make_synthetic

AS = dict(region="arabian sea", start="2024-01-01", end="2024-12-31")


@pytest.fixture
def df():
    return make_synthetic()


def q(**kw):
    return Query(**{**AS, "intent": "mean_at_depth", "depths_m": [500], **kw})


def test_depth_formula_matches_unesco_check_value():
    assert depth_m(10000, 30) == pytest.approx(9712.653, abs=0.01)


def test_mean_at_depth_exact_and_counts(df):
    r = run(df, q())
    assert r.status == "ok" and r.unit == "°C"
    assert r.series[0].value == pytest.approx(28 - 0.01 * 500)  # linear in depth => interpolation is exact
    assert r.series[0].n_profiles == 50 and r.series[0].n_floats == 5  # 5 floats x 10 cycles, 2023 float excluded
    assert r.n_profiles_in_scope == 50


def test_region_and_time_filters(df):
    assert run(df, q(region="bay of bengal")).series[0].n_profiles == 6
    assert run(df, q(start="2023-01-01", end="2023-12-31")).series[0].n_profiles == 5


def test_bad_qc_levels_are_ignored_but_interpolation_survives(df):
    bad = (df.platform_number == "900000") & df.pres.between(470, 530)
    df.loc[bad, "temp"], df.loc[bad, "temp_qc"] = 99.0, 4
    r = run(df, q())
    assert r.series[0].value == pytest.approx(23.0) and r.series[0].n_profiles == 50
    r = run(df, q(max_gap_m=50))  # removing levels widens the gap past 50 m -> those 10 profiles drop out
    assert r.series[0].n_profiles == 40 and r.series[0].value == pytest.approx(23.0)


def test_nan_values_ignored(df):
    df.loc[df.pres.between(470, 530), "temp"] = np.nan
    assert run(df, q()).series[0].value == pytest.approx(23.0)


def test_no_extrapolation_beyond_deepest_level(df):
    r = run(df, q(depths_m=[2000]))
    assert r.status == "no_data" and r.series[0].n_profiles == 0


def test_compare_depths_and_stats(df):
    r = run(df, q(intent="compare_depths", depths_m=[100, 1000]))
    assert [s.value for s in r.series] == pytest.approx([27.0, 18.0]) and r.difference == pytest.approx(-9.0)
    assert run(df, q(stat="max")).series[0].value == pytest.approx(23.0)


def test_salinity_and_profile_and_count(df):
    assert run(df, q(variable="salinity")).series[0].value == pytest.approx(35.5) and run(df, q(variable="salinity")).unit == "PSU"
    p = run(df, q(intent="depth_profile", depths_m=[]))
    assert p.status == "ok" and p.series[0].depth_m == 10 and p.series[-1].value == pytest.approx(28 - 0.01 * 1800)
    c = run(df, q(intent="count_profiles", depths_m=[]))
    assert (c.n_profiles_in_scope, c.n_floats_in_scope) == (50, 5)


def test_empty_scope_is_no_data_not_error(df):
    assert run(df, q(region="equatorial indian ocean")).status == "no_data"


@pytest.mark.parametrize("kw", [
    dict(region="atlantis"), dict(region=None), dict(intent="compare_depths"), dict(depths_m=[0]),
    dict(depths_m=[5000]), dict(end="2023-01-01"), dict(region=None, bbox=(10, 5, 50, 60)),
])
def test_query_validation_rejects(kw):
    with pytest.raises(ValidationError):
        q(**kw)
