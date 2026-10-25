import csv
import datetime as dt

import pytest

from belleias import occurrences
from belleias.occurrences import load, region_of_latitude


@pytest.mark.parametrize("lat, region", [
    (-8.0, "Nordeste"),
    (-17.96, "BA-ES (Abrolhos)"),  # Abrolhos archipelago
    (-21.3, "BA-ES (Abrolhos)"),   # band limits are inclusive on the south side
    (-23.5, "RJ-SP"),
    (-28.0, "SC-RS"),
    (-40.0, None),
])
def test_region_of_latitude(lat, region):
    assert region_of_latitude(lat) == region


def write_csv(path, rows):
    fields = ["year", "month", "day", "decimalLatitude", "datasetKey", "organismID"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def row(day, dataset="a", lat="-18.0", organism=""):
    return {"year": "2024", "month": "8", "day": str(day), "decimalLatitude": lat,
            "datasetKey": dataset, "organismID": organism}


def test_load_drops_bulk_dates_and_unparseable_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(occurrences, "RAW_DIR", tmp_path)
    bulk = [row(1, dataset="icmbio")] * (occurrences.BULK_DATE + 1)
    same_day_other_source = [row(1, dataset="happywhale")]
    normal = [row(2), row(3, organism="whale-1")]
    broken = [row(""), row(4, lat="")]
    write_csv(tmp_path / "gbif_test.csv", bulk + same_day_other_source + normal + broken)

    records, dropped = load("test")

    assert dropped == occurrences.BULK_DATE + 1
    assert [(r.date, r.dataset) for r in records] == [
        (dt.date(2024, 8, 1), "happywhale"),
        (dt.date(2024, 8, 2), "a"),
        (dt.date(2024, 8, 3), "a"),
    ]
    assert records[-1].organism == "whale-1"
