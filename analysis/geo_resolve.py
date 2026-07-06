"""Resolve each REPD project to the council THAT DECIDED IT, ON THE BOUNDARIES OF THE DAY.

Two problems this fixes:

1. Local-government reorganisation (2019-2023). Eleven English areas merged their
   district councils into new unitaries (Somerset, North Yorkshire, Cumberland,
   Westmorland & Furness, Buckinghamshire, Dorset, Bournemouth/Christchurch/Poole,
   West & North Northamptonshire, East & West Suffolk). The REPD relabels EVERY project
   in those areas with the CURRENT unitary name — even a decision made in 2004. So a
   pre-reorganisation decision looks like it was taken by a council that did not yet
   exist. We instead:
     - decision BEFORE the reorg year  -> find the historic DISTRICT from the project's
       grid reference (point-in-polygon against 2013 district boundaries) and use that
       district's control + land area on the decision date;
     - decision ON/AFTER the reorg year -> use the new unitary (land = sum of its former
       districts' ONS areas).

2. Non-council planning authorities. National consenting bodies (S36 / NSIP / offshore)
   have no local council by design; a handful of rows carry name typos, parliamentary
   constituencies, Crown Dependencies or blanks. We tag the "route" so the two are never
   confused with a genuine missing match.

Coordinates are the REPD X/Y British National Grid easting/northing (EPSG:27700),
reprojected to WGS84 for the point-in-polygon test against the England 2013 LAD polygons.
"""
import csv, json, pathlib, datetime
from council_control import norm, ctrl

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE.parent / "data" / "raw"

# ---- national consenting bodies (no local council by design) ----
# Matched on the normalised planning-authority name containing any of these tokens.
NATIONAL_HINTS = [
    "scottish government", "planning inspectorate", "crown estate", "marine scotland",
    "northern ireland planning", "decc", "desnz", "beis", "marine management",
    "welsh government", "secretary of state", "national infrastructure", "nsip",
    "infrastructure planning", "energy consents unit",
]
def is_national(pa_raw):
    n = norm(pa_raw)
    return any(h in n for h in NATIONAL_HINTS)

# ---- Crown Dependencies / outside-GB (not UK local authorities) ----
OUTSIDE_GB = {"isle man", "jersey", "guernsey"}

# ---- typo / renaming aliases -> the real council name in the control series ----
# Only clear-cut spelling or constituency-vs-council fixes; ambiguous names stay unmatched.
ALIAS = {
    "neath port talbort": "neath port talbot",
    "burnely": "burnley",
    "argyll bute and south lochaber": "argyll and bute",
}

# ---- reorganised areas: new unitary -> (vesting year, [former districts]) ----
# Former-district names as they appear in the 2013 LAD boundaries / control series.
REORG = {
    "somerset": (2023, ["Mendip", "Sedgemoor", "Taunton Deane", "West Somerset", "South Somerset",
                        "Somerset West and Taunton"]),
    "north yorkshire": (2023, ["Craven", "Hambleton", "Harrogate", "Richmondshire", "Ryedale",
                        "Scarborough", "Selby"]),
    "cumberland": (2023, ["Allerdale", "Carlisle", "Copeland"]),
    "westmorland and furness": (2023, ["Barrow-in-Furness", "Eden", "South Lakeland"]),
    "buckinghamshire": (2020, ["Aylesbury Vale", "Chiltern", "South Bucks", "Wycombe"]),
    "dorset": (2019, ["East Dorset", "North Dorset", "Purbeck", "West Dorset", "Weymouth and Portland"]),
    "bournemouth christchurch and poole": (2019, ["Bournemouth", "Christchurch", "Poole"]),
    "west northamptonshire": (2021, ["Daventry", "Northampton", "South Northamptonshire"]),
    "north northamptonshire": (2021, ["Corby", "East Northamptonshire", "Kettering", "Wellingborough"]),
    "east suffolk": (2019, ["Suffolk Coastal", "Waveney"]),
    "west suffolk": (2019, ["Forest Heath", "St Edmundsbury"]),
}
# norm(district) -> parent unitary, for quick membership tests
_DISTRICT_PARENT = {norm(d): u for u, (_, ds) in REORG.items() for d in ds}
# vesting year of each new unitary, and of each former district (the year it was abolished)
UNITARY_VEST = {u: yr for u, (yr, _) in REORG.items()}
DISTRICT_VEST = {norm(d): yr for u, (yr, ds) in REORG.items() for d in ds}

