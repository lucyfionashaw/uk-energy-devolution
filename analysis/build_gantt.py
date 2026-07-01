#!/usr/bin/env python3
"""Stage durations for the Gantt timelines on the speed page.

Stages (the dates REPD records; planning permission IS the consent, so there is no
separate consent date to split "decision -> construction"):
  1. Submission  -> decision        (Planning Application Submitted -> Permission Granted)
  2. Decision    -> construction    (Permission Granted -> Under Construction)
  3. Construction-> commissioning   (Under Construction -> Operational)

Two products:
  * buckets : one row per technology×scale bucket (Solar small/large, Onshore small/large,
              Offshore, Battery, Bioenergy, Hydro), each with median AND mean AND sample
              size for all three stages. Rows are ordered fastest→slowest by total median.
  * bySize  : the same three stages by capacity band, for the technologies where size drives
              the timeline (Solar, Onshore wind, Battery) — to show where the break is.

Every stage's stat is over the projects that have BOTH endpoint dates, so later stages are
survivor-selected (smaller n). Sample sizes are carried through for the tooltip/notes.

Output: data/processed/gantt_data.json  ->  window.GANTT
Run:    python3 analysis/build_gantt.py   (then re-run build_data_js.py)
"""
import csv, json, pathlib, datetime, re
from collections import defaultdict
from statistics import median, mean

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CSVF = RAW / "REPD_publication_Q1_2026.csv"
OUT = ROOT / "data" / "processed" / "gantt_data.json"

# --- council-control series + date-aware lookup (mirrors build_phase4_party.py) ---
STOP = {"council", "county", "city", "borough", "district", "metropolitan",
        "unitary", "authority", "royal", "of", "the", "cyngor", "sir"}
def norm(s):
    s = (s or "").lower().strip().replace("&", "and").replace(".", "")
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(t for t in s.split() if t and t not in STOP)
PARTY_COL = {"con": "Con", "lab": "Lab", "ld": "LibDem", "green": "Green", "snp": "SNP",
             "pc": "Plaid", "ref": "Reform", "ukip": "Reform", "other": "Other/Ind"}
def _largest(row, cols):
    best, bv = None, -1
    for c in cols:
        try: v = int(row[c] or 0)
        except ValueError: v = 0
        if v > bv: best, bv = c, v
    return best, bv
_ctrl = defaultdict(dict)
for r in csv.DictReader(open(RAW / "history1973-2015.csv", encoding="cp1252")):
    best, bv = _largest(r, ["con", "lab", "ld", "other", "nat"])
    if bv <= 0: continue
    _ctrl[norm(r["authority"])][int(r["year"])] = "Other/Ind" if best == "nat" else PARTY_COL.get(best, "Other/Ind")
for r in csv.DictReader(open(RAW / "history2016-26.csv", encoding="cp1252")):
    best, bv = _largest(r, ["con", "lab", "ld", "green", "ukip", "ref", "pc", "snp", "other"])
    if bv <= 0: continue
    _ctrl[norm(r["authority"])][int(r["year"])] = PARTY_COL.get(best, "Other/Ind")
def _take_office(year):
    may1 = datetime.date(year, 5, 1)
    return may1 + datetime.timedelta(days=(3 - may1.weekday()) % 7) + datetime.timedelta(days=4)
def control_at(council_norm, d):
    yrs = _ctrl.get(council_norm)
    if not yrs or d is None: return None
    eff = d.year if d >= _take_office(d.year) else d.year - 1
    cand = [y for y in yrs if y <= eff]
    return yrs[max(cand)] if cand else None

def pdate(s):
    s = (s or "").strip()
    try:
        d, m, y = s.split("/")
        return datetime.date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None

