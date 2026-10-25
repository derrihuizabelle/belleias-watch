"""Forecast humpback season dates (start, peak, end) for one coastal region.

Targets, per season year:
  start / peak / end = 10th / 50th / 90th percentile of the day of year of
  the distinct days with at least one sighting. Counting days instead of
  records is the effort correction: one boat trip that photographs 40 whales
  is one vote, not 40.

Candidate models are small linear regressions (about 17 seasons only), each
scored with leave-one-season-out cross-validation. A model replaces the
climatology baseline (the mean of the other seasons) only if it cuts the
cross-validated error by at least MIN_GAIN, and never when a predictor's
value for the forecast season lies outside the range seen in training
(that would be extrapolation, not evidence). Writes data/predictions/season_dates.json.

Run from models/:  python -m belleias.season_dates
"""

import datetime as dt
import json
from collections import defaultdict

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from . import covariates
from .occurrences import DATA_DIR, load

REGION = "BA-ES (Abrolhos)"
FIRST_SEASON = 2009     # earlier seasons have too few records
MIN_DAYS = 20           # sighting days needed for a usable season
SEASON_DOY = (121, 365) # May-Dec; drops off-season stragglers (Jan-Apr)
INTERVAL = 0.8          # width of the prediction interval
MIN_GAIN = 0.10         # error reduction a model needs over climatology
HAPPYWHALE = "e1dddb82-f1c0-4553-aa2e-1fd414658d01"

TARGETS = {"start": 0.1, "peak": 0.5, "end": 0.9}

# name -> (formula right-hand side, predictors needed, when they are known)
MODELS = {
    "climatology": ("1", [], "always"),
    "trend": ("year", ["year"], "always"),
    "enso_lag": ("oni_lag", ["oni_lag"], "October of the previous year"),
    "sst_june": ("sst_jun", ["sst_jun"], "early July of the season year"),
    "trend_effort": ("year + n_days", ["year", "n_days"], "always (typical effort)"),
    # The data source shifted from research cruises (ICMBio, until ~2017) to
    # tourist boats (Happywhale, from 2019), and tours stop earlier in the
    # season. hw_share separates that shift from a real change in the whales.
    "source_mix": ("hw_share", ["hw_share"], "always (recent source mix)"),
    "trend_source": ("year + hw_share", ["year", "hw_share"], "always (recent source mix)"),
}


def season_table(records, last_complete):
    days, hw_days = defaultdict(set), defaultdict(set)
    for r in records:
        doy = r.date.timetuple().tm_yday
        if r.region == REGION and SEASON_DOY[0] <= doy <= SEASON_DOY[1]:
            days[r.date.year].add(doy)
            if r.dataset == HAPPYWHALE:
                hw_days[r.date.year].add(doy)
    rows = []
    for year in range(FIRST_SEASON, last_complete + 1):
        doys = sorted(days.get(year, ()))
        if len(doys) < MIN_DAYS:
            continue
        row = {"year": year, "n_days": len(doys), "hw_share": len(hw_days[year]) / len(doys)}
        row.update({t: float(np.quantile(doys, q)) for t, q in TARGETS.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def add_covariates(df):
    oni = covariates.oni()
    # ENSO in Jul-Sep of the previous year: known before the season starts,
    # and it acts on Antarctic feeding conditions the summer before migration.
    jas = oni[oni.season == "JAS"].set_index("year").anom
    sst = covariates.abrolhos_sst()
    june = sst[sst.month == 6].set_index("year").sst
    df = df.copy()
    df["oni_lag"] = df.year.map(lambda y: jas.get(y - 1))
    df["sst_jun"] = df.year.map(june.get)
    return df, jas, june


def loo_mae(df, target, rhs):
    errors = []
    for year in df.year:
        train, test = df[df.year != year], df[df.year == year]
        fit = smf.ols(f"{target} ~ {rhs}", data=train).fit()
        errors.append(abs(fit.predict(test).iloc[0] - test[target].iloc[0]))
    return float(np.mean(errors))


def to_date(year, doy):
    return dt.date(year, 1, 1) + dt.timedelta(days=int(round(doy)) - 1)


def rejection(name, score, baseline, df, next_features):
    """Why a model cannot be used for the forecast, or None if it can."""
    if name == "climatology":
        return None
    for p in MODELS[name][1]:
        value = next_features.get(p)
        if value is None:
            return f"{p} not known yet"
        if p != "year" and not df[p].min() <= value <= df[p].max():
            return f"{p}={value:.2f} outside training range"
    if score > baseline * (1 - MIN_GAIN):
        return "gain over climatology below 10%"
    return None


def forecast(df, target_year, next_features):
    results = {}
    for target in TARGETS:
        scores = {name: loo_mae(df, target, rhs) for name, (rhs, _, _) in MODELS.items()}
        rejected = {n: rejection(n, s, scores["climatology"], df, next_features)
                    for n, s in scores.items()}
        best = min((n for n in scores if rejected[n] is None), key=scores.get)
        rhs, predictors, known = MODELS[best]
        fit = smf.ols(f"{target} ~ {rhs}", data=df).fit()
        frame = fit.get_prediction(pd.DataFrame([next_features])).summary_frame(alpha=1 - INTERVAL)
        mean, low, high = frame["mean"].iloc[0], frame["obs_ci_lower"].iloc[0], frame["obs_ci_upper"].iloc[0]
        results[target] = {
            "model": best,
            "predictors_known": known,
            "date": to_date(target_year, mean).isoformat(),
            "interval": [to_date(target_year, low).isoformat(), to_date(target_year, high).isoformat()],
            "cv_mae_days": round(scores[best], 1),
            "cv_mae_by_model": {n: round(s, 1) for n, s in scores.items()},
            "rejected": {n: why for n, why in rejected.items() if why},
        }
    return results


def main():
    records, _ = load("humpback")
    last_complete = max(r.date.year for r in records) - 1  # current season still being published
    target_year = last_complete + 2 if dt.date.today().month >= 10 else last_complete + 1
    df, jas, june = add_covariates(season_table(records, last_complete))
    df = df.dropna()

    next_features = {
        "year": target_year,
        "oni_lag": jas.get(target_year - 1),
        "sst_jun": june.get(target_year),
        "n_days": float(df.n_days.tail(3).mean()),
        "hw_share": float(df.hw_share.tail(3).mean()),
    }
    results = forecast(df, target_year, next_features)

    out = {
        "region": REGION,
        "season": target_year,
        "generated": dt.date.today().isoformat(),
        "interval_level": INTERVAL,
        "features": {k: (None if v is None else round(float(v), 2)) for k, v in next_features.items()},
        "forecast": results,
        "history": df.round(2).to_dict(orient="records"),
    }
    path = DATA_DIR / "predictions" / "season_dates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print(f"{REGION}: {len(df)} seasons ({df.year.min()}-{df.year.max()}), forecast for {target_year}")
    print(f"features: {out['features']}\n")
    for target, r in results.items():
        scores = "  ".join(f"{n}={s}" for n, s in r["cv_mae_by_model"].items())
        print(f"{target:5s} {r['date']}  [{r['interval'][0]} .. {r['interval'][1]}]  via {r['model']}")
        print(f"      CV error (days): {scores}")
        for n, why in r["rejected"].items():
            print(f"      - {n}: {why}")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
