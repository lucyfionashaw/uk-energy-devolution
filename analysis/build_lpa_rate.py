#!/usr/bin/env python3
"""How often does a single planning authority actually see a major renewable application?

Raw REPD -> data/processed/lpa_rate.json

Method notes:
 * National consenting bodies (S36 / NSIP / Marine / Crown) are excluded — they are
   not local planning authorities.
 * Counts are built on a FULL LPA x year grid including zeros. Counting only
   LPA-years that had an application would bias the median upwards badly.
 * "Major" is capacity-thresholded; several thresholds are reported because the
   answer is sensitive to where you draw the line.
 * Robustness: repeat applications on the same site (same LPA + Site Name) are
   checked; the median is unchanged when deduped.

Run:  py analysis/compute_lpa_rate.py
"""
import json, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "REPD_publication_Q1_2026.csv"
OUT = ROOT / "data" / "processed" / "lpa_rate.json"

NATIONAL = [
    "Crown Estate", "DECC (S36)", "Marine Management Organisation", "Marine Scotland",
    "Scottish Government (S36)", "The Planning Inspectorate - National Infrastructure",
    "Welsh Government (NSIP)",
]
LO, HI = 2020, 2025          # window
YEARS = HI - LO + 1
TECHS = ["Solar Photovoltaics", "Battery"]
HEADLINE_MW = 10             # the threshold the headline figures use

df = pd.read_csv(RAW, encoding="latin-1", low_memory=False)
for c in ["Planning Authority", "Technology Type", "Site Name"]:
    df[c] = df[c].astype(str).str.strip()
df = df[(~df["Planning Authority"].isin(NATIONAL))
        & (df["Planning Authority"].str.lower() != "nan")].copy()
df["cap"] = pd.to_numeric(df["Installed Capacity (MWelec)"], errors="coerce")
df["yr"] = pd.to_datetime(df["Planning Application Submitted"],
                          format="%d/%m/%Y", errors="coerce").dt.year

LPAS = sorted({str(x) for x in df["Planning Authority"]})
sb = df[df["Technology Type"].isin(TECHS)]


def counts(sub):
    """Applications per LPA, reindexed over every LPA so zeros are included."""
    return sub.groupby("Planning Authority").size().reindex(LPAS, fill_value=0)


win = sb[(sb.yr >= LO) & (sb.yr <= HI) & (sb.cap >= HEADLINE_MW)]
cnt = counts(win)
ded = counts(win.drop_duplicates(subset=["Planning Authority", "Site Name"]))

# distribution bands
BANDS = [(0, 0, "0"), (1, 1, "1"), (2, 2, "2"), (3, 5, "3–5"),
         (6, 10, "6–10"), (11, 20, "11–20"), (21, 10**6, "21+")]
dist = [{"band": lab, "lpas": int(((cnt >= lo) & (cnt <= hi)).sum())} for lo, hi, lab in BANDS]

# sensitivity to where "major" is drawn
thresh = []
for t in [1, 5, 10, 20, 50]:
    c = counts(sb[(sb.yr >= LO) & (sb.yr <= HI) & (sb.cap >= t)])
    med = float(c.median())
    thresh.append({
        "mw": t, "median": med, "mean": round(float(c.mean()), 2),
        "pctZero": round(float((c == 0).mean() * 100), 1),
        "yrsPerAppMedian": round(YEARS / med, 1) if med > 0 else None,
    })

# per-year rates
yearly = []
for y in range(2015, HI + 1):
    c = counts(sb[(sb.yr == y) & (sb.cap >= HEADLINE_MW)])
    yearly.append({"year": y, "median": float(c.median()), "mean": round(float(c.mean()), 2),
                   "pctZero": round(float((c == 0).mean() * 100), 1),
                   "total": int(((sb.yr == y) & (sb.cap >= HEADLINE_MW)).sum())})

payload = {
    "window": f"{LO}-{HI}", "years": YEARS, "headlineMW": HEADLINE_MW, "techs": TECHS,
    "nLPAs": len(LPAS),
    "median": float(cnt.median()), "mean": round(float(cnt.mean()), 2),
    "p90": float(cnt.quantile(.90)), "max": int(cnt.max()),
    "pctZero": round(float((cnt == 0).mean() * 100), 1),
    "yrsPerAppMedian": round(YEARS / float(cnt.median()), 1) if cnt.median() > 0 else None,
    "medianDeduped": float(ded.median()),
    "records": int(len(win)), "recordsDeduped": int(ded.sum()),
    "dist": dist, "thresh": thresh, "yearly": yearly,
    "top": [{"lpa": str(a), "n": int(v)} for a, v in cnt.sort_values(ascending=False).head(10).items()],
}
OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"median={payload['median']:.0f} (deduped {payload['medianDeduped']:.0f}) "
      f"-> one every {payload['yrsPerAppMedian']} yrs; {payload['pctZero']}% of LPAs saw none")
print(f"wrote {OUT}")
