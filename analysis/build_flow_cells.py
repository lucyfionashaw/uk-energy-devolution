#!/usr/bin/env python3
"""Break the planning-funnel / Sankey quantities down by TECHNOLOGY x PARTY so the
overview diagram can be filtered interactively.

For every project we record the 9 funnel base-metrics (in both project count and MW)
into a cell keyed by (technology bucket, controlling-party bucket):

  * technology  — Solar / OnshoreWind / OffshoreWind / Battery / Other
  * party       — the party controlling the deciding council, matched the same way as
                  phase 4 (Open Council Data UK, control at the DECISION date, May
                  take-office cut-off). For a project that has NOT been decided we fall
                  back to control at the application date; national-route / unmatched
                  projects (offshore wind, NSIP, NI, no council match) go to "None".

The front-end sums the relevant cells: "All technologies / All parties" is just the sum
of every cell, which reproduces flow_data.json exactly. Every stored metric is linear,
so the derived flows (decided, otherOut, permitted, building) can be computed AFTER the
sum and still balance.

Output: data/processed/flow_cells.json  ->  window.FLOWX in data.js
Run:    python3 analysis/build_flow_cells.py   (then re-run build_data_js.py)
"""
import csv, re, json, pathlib, datetime
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "flow_cells.json"

# --------------------------------------------------------------------------- #
# Council-control series + date-aware lookup (mirrors build_phase4_party.py).
# --------------------------------------------------------------------------- #
STOP = {"council", "county", "city", "borough", "district", "metropolitan",
        "unitary", "authority", "royal", "of", "the", "cyngor", "sir"}

def norm(s):
    s = (s or "").lower().strip().replace("&", "and").replace(".", "")
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(t for t in s.split() if t and t not in STOP)

PARTY_COL = {"con": "Con", "lab": "Lab", "ld": "LibDem", "green": "Green", "snp": "SNP",
             "pc": "Plaid", "ref": "Reform", "ukip": "Reform", "other": "Other/Ind"}

def largest(row, cols):
    best, bv = None, -1
    for c in cols:
        try: v = int(row[c] or 0)
        except ValueError: v = 0
        if v > bv: best, bv = c, v
    return best, bv

ctrl = defaultdict(dict)
for r in csv.DictReader(open(RAW / "history1973-2015.csv", encoding="cp1252")):
    best, bv = largest(r, ["con", "lab", "ld", "other", "nat"])
    if bv <= 0: continue
    party = "Nationalist (pre-2007)" if best == "nat" else PARTY_COL.get(best, "Other/Ind")
    ctrl[norm(r["authority"])][int(r["year"])] = party
for r in csv.DictReader(open(RAW / "history2016-26.csv", encoding="cp1252")):
    best, bv = largest(r, ["con", "lab", "ld", "green", "ukip", "ref", "pc", "snp", "other"])
    if bv <= 0: continue
    ctrl[norm(r["authority"])][int(r["year"])] = PARTY_COL.get(best, "Other/Ind")

def take_office(year):
    may1 = datetime.date(year, 5, 1)
    first_thu = may1 + datetime.timedelta(days=(3 - may1.weekday()) % 7)
    return first_thu + datetime.timedelta(days=4)

def control_in_year(council_norm, year):
    yrs = ctrl.get(council_norm)
    if not yrs: return None
    cand = [y for y in yrs if y <= year]
    return yrs[max(cand)] if cand else yrs[min(yrs)]

def control_at(council_norm, d):
    """Party controlling `council_norm` on date `d`, with the May take-office cut-off."""
    if d is None:
        yrs = ctrl.get(council_norm)
        return yrs[max(yrs)] if yrs else None
    eff_year = d.year if d >= take_office(d.year) else d.year - 1
    return control_in_year(council_norm, eff_year)

def parse_date(d):
    d = (d or "").strip()
    try:
        dd, mm, yy = d.split("/")
        return datetime.date(int(yy), int(mm), int(dd))
    except (ValueError, IndexError):
        return None

# --------------------------------------------------------------------------- #
# Project classification (mirrors build_map_flow.py so totals match flow_data).
# --------------------------------------------------------------------------- #
has = lambda x: bool((x or "").strip())
def num(x):
    x = (x or "").strip().replace(",", "")
    try: return float(x)
    except ValueError: return None

GCOL, UCOL, OCOL = "Planning Permission  Granted", "Under Construction", "Operational"
GRANT_ST = {"Awaiting Construction", "Under Construction", "Operational",
            "Planning Permission Expired", "Decommissioned"}
BUILT_ST = {"Under Construction", "Operational", "Decommissioned"}
OP_ST = {"Operational", "Decommissioned"}
REF = {"Application Refused", "Appeal Refused", "Secretary of State Refusal"}
PEND = {"Application Submitted", "Appeal Lodged"}
GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
REFUSE_DATES = ["Planning Permission Refused", "Appeal Refused", "Secretary of State - Refusal"]

def tech_bucket(t):
    t = (t or "").strip()
    return {"Solar Photovoltaics": "Solar", "Wind Onshore": "OnshoreWind",
            "Wind Offshore": "OffshoreWind", "Battery": "Battery"}.get(t, "Other")

METRICS = ["applied", "granted", "refused", "pending", "expired", "built", "op"]
# cells[(tech, party)] = {"n": {...}, "mw": {...}}
cells = defaultdict(lambda: {"n": {m: 0 for m in METRICS}, "mw": {m: 0.0 for m in METRICS}})

for r in csv.DictReader(open(RAW / "REPD_publication_Q1_2026.csv", encoding="cp1252")):
    st = r["Development Status (short)"].strip()
    granted = has(r[GCOL]) or st in GRANT_ST
    built = has(r[UCOL]) or st in BUILT_ST
    oper = has(r[OCOL]) or st in OP_ST
    refused = st in REF
    pending = st in PEND
    expired = st == "Planning Permission Expired"
    cap = num(r["Installed Capacity (MWelec)"]) or 0.0

    # --- controlling party: decision date if decided, else application date ---
    if granted:
        d = next((parse_date(r[c]) for c in GRANT_DATES if has(r[c])), None)
    elif refused:
        d = next((parse_date(r[c]) for c in REFUSE_DATES if has(r[c])), None)
    else:
        d = None
    if d is None:  # undecided, or decided with no recorded date -> fall back to submission
        d = parse_date(r["Planning Application Submitted"])
    party = control_at(norm(r["Planning Authority"]), d) or "None"

    cell = cells[(tech_bucket(r["Technology Type"]), party)]
    def add(metric):
        cell["n"][metric] += 1
        cell["mw"][metric] += cap
    add("applied")
    if granted: add("granted")
    if refused: add("refused")
    if pending: add("pending")
    if expired: add("expired")
    if built: add("built")
    if oper: add("op")

out = {"metrics": METRICS,
       "cells": [{"tech": t, "party": p,
                  "n": v["n"], "mw": {m: round(v["mw"][m]) for m in METRICS}}
                 for (t, p), v in sorted(cells.items())]}
OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

# ---- sanity: All/All totals should match flow_data.json ----
tot = {u: {m: 0 for m in METRICS} for u in ("n", "mw")}
for c in out["cells"]:
    for u in ("n", "mw"):
        for m in METRICS:
            tot[u][m] += c[u][m]
print(f"flow_cells.json: {len(out['cells'])} cells")
print("  All/All projects:", tot["n"])
print("  All/All MW      :", tot["mw"])
parties = sorted({c["party"] for c in out["cells"]})
print("  parties present :", parties)
