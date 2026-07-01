#!/usr/bin/env python3
"""Build two artefacts from the raw REPD extract:

  data/processed/map_points.json  — one lightweight record per project with a
                                    grid reference, converted OSGB36 -> WGS84 so
                                    it can be dropped straight onto a Leaflet map.
  data/processed/flow_data.json   — the planning funnel / Sankey quantities in
                                    BOTH units (project count and MW), so the
                                    overview page can toggle the scale.

Run:  python3 analysis/build_map_flow.py   (then re-run build_data_js.py)
"""
import csv, json, pathlib
from pyproj import Transformer

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "REPD_publication_Q1_2026.csv"
PROC = ROOT / "data" / "processed"

rows = list(csv.DictReader(open(RAW, encoding="latin-1")))

def has(x):
    return bool((x or "").strip())

def num(x):
    x = (x or "").strip().replace(",", "")
    try:
        return float(x)
    except ValueError:
        return None

S = lambda r: r["Development Status (short)"].strip()
GCOL, UCOL, OCOL = "Planning Permission  Granted", "Under Construction", "Operational"
GRANT_ST = {"Awaiting Construction", "Under Construction", "Operational",
            "Planning Permission Expired", "Decommissioned"}
BUILT_ST = {"Under Construction", "Operational", "Decommissioned"}
OP_ST = {"Operational", "Decommissioned"}
REF = {"Application Refused", "Appeal Refused", "Secretary of State Refusal"}
WDR = {"Application Withdrawn", "Appeal Withdrawn"}
PEND = {"Application Submitted", "Appeal Lodged"}

granted = lambda r: has(r[GCOL]) or S(r) in GRANT_ST
built = lambda r: has(r[UCOL]) or S(r) in BUILT_ST
oper = lambda r: has(r[OCOL]) or S(r) in OP_ST

# ---- technology buckets (match charts.js colour keys) ------------------------
def tech_bucket(t):
    t = (t or "").strip()
    if t == "Solar Photovoltaics":
        return "Solar"
    if t == "Wind Onshore":
        return "OnshoreWind"
    if t == "Wind Offshore":
        return "OffshoreWind"
    if t == "Battery":
        return "Battery"
    return "Other"

# ---- map-friendly status buckets --------------------------------------------
def status_bucket(r):
    if S(r) in PEND:
        return "Pending"
    if S(r) in REF:
        return "Refused"
    if oper(r):
        return "Operational"
    if S(r) == "Under Construction":
        return "Construction"
    if granted(r):
        return "Approved"
    return "Other"

# =============================================================================
# 1. MAP POINTS  (OSGB36 easting/northing -> WGS84 lat/lon)
# =============================================================================
# EPSG:27700 = British National Grid; EPSG:4326 = WGS84 lat/lon.
tf = Transformer.from_crs(27700, 4326, always_xy=True)
points = []
for r in rows:
    x, y = num(r["X-coordinate"]), num(r["Y-coordinate"])
    if x is None or y is None:
        continue
    lon, lat = tf.transform(x, y)
    if not (49 < lat < 61 and -9 < lon < 3):   # drop obvious junk coords
        continue
    mw = num(r["Installed Capacity (MWelec)"]) or 0
    points.append([
        round(lat, 4), round(lon, 4),
        tech_bucket(r["Technology Type"]),
        status_bucket(r),
        round(mw, 1),
        (r["Site Name"] or "").strip()[:60],
        (r["Planning Authority"] or "").strip()[:40],
    ])

map_out = {
    "fields": ["lat", "lon", "tech", "status", "mw", "site", "authority"],
    "points": points,
}
(PROC / "map_points.json").write_text(json.dumps(map_out, separators=(",", ":")), encoding="utf-8")
print(f"map_points.json: {len(points):,} points")

# =============================================================================
# 2. FLOW DATA  (project count + MW, so the Sankey/funnel can switch units)
# =============================================================================
def agg(pred):
    n = cap = 0
    for r in rows:
        if pred(r):
            n += 1
            cap += num(r["Installed Capacity (MWelec)"]) or 0
    return n, cap

metrics = {
    "applied": lambda r: True,
    "granted": granted,
    "refused": lambda r: S(r) in REF,
    "withdrawn": lambda r: S(r) in WDR,
    "abandoned": lambda r: S(r) == "Abandoned",
    "pending": lambda r: S(r) in PEND,
    "expired": lambda r: S(r) == "Planning Permission Expired",
    "built": built,
    "op": oper,
}
raw = {k: agg(p) for k, p in metrics.items()}

def pack(idx):
    q = {k: round(v[idx]) for k, v in raw.items()}
    # derived flow segments
    q["otherOut"] = q["applied"] - q["granted"] - q["refused"] - q["pending"]
    q["permitted"] = q["granted"] - q["built"] - q["expired"]
    q["building"] = q["built"] - q["op"]
    q["decided"] = q["granted"] + q["refused"]
    return q

flow_out = {"n": pack(0), "mw": pack(1)}
(PROC / "flow_data.json").write_text(json.dumps(flow_out, separators=(",", ":")), encoding="utf-8")
print("flow_data.json:")
print("  projects:", flow_out["n"])
print("  MW      :", flow_out["mw"])
