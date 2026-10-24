"""Download whale occurrences in Brazil from the GBIF API into data/raw/*.csv.

Exploration only: answers "how much data is there?" before any modelling.
Standard library only, so it runs on any Python 3.9+ without installs.
The GBIF API drops connections often, so records are fetched one year at a
time and each year is cached in data/raw/cache/; a rerun resumes where it stopped.
"""

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search"
PAGE_SIZE = 300  # GBIF maximum per request
FIRST_YEAR = 1990
MAX_ATTEMPTS = 8

SPECIES = {
    "humpback": 5220086,      # Megaptera novaeangliae (jubarte)
    "southern_right": 2440332,  # Eubalaena australis (franca)
}

FIELDS = [
    "gbifID", "eventDate", "year", "month", "day", "stateProvince", "locality",
    "decimalLatitude", "decimalLongitude", "individualCount", "basisOfRecord",
    "datasetKey", "datasetName", "recordedBy", "occurrenceStatus", "organismID",
]

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
CACHE_DIR = RAW_DIR / "cache"


def fetch_page(taxon_key, year, offset):
    params = {
        "taxonKey": taxon_key,
        "year": year,
        "country": "BR",
        "occurrenceStatus": "PRESENT",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    url = GBIF_SEARCH + "?" + urllib.parse.urlencode(params)
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except OSError as err:
            wait = min(2 ** attempt, 60)
            print(f"  retry in {wait}s after {err}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"GBIF request failed: {url}")


def fetch_year(taxon_key, year):
    rows, offset = [], 0
    while True:
        page = fetch_page(taxon_key, year, offset)
        rows.extend({f: r.get(f, "") for f in FIELDS} for r in page["results"])
        if page["endOfRecords"]:
            return rows
        offset += PAGE_SIZE


def fetch_species(name, taxon_key, last_year):
    rows = []
    for year in range(FIRST_YEAR, last_year + 1):
        cached = CACHE_DIR / f"{name}_{year}.json"
        if not cached.exists():
            cached.write_text(json.dumps(fetch_year(taxon_key, year)))
        year_rows = json.loads(cached.read_text())
        print(f"  {name} {year}: {len(year_rows)}", file=sys.stderr)
        rows.extend(year_rows)
    return rows


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # The current year is still in progress, so it is always refetched.
    this_year = time.localtime().tm_year
    for cached in CACHE_DIR.glob(f"*_{this_year}.json"):
        cached.unlink()
    for name, key in SPECIES.items():
        rows = fetch_species(name, key, this_year)
        out = RAW_DIR / f"gbif_{name}.csv"
        with out.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
