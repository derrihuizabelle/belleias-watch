"""Summarise each year's whale season from the raw GBIF CSVs.

For every species/region/year with enough dated records it prints:
  n      records with a trustworthy date
  days   distinct observation days (a crude proxy for observation effort)
  src    distinct datasets
  ids    distinct photo-identified individuals (Happywhale organismID)
  p10 / p50 / p90  day-of-year quantiles -> season start, peak, end
The p10-p90 window is the season length used later by the models.
Cleaning rules (regions by latitude, bulk dates) live in belleias/occurrences.py.
"""

import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from belleias.occurrences import REGIONS, load  # noqa: E402

MIN_RECORDS = 30  # below this the quantiles are noise


def quantile(sorted_values, q):
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def as_date(doy):
    # Non-leap reference year, only for printing "dd/mm".
    return (dt.date(2001, 1, 1) + dt.timedelta(days=doy - 1)).strftime("%d/%m")


def main():
    for species in ("humpback", "southern_right"):
        records, dropped = load(species)
        by_key = defaultdict(list)
        for r in records:
            by_key[(r.region, r.date.year)].append(r)
        print(f"\n## {species}  (dropped {dropped} records with bulk dates)")
        for _, region in REGIONS:
            years = sorted(y for (reg, y) in by_key if reg == region)
            usable = [y for y in years if len(by_key[(region, y)]) >= MIN_RECORDS]
            total = sum(len(by_key[(region, y)]) for y in years)
            print(f"\n{region}: {total} dated records, {len(usable)} usable years (>= {MIN_RECORDS})")
            if not usable:
                continue
            print("  year     n  days  src   ids    p10    p50    p90  length")
            for year in usable:
                recs = by_key[(region, year)]
                doys = sorted(r.date.timetuple().tm_yday for r in recs)
                p10, p50, p90 = (quantile(doys, q) for q in (0.1, 0.5, 0.9))
                print(f"  {year} {len(recs):5d} {len({r.date for r in recs}):5d} "
                      f"{len({r.dataset for r in recs}):4d} {len({r.organism for r in recs if r.organism}):5d}  "
                      f"{as_date(p10)}  {as_date(p50)}  {as_date(p90)}  {p90 - p10:4d}d")


if __name__ == "__main__":
    main()