def months(a, b):
    if a is None or b is None:
        return None
    v = (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.0
    return v if 0 <= v < 360 else None

def num(x):
    x = (x or "").strip().replace(",", "")
    try:
        return float(x)
    except ValueError:
        return None

SUB, GR, UC, OP = ("Planning Application Submitted", "Planning Permission  Granted",
                   "Under Construction", "Operational")
STAGE_COLS = [(SUB, GR), (GR, UC), (UC, OP)]
STAGE_LABELS = ["Submission → decision", "Decision → construction start",
                "Construction → commissioning"]

BIO = {"Anaerobic Digestion", "Landfill Gas", "Biomass (dedicated)", "Biomass (co-firing)",
       "EfW Incineration", "Advanced Conversion Technologies", "Sewage Sludge Digestion"}
HYDRO = {"Small Hydro", "Large Hydro", "Pumped Storage Hydroelectricity"}

GRANT_DATES = ["Planning Permission  Granted", "Appeal Granted", "Secretary of State - Granted"]
rows = list(csv.DictReader(open(CSVF, encoding="latin-1")))
for x in rows:
    x["_mw"] = num(x["Installed Capacity (MWelec)"])
    x["_t"] = x["Technology Type"].strip()
    # party controlling the deciding council at the grant (decision) date
    gdate = next((pdate(x[c]) for c in GRANT_DATES if (x[c] or "").strip()), None)
    x["_party"] = control_at(norm(x["Planning Authority"]), gdate)

def bucket_of(x):
    t, mw = x["_t"], x["_mw"]
    if t == "Solar Photovoltaics":
        return "SolarSmall" if (mw is not None and mw < 10) else "SolarLarge"
    if t == "Wind Onshore":
        return "OnshoreSmall" if (mw is not None and mw < 10) else "OnshoreLarge"
    if t == "Wind Offshore":
        return "Offshore"
    if t == "Battery":
        return "Battery"
    if t in BIO:
        return "Bioenergy"
    if t in HYDRO:
        return "Hydro"
    return None

BUCKET_NAME = {
    "SolarSmall": "Solar · small (<10 MW)", "SolarLarge": "Solar · large (≥10 MW)",
    "OnshoreSmall": "Onshore wind · small (<10 MW)", "OnshoreLarge": "Onshore wind · large (≥10 MW)",
    "Offshore": "Offshore wind", "Battery": "Battery",
    "Bioenergy": "Bioenergy", "Hydro": "Hydro",
}

MIN_STAGE = 15  # a stage needs this many validly-dated projects to report a duration

def stats(rowset):
    """median, mean, n for each of the three stages over a set of rows.

    A stage is only counted for a project when BOTH its endpoint dates exist AND fall in
    order (0 ≤ gap < 360 months). Some REPD records have dates out of order — e.g. an
    "Under Construction" date logged before the grant date, or an operational site with no
    construction date — so the three stages draw on different, non-nested subsets. Stages
    with fewer than MIN_STAGE valid projects are reported as null (no bar) rather than a
    noisy one- or two-project median.
    """
    lists = [[], [], []]
    for x in rowset:
        for i, (c0, c1) in enumerate(STAGE_COLS):
            m = months(pdate(x[c0]), pdate(x[c1]))
            if m is not None:
                lists[i].append(m)
    med = [round(median(l), 1) if len(l) >= MIN_STAGE else None for l in lists]
    avg = [round(mean(l), 1) if len(l) >= MIN_STAGE else None for l in lists]
    # the bar is a cumulative timeline, so once a stage is missing the following stages
    # have no valid start — drop them rather than stack them in the wrong place
    for arr in (med, avg):
        gap = False
        for i in range(3):
            if arr[i] is None:
                gap = True
            elif gap:
                arr[i] = None
    n = [len(l) for l in lists]
    return {"median": med, "mean": avg, "n": n}

# ---- buckets -----------------------------------------------------------------
grouped = defaultdict(list)
for x in rows:
    b = bucket_of(x)
    if b:
        grouped[b].append(x)

buckets = []
for key, name in BUCKET_NAME.items():
    if key not in grouped:
        continue
    s = stats(grouped[key])
    total = sum(v for v in s["median"] if v)   # order fastest→slowest by total median
    buckets.append({"key": key, "name": name, "total": total, **s})
buckets.sort(key=lambda d: d["total"])

# ---- by size band (Solar / Onshore wind / Battery) ---------------------------
BANDS = [(1, "<1 MW"), (5, "1–5 MW"), (10, "5–10 MW"), (25, "10–25 MW"),
         (50, "25–50 MW"), (100, "50–100 MW"), (float("inf"), "100+ MW")]

def band_of(mw):
    if mw is None:
        return None
    for hi, lab in BANDS:
        if mw < hi:
            return lab
    return "100+ MW"

SIZE_TECHS = {"Solar": "Solar Photovoltaics", "OnshoreWind": "Wind Onshore", "Battery": "Battery"}
bySize = {}
for key, tname in SIZE_TECHS.items():
    per = defaultdict(list)
    for x in rows:
        if x["_t"] == tname:
            b = band_of(x["_mw"])
            if b:
                per[b].append(x)
    bySize[key] = [{"band": lab, **stats(per[lab])} for _, lab in BANDS if lab in per]

# ---- by controlling party (at the decision date), per technology filter ------
# Only local-route projects with a matched council carry a party; national-route
# (offshore wind, NSIP) and unmatched councils have none.
PARTY_NAME = {"Con": "Conservative", "Lab": "Labour", "LibDem": "Lib Dem", "SNP": "SNP",
              "Plaid": "Plaid Cymru", "Green": "Green", "Reform": "Reform / UKIP",
              "Other/Ind": "Other / Ind"}
PARTY_TECHS = {"All": None, "Solar": "Solar Photovoltaics",
               "OnshoreWind": "Wind Onshore", "Battery": "Battery"}
MIN_N = 30  # need a real sample for the first (decision) stage

byParty = {}
for tkey, tname in PARTY_TECHS.items():
    per = defaultdict(list)
    for x in rows:
        if tname is not None and x["_t"] != tname:
            continue
        p = x["_party"]
        if p in PARTY_NAME:
            per[p].append(x)
    party_rows = []
    for p in PARTY_NAME:
        if p not in per:
            continue
        s = stats(per[p])
        if s["n"][0] < MIN_N:      # too few decided projects to time reliably
            continue
        total = sum(v for v in s["median"] if v)
        party_rows.append({"key": p, "name": PARTY_NAME[p], "total": total, **s})
    # sort by the DECISION stage (every party has it) so parties missing later-stage data
    # aren't misranked as "fastest overall"
    party_rows.sort(key=lambda d: d["median"][0])
    byParty[tkey] = party_rows

out = {"stages": STAGE_LABELS, "buckets": buckets, "bySize": bySize, "byParty": byParty,
       "sizeTechNames": {"Solar": "Solar", "OnshoreWind": "Onshore wind", "Battery": "Battery"},
       "partyTechNames": {"All": "All technologies", "Solar": "Solar",
                          "OnshoreWind": "Onshore wind", "Battery": "Battery"}}
OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

print("gantt_data.json written.")
print("buckets (fastest→slowest by total median):")
for b in buckets:
    print(f"  {b['name']:34s} median {b['median']}  n {b['n']}")
print("\nby party — All technologies (fastest→slowest):")
for b in byParty["All"]:
    print(f"  {b['name']:16s} median {b['median']}  n {b['n']}")
print("\nby party — Solar:")
for b in byParty["Solar"]:
    print(f"  {b['name']:16s} median {b['median']}  n {b['n']}")
