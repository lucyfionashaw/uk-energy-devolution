#!/usr/bin/env python3
"""Phase 4 — planning outcomes by the council party IN CONTROL AT THE TIME OF THE DECISION.

Earlier work (phase 3 land density) attributed *cumulative* approvals to *today's*
controlling party, which credits e.g. Reform with pipelines approved years before it
won the council. This script instead joins every decided local-route project to whoever
controlled its planning authority in the YEAR THE DECISION WAS MADE, and reports, by that
party: project count, approval rate, capacity approved (MW), and median months from
application to decision.

Inputs  (data/raw):  REPD_publication_Q1_2026.csv, history1973-2015.csv, history2016-26.csv
Output  (data/processed/phase4_party.json)  ->  wired into data.js as window.PHASE4_PARTY

Controlling party = largest party by seats in that council-year (the same
"largest-party proxy" used in phase 2). National/strategic-route projects (Scottish
Government S36, Welsh Government NSIP, Planning Inspectorate, Marine Scotland, etc.) have
no local council and fall out of the join automatically. Northern Ireland is not in the
GB composition files, so phase 4 is GB local route only — consistent with the
approval-rate-by-party chart on the politics page.
"""
import csv, re, json, pathlib
from collections import defaultdict
from statistics import median

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "phase4_party.json"

STOP = {"council", "county", "city", "borough", "district", "metropolitan",
        "unitary", "authority", "royal", "of", "the", "cyngor", "sir"}

def norm(s):
    s = s.lower().strip().replace("&", "and").replace(".", "")
    s = re.sub(r"[^a-z ]", " ", s)
    toks = [t for t in s.split() if t and t not in STOP]
    return " ".join(toks)

PARTY_COL = {"con": "Con", "lab": "Lab", "ld": "LibDem", "green": "Green", "snp": "SNP",
             "pc": "Plaid", "ref": "Reform", "ukip": "Reform", "other": "Other/Ind"}

def largest(row, cols):
    best, bv = None, -1
    for c in cols:
        try: v = int(row[c] or 0)
        except ValueError: v = 0
        if v > bv: best, bv = c, v
    return best, bv

# ---- control[council_norm] -> sorted [(year, party)] ----
ctrl = defaultdict(list)
for r in csv.DictReader(open(RAW / "history1973-2015.csv", encoding="cp1252")):
    best, bv = largest(r, ["con", "lab", "ld", "other", "nat"])
    if bv <= 0: continue
    party = "Nationalist (pre-2007)" if best == "nat" else PARTY_COL.get(best, "Other/Ind")
    ctrl[norm(r["authority"])].append((int(r["year"]), party))
for r in csv.DictReader(open(RAW / "history2016-26.csv", encoding="cp1252")):
    best, bv = largest(r, ["con", "lab", "ld", "green", "ukip", "ref", "pc", "snp", "other"])
    if bv <= 0: continue
    ctrl[norm(r["authority"])].append((int(r["year"]), PARTY_COL.get(best, "Other/Ind")))
for k in ctrl: ctrl[k].sort()

def control_at(council_norm, year):
    lst = ctrl.get(council_norm)
    if not lst: return None
    pick = lst[0][1]
    for y, p in lst:
        if y <= year: pick = p
        else: break
    return pick

def yr(d):
    d = d.strip()
    try: return int(d.split("/")[-1])
    except (ValueError, IndexError): return None

def months(sub, dec):
    try:
        a, b = sub.split("/"), dec.split("/")
        return (int(b[2]) - int(a[2])) * 12 + (int(b[1]) - int(a[1])) + (int(b[0]) - int(a[0])) / 30.0
    except (ValueError, IndexError): return None

GRANT_ST = {"Awaiting Construction", "Under Construction", "Operational", "Decommissioned",
            "Planning Permission Expired", "Application Granted"}
REFUSE_ST = {"Application Refused", "Appeal Refused"}
GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
REFUSE_DATES = ["Planning Permission Refused", "Appeal Refused", "Secretary of State - Refusal"]

agg = defaultdict(lambda: {"n": 0, "granted": 0, "refused": 0, "grantedCap": 0.0, "months": []})
matched = unmatched = 0
for r in csv.DictReader(open(RAW / "REPD_publication_Q1_2026.csv", encoding="cp1252")):
    st = r["Development Status (short)"]
    if st in GRANT_ST: outcome = "granted"
    elif st in REFUSE_ST: outcome = "refused"
    else: continue
    dec = next((r[c].strip() for c in (GRANT_DATES if outcome == "granted" else REFUSE_DATES) if r[c].strip()), "")
    dyear = yr(dec)
    if dyear is None: continue
    party = control_at(norm(r["Planning Authority"]), dyear)
    if not party:
        unmatched += 1
        continue
    matched += 1
    try: cap = float(r["Installed Capacity (MWelec)"] or 0)
    except ValueError: cap = 0.0
    a = agg[party]
    a["n"] += 1
    a[outcome] += 1
    if outcome == "granted": a["grantedCap"] += cap
    sub = r["Planning Application Submitted"].strip()
    if sub and dec:
        m = months(sub, dec)
        if m is not None and 0 <= m < 360: a["months"].append(m)

ORDER = ["Con", "Lab", "LibDem", "SNP", "Plaid", "Green", "Reform", "Other/Ind", "Nationalist (pre-2007)"]
byParty = {}
for p in ORDER:
    a = agg.get(p)
    if not a or (a["granted"] + a["refused"]) == 0: continue
    byParty[p] = {
        "n": a["n"], "granted": a["granted"], "refused": a["refused"],
        "approvalRate": round(100 * a["granted"] / (a["granted"] + a["refused"]), 1),
        "approvedMW": round(a["grantedCap"]),
        "medMonthsToDecision": round(median(a["months"]), 1) if a["months"] else None,
        "nTimed": len(a["months"]),
    }

out = {
    "note": "By council party in control in the YEAR THE DECISION WAS MADE. GB local route only.",
    "matchedDecided": matched, "unmatchedDecided": unmatched,
    "byParty": byParty,
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"matched={matched} unmatched={unmatched} -> {OUT}")
for p, v in byParty.items():
    print(f"  {p:24s} n={v['n']:5d} appr={v['approvalRate']:5.1f}% MW={v['approvedMW']:7d} med={v['medMonthsToDecision']}mo")
