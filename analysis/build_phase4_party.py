#!/usr/bin/env python3
"""Phase 4 — planning outcomes by the council party IN CONTROL AT THE TIME OF THE DECISION.

Earlier work (phase 3 land density) attributed *cumulative* approvals to *today's*
controlling party, which credits e.g. Reform with pipelines approved years before it
won the council. This script instead joins every decided local-route project to whoever
controlled its planning authority on the DATE THE DECISION WAS MADE.

Crucially, control is matched at the decision *date*, not just the year. UK local
elections are held in early May, so a permit granted in (say) February 2025 was decided
under the OLD administration even if a new party won that May. Bucketing by year alone
hands the whole year's permits to the post-election winner — which massively over-credits
a surging party (it inflated Reform's approved capacity ~10x). We treat decisions from
June onward as under that year's (post-election) control, and Jan–May as under the
previous year's control.

The controlling-party series itself is legitimate open data — Open Council Data UK,
"largest party by seats" each year. The fix here is purely temporal attribution, not the
source.

Reports, by the party in control at the decision date:
  - approval rate, capacity approved (MW), median months application->decision
  - land density over 2015-2025: MW approved per km2 of land controlled, per year
    (numerator credited at the permit date; denominator = land-years that party actually
    governed, using ONS Standard Area Measurement lower-tier (LAD) land areas).

Inputs  (data/raw):  REPD_publication_Q1_2026.csv, history1973-2015.csv,
                     history2016-26.csv, SAM_LAD_DEC_2018_UK.csv
Output  (data/processed/phase4_party.json)  ->  wired into data.js as window.PHASE4_PARTY

GB local route only — Northern Ireland is not in the GB composition files. National /
strategic-route projects (Scottish Government S36, Welsh Government NSIP, Planning
Inspectorate, Marine Scotland) have no local council and fall out of the join.
"""
import csv, re, json, pathlib
from collections import defaultdict
from statistics import median

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "phase4_party.json"

LAND_WINDOW = range(2015, 2026)  # 2015..2025 inclusive; 2026 omitted (partial/provisional year)
ELECTION_CUTOVER_MONTH = 6       # decisions in month >= 6 fall under that year's (post-May) control

STOP = {"council", "county", "city", "borough", "district", "metropolitan",
        "unitary", "authority", "royal", "of", "the", "cyngor", "sir"}

def norm(s):
    s = s.lower().strip().replace("&", "and").replace(".", "")
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

# ---- control[council_norm][year] = party ----
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

def control_in_year(council_norm, year):
    """Carry-forward: control as recorded for the most recent election year <= year."""
    yrs = ctrl.get(council_norm)
    if not yrs: return None
    cand = [y for y in yrs if y <= year]
    return yrs[max(cand)] if cand else yrs[min(yrs)]

def control_at_decision(council_norm, year, month):
    """Month-aware: Jan–May decisions sit under the previous year's (pre-election) control."""
    eff = year if (month and month >= ELECTION_CUTOVER_MONTH) else year - 1
    return control_in_year(council_norm, eff)

# ---- ONS land area (lower-tier LADs), km2, by normalised name ----
landKm2 = {}
for r in csv.DictReader(open(RAW / "SAM_LAD_DEC_2018_UK.csv", encoding="utf-8-sig")):
    try: landKm2[norm(r["LAD18NM"])] = float(r["AREALHECT"]) / 100.0
    except (ValueError, KeyError): pass

def parse_date(d):
    d = d.strip()
    try:
        dd, mm, yy = d.split("/")
        return int(yy), int(mm), int(dd)
    except (ValueError, IndexError):
        return None, None, None

def months_between(sub, dec):
    sy, sm, sd = parse_date(sub)
    dy, dm, dd = parse_date(dec)
    if sy is None or dy is None: return None
    return (dy - sy) * 12 + (dm - sm) + (dd - sd) / 30.0

GRANT_ST = {"Awaiting Construction", "Under Construction", "Operational", "Decommissioned",
            "Planning Permission Expired", "Application Granted"}
