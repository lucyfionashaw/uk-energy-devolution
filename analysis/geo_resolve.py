"""Resolve each REPD planning-authority name to the council we attribute the decision to,
its route (local / national / etc.), and — where the party is blank — why.

Design decision (per the project owner): the planning authority named in the REPD IS the
authority. We do NOT split a named unitary back into its former districts. So "Somerset"
is attributed to Somerset Council, with control read at the decision date; a pre-2023
"Somerset" decision therefore falls under Somerset County Council's control on that date.

The only special handling is:
  - LAND AREA for the 11 unitaries created by the 2019-2023 reorganisation, which the 2018
    ONS land file does not list by their new name. Their area = the sum of their former
    districts' ONS Standard Area Measurements (whole-district mergers, so the areas add
    exactly). The former-district rows are then dropped from the land table, because no REPD
    project is labelled with an old district name (the REPD uses current names throughout),
    and keeping both would double-count that land in the density denominator.
  - ROUTE tagging so national consenting bodies, Northern Ireland, Crown Dependencies and
    unrecognised names are never confused with a genuine missing match.
  - a few clear spelling / renaming ALIASes so obvious typos still match a real council.
"""
import csv, pathlib, datetime
from council_control import norm, ctrl

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE.parent / "data" / "raw"

# ---- national consenting bodies (no local council by design) ----
NATIONAL_HINTS = [
    "scottish government", "planning inspectorate", "crown estate", "marine scotland",
    "northern ireland planning", "decc", "desnz", "beis", "marine management",
    "welsh government", "secretary of state", "national infrastructure", "nsip",
    "infrastructure planning", "energy consents unit",
]
def is_national(pa_raw):
    n = norm(pa_raw)
    return any(h in n for h in NATIONAL_HINTS)

# ---- Crown Dependencies (not UK local authorities) ----
OUTSIDE_GB = {"isle man", "jersey", "guernsey"}

# ---- clear typo / renaming aliases -> the real council name in the control series ----
ALIAS = {
    "neath port talbort": "neath port talbot",
    "burnely": "burnley",
    "argyll bute and south lochaber": "argyll and bute",
}

# ---- new unitary -> former districts (for the LAND-AREA crosswalk only) ----
REORG = {
    "somerset": ["Mendip", "Sedgemoor", "Taunton Deane", "West Somerset", "South Somerset",
                 "Somerset West and Taunton"],
    "north yorkshire": ["Craven", "Hambleton", "Harrogate", "Richmondshire", "Ryedale",
                        "Scarborough", "Selby"],
    "cumberland": ["Allerdale", "Carlisle", "Copeland"],
    "westmorland and furness": ["Barrow-in-Furness", "Eden", "South Lakeland"],
    "buckinghamshire": ["Aylesbury Vale", "Chiltern", "South Bucks", "Wycombe"],
    "dorset": ["East Dorset", "North Dorset", "Purbeck", "West Dorset", "Weymouth and Portland"],
    "bournemouth christchurch and poole": ["Bournemouth", "Christchurch", "Poole"],
    "west northamptonshire": ["Daventry", "Northampton", "South Northamptonshire"],
    "north northamptonshire": ["Corby", "East Northamptonshire", "Kettering", "Wellingborough"],
    "east suffolk": ["Suffolk Coastal", "Waveney"],
    "west suffolk": ["Forest Heath", "St Edmundsbury"],
}

# ---- ONS land area (km2) by normalised name ----
# 2018 SAM gives every pre-reorg district; the new unitaries are the sum of their former
# districts. NI councils are loaded (their real area shows in the audit export) but tracked
# in NI_LADS so the GB-only land-density chart can exclude them.
_land = {}
NI_LADS = set()
for _r in csv.DictReader(open(RAW / "SAM_LAD_DEC_2018_UK.csv", encoding="utf-8-sig")):
    _code = (_r.get("LAD18CD") or "")
    _nm = norm(_r["LAD18NM"])
    try:
        _land[_nm] = round(float(_r["AREALHECT"]) / 100.0, 1)
    except (ValueError, KeyError):
        continue
    if _code.startswith("N"):
        NI_LADS.add(_nm)
for _u, _ds in REORG.items():
    _land[_u] = round(sum(_land.get(norm(_d), 0.0) for _d in _ds), 1)
    for _d in _ds:                       # drop the former districts: no project uses those names,
        _land.pop(norm(_d), None)        # and keeping them would double-count the land.

def land_km2(name_norm):
    return _land.get(name_norm)

def parse_date(s):
    s = (s or "").strip()
    try:
        d, m, y = s.split("/"); return datetime.date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None

def resolve(pa_raw, country=None):
    """Return (authority_norm, route, note).

    authority_norm: the council to look up control/land for (None if no local council).
    route: 'Local council' | 'National' | 'Northern Ireland' | 'Outside GB' | 'Unmatched'.
    note: human-readable reason, especially when there is no assignable party.
    """
    pa = norm(pa_raw)
    pa = ALIAS.get(pa, pa)
    if not pa:
        return None, "Unmatched", "no planning authority named"
    if is_national(pa_raw):
        return None, "National", f"national consenting body ({pa_raw.strip()}) — no local council"
    if pa in OUTSIDE_GB:
        return None, "Outside GB", f"Crown Dependency ({pa_raw.strip()}) — outside Great Britain"
    if pa in ctrl:
        if (country or "").strip() == "Northern Ireland":
            return pa, "Northern Ireland", "Northern Ireland council — excluded from the GB land comparison"
        return pa, "Local council", ""
    if (country or "").strip() == "Northern Ireland":
        return None, "Northern Ireland", f'unrecognised NI authority name ("{pa_raw.strip()}")'
    return None, "Unmatched", f'unrecognised authority name ("{pa_raw.strip()}")'

def party_at(row, decision_date):
    """Controlling party of the named planning authority on decision_date. None if there is no
    local council or no date. Import control_at here to avoid a circular import."""
    from council_control import control_at
    if decision_date is None:
        return None
    auth, _route, _note = resolve(row["Planning Authority"], row.get("Country"))
    return control_at(auth, decision_date) if auth else None
