# belleias-watch

Predicting humpback whale seasons on the Brazilian coast: when the season starts, how long it lasts, and how many whales pass by.

> Work in progress. This first stage explores the open data to see what can honestly be predicted.

## Planned stack

| Part | Tech |
|---|---|
| Ingestion and API | Kotlin, Spring Boot, PostgreSQL |
| Models | Python (seasonal phenology, mark-recapture) |
| Web | Next.js (TypeScript) |

## Data exploration so far

Sources: the [GBIF](https://www.gbif.org) occurrence API (records in Brazil since 1990), the [NOAA CPC ONI](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt) and [NOAA OISST v2](https://psl.noaa.gov/data/gridded/data.noaa.oisst.v2.highres.html) monthly sea surface temperature.

```bash
python3 models/explore/fetch_gbif.py      # downloads to data/raw/ (resumable, standard library only)
python3 models/explore/season_summary.py  # per-region, per-year season start, peak, end
```

Findings that shaped the plan:

- **Species.** Humpback whales have about 8,500 records and 18 usable seasons around Abrolhos (BA-ES). Southern right whales have only about 380, which is too few, so humpbacks come first.
- **Regions by latitude.** Happywhale, the largest source, has no state field, so each record's region comes from its latitude.
- **Bulk dates dropped.** Some datasets file hundreds of records under a single report date. These would fake a one-day season, so they are excluded from the date statistics.
- **Individuals, not just sightings.** Happywhale photo-identifies whales. Whales resighted across seasons allow a mark-recapture estimate of the population.
- **Observation effort.** The number of sightings grows with tourism and citizen science, not only with the number of whales. The models need to correct for this.

## Season dates model

`models/belleias/season_dates.py` forecasts the start, peak and end of the humpback season around Abrolhos. Each one is the 10th, 50th or 90th percentile of that season's sighting days.

```bash
python3 -m venv .venv && .venv/bin/pip install -r models/requirements.txt -r models/requirements-dev.txt
cd models
../.venv/bin/python -m belleias.season_dates   # writes data/predictions/season_dates.json
../.venv/bin/python -m pytest
```

**Design.** There are only 17 seasons (2009-2025), so the candidates are small linear regressions: a historical mean (climatology), a year trend, lagged ENSO (ONI), June sea surface temperature at Abrolhos (NOAA OISST), observation effort and the share of data from tourist boats. Each candidate is scored with leave-one-season-out cross-validation.

**Guards against fooling ourselves.**
- **One day, one vote.** Distinct sighting days are counted, not records, so one trip that photographs 40 whales does not move the dates.
- **Minimum gain.** A model replaces climatology only if it cuts the cross-validated error by at least 10%.
- **No extrapolation.** A covariate outside its training range blocks that model. The July-September 2026 ONI is +2.16, above the +1.73 maximum seen in training, so the ENSO model sits out the 2027 forecast.
- **Source shift.** The data moved from research cruises (ICMBio, until ~2017) to tourist boats (Happywhale, from 2019). Tours stop earlier, which made the season *look* shorter. With the Happywhale share as a covariate, that apparent trend in the end date disappears. The earlier peak shows up within both sources, so it is kept.

**Forecast for 2027** (80% intervals, generated 2026-10-24):

| | Date | Interval | Model | CV error | Climatology error |
|---|---|---|---|---|---|
| Start | 13 Jul | 29 Jun - 28 Jul | climatology | 7.7 days | 7.7 days |
| Peak | 14 Aug | 1 Aug - 26 Aug | trend | 7.1 days | 8.7 days |
| End | 4 Oct | 20 Sep - 19 Oct | source mix | 8.6 days | 12.3 days |

**Limitations.** Presence-only data has no record of days when people looked and saw nothing, and tours run only in season, so the start date partly reflects when tours begin. Seventeen seasons cannot support more than one or two predictors per model.

## Data credits

The occurrence data is published under CC BY 4.0 by Happywhale, ICMBio (SISBio), iNaturalist, PGS, TotalEnergies EP Brasil and others, through GBIF. Raw data is not stored in this repository.

## License

Code is released under the [MIT License](LICENSE). The data belongs to its publishers (see Data credits).