# ---- ONS land area (km2) for a lower-tier authority, by normalised name ----
# 2018 SAM gives every pre-reorg district; the new unitaries are the sum of their former
# districts (whole-district mergers, so the areas add exactly). Northern Ireland councils
# ARE loaded (their land is real and shown in the audit export) but tracked in NI_LADS so
# the GB-only land-density chart can exclude them.
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
for _u, (_yr, _ds) in REORG.items():
    _tot = 0.0
    for _d in _ds:
        _tot += _land.get(norm(_d), 0.0)
    _land[_u] = round(_tot, 1)

def land_km2(name_norm):
    return _land.get(name_norm)

# ---- 2013 England LAD polygons for point-in-polygon (lazy, needs shapely) ----
_polys = None            # norm(name) -> shapely geometry
_to_wgs = None
def _load_polys():
    global _polys, _to_wgs
    if _polys is not None:
        return
    from shapely.geometry import shape
    from pyproj import Transformer
    _to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)
    _polys = {}
    gj = json.load(open(RAW / "lad_eng.geojson"))
    wanted = set(_DISTRICT_PARENT)          # only the ~40 reorganised districts matter
    for f in gj["features"]:
        nm = norm(f["properties"]["LAD13NM"])
        if nm in wanted:
            _polys[nm] = shape(f["geometry"])

def district_from_coords(easting, northing, parent_unitary):
    """Which former district (of parent_unitary) contains this BNG point? None if outside all."""
    _load_polys()
    try:
        lon, lat = _to_wgs.transform(float(easting), float(northing))
    except (ValueError, TypeError):
        return None
    from shapely.geometry import Point
    p = Point(lon, lat)
    for d in REORG[parent_unitary][1]:
        g = _polys.get(norm(d))
        if g is not None and g.contains(p):
            return norm(d)
    return None

def parse_date(s):
    s = (s or "").strip()
    try:
        d, m, y = s.split("/"); return datetime.date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None

def party_at(row, decision_date):
    """Controlling party of the DECIDING council on decision_date, resolving reorganised areas
    to the historic district. `row` is a REPD dict row. Returns None if no local council / no date.

    Import here (not at module top) to avoid a circular import with council_control.
    """
    from council_control import control_at
    if decision_date is None:
        return None
    auth, _route, _note = resolve(row["Planning Authority"], decision_date,
                                  row.get("X-coordinate"), row.get("Y-coordinate"), row.get("Country"))
    return control_at(auth, decision_date) if auth else None

def resolve(pa_raw, decision_date, easting=None, northing=None, country=None):
    """Return (authority_norm, route, note).

    authority_norm: the council to look up control/land for (None if no local council).
    route: 'Local council' | 'National' | 'Northern Ireland' | 'Outside GB' | 'Unmatched'.
    note: human-readable reason, esp. when there is no assignable party.
    """
    pa = norm(pa_raw)
    pa = ALIAS.get(pa, pa)
    if not pa:
        return None, "Unmatched", "no planning authority named"
    if is_national(pa_raw):
        return None, "National", f"national consenting body ({pa_raw.strip()}) — no local council"
    if pa in OUTSIDE_GB:
        return None, "Outside GB", f"Crown Dependency ({pa_raw.strip()}) — outside Great Britain"
    # reorganised area: pick district (pre-vesting) or unitary (post-vesting) at the decision date
    if pa in REORG:
        vest = REORG[pa][0]
        if decision_date is not None and decision_date.year < vest:
            dist = district_from_coords(easting, northing, pa) if (easting and northing) else None
            if dist:
                return dist, "Local council", ""
            # couldn't place it: fall back to the unitary name, flag the approximation
            return pa, "Local council", ("pre-reorganisation decision; grid reference did not fall in a "
                                         "former district, using successor unitary")
        return pa, "Local council", ""
    if pa in ctrl:
        route = "Northern Ireland" if (country or "").strip() == "Northern Ireland" else "Local council"
        note = ("Northern Ireland council — excluded from the GB land comparison"
                if route == "Northern Ireland" else "")
        return pa, route, note
    # name is not a recognised GB or NI local authority
    if (country or "").strip() == "Northern Ireland":
        return None, "Northern Ireland", f'unrecognised NI authority name ("{pa_raw.strip()}")'
    return None, "Unmatched", f'unrecognised authority name ("{pa_raw.strip()}")'
