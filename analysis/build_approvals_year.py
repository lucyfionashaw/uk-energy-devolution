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

STOP = {"council", "county", "city", "borough", "district", "metropolitan", "unitary",
        "authority", "royal", "of", "the", "cyngor", "sir"}
def norm(s):
    s = (s or "").lower().strip().replace("&", "and").replace(".", "")
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(t for t in s.split() if t and t not in STOP)
PC = {"con": "Con", "lab": "Lab", "ld": "LibDem", "green": "Green", "snp": "SNP",
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
    b, bv = largest(r, ["con", "lab", "ld", "other", "nat"])
    if bv <= 0: continue
    ctrl[norm(r["authority"])][int(r["year"])] = "Other/Ind" if b == "nat" else PC.get(b, "Other/Ind")
for r in csv.DictReader(open(RAW / "history2016-26.csv", encoding="cp1252")):
    b, bv = largest(r, ["con", "lab", "ld", "green", "ukip", "ref", "pc", "snp", "other"])
    if bv <= 0: continue
    ctrl[norm(r["authority"])][int(r["year"])] = PC.get(b, "Other/Ind")
def take_office(y):
    m = datetime.date(y, 5, 1)
    return m + datetime.timedelta(days=(3 - m.weekday()) % 7) + datetime.timedelta(days=4)
def control_at(pa, d):
    yrs = ctrl.get(pa)
    if not yrs or d is None: return None
    eff = d.year if d >= take_office(d.year) else d.year - 1
    cand = [y for y in yrs if y <= eff]
    return yrs[max(cand)] if cand else None

GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
ORDER = ["Con", "Lab", "LibDem", "SNP", "Plaid", "Green", "Reform", "Other/Ind"]
Y0, Y1 = 2010, 2025

n_ct = defaultdict(lambda: defaultdict(int))
mw_ct = defaultdict(lambda: defaultdict(float))
for x in csv.DictReader(open(RAW / "REPD_publication_Q1_2026.csv", encoding="latin-1")):
    gd = next((pdate(x[c]) for c in GRANT_DATES if has(x[c])), None)
    if gd is None or gd.year < Y0 or gd.year > Y1:
        continue
    p = control_at(norm(x["Planning Authority"]), gd)
    if p == "Nationalist (pre-2007)":
        p = "Other/Ind"
    if p not in ORDER:      # unmatched / national-route projects have no council party
        continue
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
