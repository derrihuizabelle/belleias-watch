"""Load and clean the raw GBIF occurrence CSVs (see explore/fetch_gbif.py).

Two data problems found while exploring are handled here:
  * Happywhale (the largest source) has no stateProvince, so regions come
    from latitude instead of the state field.
  * Some datasets (notably ICMBio/SISBio) file hundreds of records under one
    date, apparently the report date rather than the sighting date. Those
    "bulk dates" are dropped, because they would fake a one-day season.
"""

import csv
import datetime as dt
from collections import Counter, namedtuple
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"
BULK_DATE = 50  # records from one dataset on one day above this = report date

# Coastal bands by latitude, north to south: (southern limit, name).
REGIONS = [
    (-15.0, "Nordeste"),
    (-21.3, "BA-ES (Abrolhos)"),
    (-25.3, "RJ-SP"),
    (-34.0, "SC-RS"),
]

Record = namedtuple("Record", "region date dataset organism")


def region_of_latitude(lat):
    previous = 90.0
    for lower_lat, name in REGIONS:
        if lower_lat <= lat < previous:
            return name
        previous = lower_lat
    return None


def _parse(row):
    try:
        date = dt.date(int(row["year"]), int(row["month"]), int(row["day"]))
        lat = float(row["decimalLatitude"])
    except ValueError:
        return None
    region = region_of_latitude(lat)
    if not region:
        return None
    return Record(region, date, row["datasetKey"], row.get("organismID", ""))


def load(species):
    """Return (records, dropped) with bulk-dated records removed."""
    with (RAW_DIR / f"gbif_{species}.csv").open() as fh:
        parsed = [r for r in map(_parse, csv.DictReader(fh)) if r]
    per_day = Counter((r.date, r.dataset) for r in parsed)
    kept = [r for r in parsed if per_day[(r.date, r.dataset)] <= BULK_DATE]
    return kept, len(parsed) - len(kept)
