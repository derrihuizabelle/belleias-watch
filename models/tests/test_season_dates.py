import datetime as dt

import pandas as pd

from belleias import season_dates
from belleias.occurrences import Record
from belleias.season_dates import HAPPYWHALE, REGION, rejection, season_table


def records_for(year, days, dataset="icmbio", per_day=1):
    start = dt.date(year, 7, 1)
    return [Record(REGION, start + dt.timedelta(days=d), dataset, "")
            for d in days for _ in range(per_day)]


def test_season_table_counts_days_not_records(monkeypatch):
    monkeypatch.setattr(season_dates, "FIRST_SEASON", 2024)
    monkeypatch.setattr(season_dates, "MIN_DAYS", 3)
    busy_first_day = records_for(2024, [0], per_day=50)
    records = busy_first_day + records_for(2024, [10, 20], dataset=HAPPYWHALE)

    table = season_table(records, last_complete=2024)

    row = table.iloc[0]
    assert row.n_days == 3
    assert row.hw_share == 2 / 3
    # 50 records on 1 July would drag the peak to that day if records counted.
    assert row.peak == dt.date(2024, 7, 11).timetuple().tm_yday


def test_season_table_skips_off_season_and_thin_years(monkeypatch):
    monkeypatch.setattr(season_dates, "FIRST_SEASON", 2023)
    monkeypatch.setattr(season_dates, "MIN_DAYS", 3)
    january = [Record(REGION, dt.date(2024, 1, d), "icmbio", "") for d in (5, 6, 7)]
    other_region = [Record("RJ-SP", dt.date(2024, 8, d), "icmbio", "") for d in (1, 2, 3)]
    thin_2023 = records_for(2023, [0, 1])
    full_2024 = records_for(2024, [0, 1, 2])

    table = season_table(january + other_region + thin_2023 + full_2024, last_complete=2024)

    assert table.year.tolist() == [2024]
    assert table.iloc[0].start >= dt.date(2024, 7, 1).timetuple().tm_yday


HISTORY = pd.DataFrame({"year": [2020, 2021, 2022], "oni_lag": [-0.5, 0.0, 1.0]})


def test_rejection_keeps_climatology_and_good_models():
    assert rejection("climatology", 9.0, 9.0, HISTORY, {}) is None
    assert rejection("enso_lag", 5.0, 9.0, HISTORY, {"oni_lag": 0.5}) is None


def test_rejection_reasons():
    assert rejection("enso_lag", 5.0, 9.0, HISTORY, {"oni_lag": None}) == "oni_lag not known yet"
    assert "outside training range" in rejection("enso_lag", 5.0, 9.0, HISTORY, {"oni_lag": 2.16})
    assert "below 10%" in rejection("enso_lag", 8.5, 9.0, HISTORY, {"oni_lag": 0.5})


def test_rejection_allows_extrapolating_the_year():
    # A trend always forecasts a future year; only covariates are range-checked.
    assert rejection("trend", 5.0, 9.0, HISTORY, {"year": 2027}) is None
