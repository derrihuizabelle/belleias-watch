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

Source: [GBIF](https://www.gbif.org) occurrence API, records in Brazil since 1990.

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

## Data credits

The occurrence data is published under CC BY 4.0 by Happywhale, ICMBio (SISBio), iNaturalist, PGS, TotalEnergies EP Brasil and others, through GBIF. Raw data is not stored in this repository.
