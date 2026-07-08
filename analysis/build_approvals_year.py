#!/usr/bin/env python3
"""Renewable capacity approved each year, split by the party controlling the DECIDING
council at the grant date.

This is the cut that separates two things people routinely conflate: the national
government of the day, and the councils that actually grant local applications. It shows
the post-2021 approvals boom is cross-party (Conservative councils approve the most in
absolute terms), so a rise in approvals under a Labour national government is mostly the
solar/battery pipeline maturing, not Labour councils — still less Westminster — waving
projects through.

Output: data/processed/approvals_year.json  ->  window.APPR_YEAR
Run:    python3 analysis/build_approvals_year.py   (then re-run build_data_js.py)
"""
import csv, json, pathlib, datetime, re
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "approvals_year.json"

def has(x): return bool((x or "").strip())
def num(x):
    x = (x or "").strip().replace(",", "")
    try: return float(x)
    except ValueError: return None
def pdate(s):
    s = (s or "").strip()
    try:
        d, m, y = s.split("/"); return datetime.date(int(y), int(m), int(d))
    except (ValueError, IndexError): return None

# Council control via the shared module (reads the `majority` column, not seat counts).
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from council_control import norm, control_at
import repd_records as R
import geo_resolve as G

GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
# Grants with no GB council party are national-route consents — attributed to the
# GOVERNMENT that decided them: Scottish Ministers (S36 / Marine Scotland; SNP-run
# throughout the window), the UK government (Planning Inspectorate NSIP / DECC / SoS;
# Con to 5 Jul 2024, Lab after), or the residual (Welsh Government, NI, unmatched).
ORDER = ["Con", "Lab", "LibDem", "SNP", "Plaid", "Green", "Reform", "Other/Ind",
         "NatUKCon", "NatUKLab", "NatSNP", "NatOther"]
Y0, Y1 = 2010, 2025
CON_IN = datetime.date(2010, 5, 11)       # Brown -> Cameron (2010 election)
LAB_IN = datetime.date(2024, 7, 5)        # Sunak -> Starmer (4 Jul 2024 election)

def national_bucket(x, gd):
    pa = norm(x["Planning Authority"])
    if "scottish government" in pa or "marine scotland" in pa or "energy consents" in pa:
        return "NatSNP"                    # Scottish Ministers: SNP-run since May 2007
    if ("planning inspectorate" in pa or "decc" in pa or "secretary of state" in pa
            or "crown estate" in pa or "marine management" in pa or "national infrastructure" in pa):
        if gd < CON_IN or gd >= LAB_IN:
            return "NatUKLab"
        return "NatUKCon"
    return "NatOther"     # Welsh Government DNS, Northern Ireland, unmatched names

n_ct = defaultdict(lambda: defaultdict(int))
mw_ct = defaultdict(lambda: defaultdict(float))
for x in R.live():                       # de-duplicated: one row per physical project
    gd = next((pdate(x[c]) for c in GRANT_DATES if has(x[c])), None)
    if gd is None or gd.year < Y0 or gd.year > Y1:
        continue
    p = G.party_at(x, gd)     # deciding council on the boundaries of the decision date
    if p == "Nationalist (pre-2007)":
        p = "Other/Ind"
    if p not in ORDER:      # no council party -> attribute to the deciding government
        p = national_bucket(x, gd)
    n_ct[gd.year][p] += 1
    mw_ct[gd.year][p] += num(x["Installed Capacity (MWelec)"]) or 0.0

years = list(range(Y0, Y1 + 1))
series = {p: {"n": [n_ct[y].get(p, 0) for y in years],
              "mw": [round(mw_ct[y].get(p, 0.0)) for y in years]}
          for p in ORDER}
OUT.write_text(json.dumps({"years": years, "order": ORDER, "series": series},
                          separators=(",", ":")), encoding="utf-8")

print("approvals_year.json written.")
print(f"{'yr':4} " + " ".join(f"{p:>7}" for p in ("Con", "Lab", "LibDem", "Other/Ind")))
for i, y in enumerate(years):
    print(f"{y:4} " + " ".join(f"{series[p]['mw'][i]/1000:>7.1f}" for p in ("Con", "Lab", "LibDem", "Other/Ind")))
