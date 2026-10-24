"""Summarise each year's whale season from the raw GBIF CSVs.

For every species/region/year with enough dated records it prints:
  n      records with a trustworthy date
  days   distinct observation days (a crude proxy for observation effort)
  src    distinct datasets
  ids    distinct photo-identified individuals (Happywhale organismID)
  p10 / p50 / p90  day-of-year quantiles -> season start, peak, end
The p10-p90 window is the season length used later by the models.

Two data problems found while exploring, handled here:
  * Happywhale (the largest source) has no stateProvince, so regions come
    from latitude instead of the state field.
  * Some datasets (notably ICMBio/SISBio) file hundreds of records under one
    date, apparently the report date rather than the sighting date. Those
    "bulk dates" are dropped, because they would fake a one-day season.
"""

import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
MIN_RECORDS = 30   # below this the quantiles are noise
BULK_DATE = 50     # records from one dataset on one day above this = report date

# Coastal bands by latitude, north to south: (southern limit, name).
REGIONS = [
    (-15.0, "Nordeste"),
    (-21.3, "BA-ES (Abrolhos)"),
    (-25.3, "RJ-SP"),
    (-34.0, "SC-RS"),
]


def region_of_latitude(lat):
    previous = 90.0
    for lower_lat, name in REGIONS:
        if lower_lat <= lat < previous:
            return name
        previous = lower_lat
    return None


def quantile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def as_date(doy):
    # Non-leap reference year, only for printing "dd/mm".
    return (dt.date(2001, 1, 1) + dt.timedelta(days=doy - 1)).strftime("%d/%m")


def parse(row):
    try:
        date = dt.date(int(row["year"]), int(row["month"]), int(row["day"]))
        lat = float(row["decimalLatitude"])
    except ValueError:
        return None
    region = region_of_latitude(lat)
    return (region, date) if region else None


def load(species):
    parsed = []
    with (RAW_DIR / f"gbif_{species}.csv").open() as fh:
        for row in csv.DictReader(fh):
            hit = parse(row)
            if hit:
                parsed.append((*hit, row["datasetKey"], row.get("organismID", "")))
    per_day = Counter((date, key) for _, date, key, _ in parsed)
    by_key, dropped = defaultdict(list), 0
    for region, date, key, organism in parsed:
        if per_day[(date, key)] > BULK_DATE:
            dropped += 1
            continue
        by_key[(region, date.year)].append((date, key, organism))
    return by_key, dropped


def main():
    for species in ("humpback", "southern_right"):
        by_key, dropped = load(species)
        print(f"\n## {species}  (dropped {dropped} records with bulk dates)")
        for _, region in REGIONS:
            years = sorted(y for (r, y) in by_key if r == region)
            usable = [y for y in years if len(by_key[(region, y)]) >= MIN_RECORDS]
            total = sum(len(by_key[(region, y)]) for y in years)
            print(f"\n{region}: {total} dated records, {len(usable)} usable years (>= {MIN_RECORDS})")
            if not usable:
                continue
            print("  year     n  days  src   ids    p10    p50    p90  length")
            for year in usable:
                recs = by_key[(region, year)]
                doys = sorted(d.timetuple().tm_yday for d, _, _ in recs)
                p10, p50, p90 = (quantile(doys, q) for q in (0.1, 0.5, 0.9))
                print(f"  {year} {len(recs):5d} {len({d for d, _, _ in recs}):5d} "
                      f"{len({k for _, k, _ in recs}):4d} {len({o for _, _, o in recs if o}):5d}  "
                      f"{as_date(p10)}  {as_date(p50)}  {as_date(p90)}  {p90 - p10:4d}d")


if __name__ == "__main__":
    main()
