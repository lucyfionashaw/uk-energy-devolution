#!/usr/bin/env python3
"""Median duration of each planning/build stage, by technology, for the Gantt-style
timeline on the speed page.

Stages (using the dates REPD actually records):
  1. Submission -> decision   : Planning Application Submitted -> Planning Permission Granted
  2. Decision  -> construction: Planning Permission Granted    -> Under Construction
  3. Construction -> commissioning : Under Construction         -> Operational

Each stage's median is computed over the projects that have BOTH endpoint dates, so the
later stages are based on a shrinking, survivor-selected subset (only projects that got
that far). We record the sample size `n` per stage so the page can flag that bias.

In REPD, planning permission IS the consent, so "approval" and "consent" are the same
event — there is no separate consenting date to split stage 2.

Output: data/processed/gantt_data.json  ->  window.GANTT
Run:    python3 analysis/build_gantt.py   (then re-run build_data_js.py)
"""
import csv, json, pathlib, datetime
from collections import defaultdict
from statistics import median

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "REPD_publication_Q1_2026.csv"
OUT = ROOT / "data" / "processed" / "gantt_data.json"

def parse_date(d):
    d = (d or "").strip()
    try:
        dd, mm, yy = d.split("/")
        return datetime.date(int(yy), int(mm), int(dd))
    except (ValueError, IndexError):
        return None

def months_between(a, b):
    if a is None or b is None:
        return None
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.0

def tech_bucket(t):
    t = (t or "").strip()
    return {"Solar Photovoltaics": "Solar", "Wind Onshore": "OnshoreWind",
            "Wind Offshore": "OffshoreWind", "Battery": "Battery"}.get(t, "Other")

SUB = "Planning Application Submitted"
GRANT = "Planning Permission  Granted"
CONSTR = "Under Construction"
OP = "Operational"
STAGES = [("submit", "decision", SUB, GRANT),
          ("decision", "construction", GRANT, CONSTR),
          ("construction", "commissioning", CONSTR, OP)]

# durs[bucket][stage_index] = list of month gaps
durs = defaultdict(lambda: [[], [], []])
for r in csv.DictReader(open(RAW, encoding="cp1252")):
    bucket = tech_bucket(r["Technology Type"])
    for i, (_, _, c0, c1) in enumerate(STAGES):
        m = months_between(parse_date(r[c0]), parse_date(r[c1]))
        if m is not None and 0 <= m < 360:
            durs[bucket][i].append(m)
            durs["All"][i].append(m)

STAGE_LABELS = ["Submission → decision", "Decision → construction start",
                "Construction → commissioning"]
TECH_ORDER = ["All", "Solar", "OnshoreWind", "OffshoreWind", "Battery", "Other"]

byTech = {}
for bucket in TECH_ORDER:
    lists = durs.get(bucket)
    if not lists:
        continue
    byTech[bucket] = [
        {"stage": STAGE_LABELS[i],
         "med": round(median(lists[i]), 1) if lists[i] else None,
         "n": len(lists[i])}
        for i in range(3)
    ]

out = {"stages": STAGE_LABELS, "byTech": byTech}
OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
print("gantt_data.json written. Sample (All):")
for s in byTech["All"]:
    print(f"  {s['stage']:32s} median {s['med']} mo   n={s['n']:,}")
print("techs:", list(byTech.keys()))
