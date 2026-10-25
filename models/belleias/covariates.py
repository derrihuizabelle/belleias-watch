"""Environmental covariates, downloaded once and cached in data/raw/cache/.

  ONI   Oceanic Nino Index (NOAA CPC), 3-month running ENSO anomaly.
  SST   Monthly sea surface temperature over the Abrolhos Bank from
        NOAA OISST v2 high resolution (0.25 deg), via the PSL OPeNDAP server.
"""

import datetime as dt
import urllib.request

import pandas as pd

from .occurrences import RAW_DIR

CACHE_DIR = RAW_DIR / "cache"

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
SST_URL = "https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc.ascii"

# Grid indices for the Abrolhos Bank box (about 19S-17S, 38.75W-37.75W).
# lat = -89.875 + 0.25 * i, lon = 0.125 + 0.25 * j (degrees east).
ABROLHOS_LAT = (284, 291)
ABROLHOS_LON = (1285, 1288)
SST_MISSING = -9.0e36


def _cached_text(name, url):
    path = CACHE_DIR / name
    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as resp:
            path.write_bytes(resp.read())
    return path.read_text()


def oni():
    """DataFrame with columns season ('DJF', ..., 'NDJ'), year, anom."""
    lines = _cached_text("oni.txt", ONI_URL).splitlines()[1:]
    rows = [line.split() for line in lines if line.strip()]
    return pd.DataFrame(
        [(s, int(y), float(a)) for s, y, _, a in rows], columns=["season", "year", "anom"]
    )


def _parse_opendap_grid(text):
    """Parse the ASCII body of an OPeNDAP sst[time][lat][lon] response."""
    body = text.split("sst.sst", 1)[1]
    values = {}
    for line in body.splitlines()[1:]:
        if not line.startswith("["):
            break
        index, cells = line.split(",", 1)
        t = int(index.strip("[]").split("][")[0])
        cells = [float(c) for c in cells.split(",")]
        values.setdefault(t, []).extend(c for c in cells if c > SST_MISSING)
    times = [float(t) for t in text.split("sst.time[", 1)[1].splitlines()[1].split(",")]
    return times, values


def abrolhos_sst():
    """DataFrame with columns year, month, sst (box mean, deg C)."""
    query = "?sst%5B0:1:{last}%5D%5B{}:{}%5D%5B{}:{}%5D".format(
        *ABROLHOS_LAT, *ABROLHOS_LON, last="{last}"
    )
    dds = _cached_text("oisst_dds.txt", SST_URL.replace(".ascii", ".dds"))
    n_months = int(dds.split("time = ", 1)[1].split("]", 1)[0])
    text = _cached_text("oisst_abrolhos.txt", SST_URL + query.format(last=n_months - 1))
    times, values = _parse_opendap_grid(text)
    epoch = dt.date(1800, 1, 1)
    rows = []
    for t, days in enumerate(times):
        date = epoch + dt.timedelta(days=days)
        cells = values.get(t, [])
        if cells:
            rows.append((date.year, date.month, sum(cells) / len(cells)))
    return pd.DataFrame(rows, columns=["year", "month", "sst"])