REFUSE_ST = {"Application Refused", "Appeal Refused"}
GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
REFUSE_DATES = ["Planning Permission Refused", "Appeal Refused", "Secretary of State - Refusal"]

agg = defaultdict(lambda: {"n": 0, "granted": 0, "refused": 0, "grantedCap": 0.0, "months": []})
landApprovedMW = defaultdict(float)   # numerator: MW granted in-window, in a LAD, at permit-date control
matched = unmatched = 0
for r in csv.DictReader(open(RAW / "REPD_publication_Q1_2026.csv", encoding="cp1252")):
    st = r["Development Status (short)"]
    if st in GRANT_ST: outcome = "granted"
    elif st in REFUSE_ST: outcome = "refused"
    else: continue
    dec = next((r[c].strip() for c in (GRANT_DATES if outcome == "granted" else REFUSE_DATES) if r[c].strip()), "")
    dy, dm, _ = parse_date(dec)
    if dy is None: continue
    pa = norm(r["Planning Authority"])
    party = control_at_decision(pa, dy, dm)
    if not party:
        unmatched += 1
        continue
    matched += 1
    try: cap = float(r["Installed Capacity (MWelec)"] or 0)
    except ValueError: cap = 0.0
    a = agg[party]
    a["n"] += 1
    a[outcome] += 1
    if outcome == "granted":
        a["grantedCap"] += cap
        # land-density numerator: granted, in window, planning authority is a lower-tier LAD
        if dy in LAND_WINDOW and pa in landKm2:
            landApprovedMW[party] += cap
    sub = r["Planning Application Submitted"].strip()
    if sub and dec:
        m = months_between(sub, dec)
        if m is not None and 0 <= m < 360: a["months"].append(m)

# ---- land-years controlled per party over the window (lower-tier LADs only) ----
landYears = defaultdict(float)  # km2 * years
nYears = len(LAND_WINDOW)
for lad, area in landKm2.items():
    for y in LAND_WINDOW:
        p = control_in_year(lad, y)
        if p: landYears[p] += area

ORDER = ["Con", "Lab", "LibDem", "SNP", "Plaid", "Green", "Reform", "Other/Ind", "Nationalist (pre-2007)"]
byParty = {}
for p in ORDER:
    a = agg.get(p)
    if not a or (a["granted"] + a["refused"]) == 0: continue
    ly = landYears.get(p, 0.0)
    byParty[p] = {
        "n": a["n"], "granted": a["granted"], "refused": a["refused"],
        "approvalRate": round(100 * a["granted"] / (a["granted"] + a["refused"]), 1),
        "approvedMW": round(a["grantedCap"]),
        "medMonthsToDecision": round(median(a["months"]), 1) if a["months"] else None,
        "nTimed": len(a["months"]),
        # land density (2015-2025, lower-tier geography)
        "landApprovedMW": round(landApprovedMW.get(p, 0.0)),
        "avgLandKm2": round(ly / nYears),
        "mwPerKm2PerYr": round(landApprovedMW.get(p, 0.0) / ly, 4) if ly else None,
    }

out = {
    "note": ("By council party in control AT THE DECISION DATE (month-aware; Jan-May "
             "decisions fall under the pre-election administration). GB local route only. "
             "Land density: 2015-2025, lower-tier (LAD) geography."),
    "landWindow": f"{LAND_WINDOW.start}-{LAND_WINDOW.stop - 1}",
    "matchedDecided": matched, "unmatchedDecided": unmatched,
    "byParty": byParty,
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"matched={matched} unmatched={unmatched} -> {OUT}")
for p, v in byParty.items():
    print(f"  {p:24s} n={v['n']:5d} appr={v['approvalRate']:5.1f}% MW={v['approvedMW']:7d} "
          f"med={v['medMonthsToDecision']}mo  land:{v['landApprovedMW']:6d}MW/{v['avgLandKm2']:6d}km2 "
          f"={v['mwPerKm2PerYr']}")
