"""Shared council-control lookup — single source of truth for every build script.

CONTROL, not seat count. Earlier builds took "largest party by seats", which mislabels
the ~3% of council-years run by a coalition or minority administration (e.g. Cornwall
2025: Reform is the largest party, but a Lib Dem/Independent coalition runs it). We now
read the `majority` column that Open Council Data UK provides, which encodes real control:

    "Con"            -> majority control
    "LAB min"        -> Labour minority administration
    "LD/IND"         -> Lib Dem / Independent coalition  (credited to the LEAD party, LD)
    "Con plurality"  -> no overall control, Conservatives largest (credited to Con)
    "NULL"/""        -> unknown -> fall back to largest party by seats

Exposes: norm(), take_office(), control_in_year(), control_at() — all keyed on a
normalised council name.
"""
import csv, re, datetime, pathlib
from collections import defaultdict

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

STOP = {"council", "county", "city", "borough", "district", "metropolitan", "unitary",
        "authority", "royal", "of", "the", "cyngor", "sir"}

def norm(s):
    s = (s or "").lower().strip().replace("&", "and").replace(".", "")
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(t for t in s.split() if t and t not in STOP)

# seat-count column -> party (fallback only, when the majority column is blank)
_SEAT = {"con": "Con", "lab": "Lab", "ld": "LibDem", "green": "Green", "snp": "SNP",
         "pc": "Plaid", "ref": "Reform", "ukip": "Reform", "other": "Other/Ind",
         "nat": "Other/Ind"}
# parsed majority token -> party
_MAJ = {"CON": "Con", "LAB": "Lab", "LD": "LibDem", "LIBDEM": "LibDem", "SNP": "SNP",
        "PLAID": "Plaid", "PC": "Plaid", "GREEN": "Green", "REF": "Reform", "UKIP": "Reform",
        "IND": "Other/Ind", "OTHER": "Other/Ind", "NAT": "Other/Ind"}

def _largest(row, cols):
    best, bv = None, -1
    for c in cols:
        try: v = int(row[c] or 0)
        except (ValueError, TypeError): v = 0
        if v > bv: best, bv = c, v
    return best, bv

def _party_from_majority(m):
    """Turn a `majority` cell into a party, or None if blank/unusable."""
    m = (m or "").strip()
    if not m or m.upper() == "NULL":
        return None
    core = re.sub(r"\s*(plurality|min|mayor|majority)\s*", " ", m, flags=re.I).strip()
    if "/" in core:                     # coalition -> lead (first-listed) party
        core = core.split("/")[0].strip()
    return _MAJ.get(core.upper(), "Other/Ind")   # any other non-blank label = independent/other

# ctrl[normalised council][election year] = controlling party
ctrl = defaultdict(dict)
_FILES = [("history1973-2015.csv", ["con", "lab", "ld", "other", "nat"]),
          ("history2016-26.csv", ["con", "lab", "ld", "green", "ukip", "ref", "pc", "snp", "other"])]
for _fname, _cols in _FILES:
    for r in csv.DictReader(open(RAW / _fname, encoding="cp1252")):
        party = _party_from_majority(r.get("majority"))
        if party is None:                         # fall back to largest party by seats
            best, bv = _largest(r, _cols)
            if bv <= 0:
                continue
            party = _SEAT.get(best, "Other/Ind")
        ctrl[norm(r["authority"])][int(r["year"])] = party

def take_office(year):
    """First Thursday of May + 4 days: when a newly elected council takes office."""
    may1 = datetime.date(year, 5, 1)
    return may1 + datetime.timedelta(days=(3 - may1.weekday()) % 7) + datetime.timedelta(days=4)

def control_in_year(council_norm, year):
    yrs = ctrl.get(council_norm)
    if not yrs:
        return None
    cand = [y for y in yrs if y <= year]
    return yrs[max(cand)] if cand else yrs[min(yrs)]

def control_at(council_norm, d):
    """Controlling party on date `d`, honouring the May take-office cut-off."""
    if d is None:
        return None
    eff_year = d.year if d >= take_office(d.year) else d.year - 1
    return control_in_year(council_norm, eff_year)
