#!/usr/bin/env python3
"""New planning applications by technology, per year of application, bucketed to cover
EVERY technology in the REPD — and measured in BOTH units:

  * n  : number of applications submitted that year
  * mw : capacity (MWelec) applied for that year

The two tell opposite stories: solar/battery dominate by application count (many small
schemes) while offshore wind dominates by capacity (a few enormous ones). The page
toggles between them.

Buckets:  Solar / OnshoreWind / OffshoreWind / Battery / Hydro / Bioenergy / Other

Output: data/processed/apps_tech.json  ->  window.APPSTECH
Run:    python3 analysis/build_apps_tech.py   (then re-run build_data_js.py)
"""
import csv, json, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "REPD_publication_Q1_2026.csv"
OUT = ROOT / "data" / "processed" / "apps_tech.json"

BUCKET = {
    "Solar Photovoltaics": "Solar",
    "Wind Onshore": "OnshoreWind",
    "Wind Offshore": "OffshoreWind",
    "Battery": "Battery",
    "Small Hydro": "Hydro", "Large Hydro": "Hydro",
    "Pumped Storage Hydroelectricity": "Hydro",
    "Anaerobic Digestion": "Bioenergy", "Landfill Gas": "Bioenergy",
    "Biomass (dedicated)": "Bioenergy", "Biomass (co-firing)": "Bioenergy",
    "EfW Incineration": "Bioenergy", "Advanced Conversion Technologies": "Bioenergy",
    "Sewage Sludge Digestion": "Bioenergy",
}
# everything else (Tidal, Wave, Hydrogen, Geothermal, Fuel Cell, CAES, LAES, Flywheel...) -> Other
ORDER = ["Solar", "OnshoreWind", "OffshoreWind", "Battery", "Hydro", "Bioenergy", "Other"]
Y0, Y1 = 2008, 2026

def num(x):
    x = (x or "").strip().replace(",", "")
    try: return float(x)
    except ValueError: return None

def sub_year(s):
    s = (s or "").strip()
    try:
        return int(s.split("/")[2])
    except (IndexError, ValueError):
        return None

n_ct = defaultdict(lambda: defaultdict(int))     # n_ct[year][bucket]
mw_ct = defaultdict(lambda: defaultdict(float))  # mw_ct[year][bucket]
for r in csv.DictReader(open(RAW, encoding="latin-1")):
    y = sub_year(r["Planning Application Submitted"])
    if y is None or y < Y0 or y > Y1:
        continue
    b = BUCKET.get(r["Technology Type"].strip(), "Other")
    n_ct[y][b] += 1
    mw_ct[y][b] += num(r["Installed Capacity (MWelec)"]) or 0.0

years = list(range(Y0, Y1 + 1))
series = {b: {"n": [n_ct[y].get(b, 0) for y in years],
              "mw": [round(mw_ct[y].get(b, 0.0)) for y in years]}
          for b in ORDER}

OUT.write_text(json.dumps({"years": years, "order": ORDER, "series": series},
                          separators=(",", ":")), encoding="utf-8")

print("apps_tech.json written.")
tot_n = {b: sum(series[b]["n"]) for b in ORDER}
tot_mw = {b: sum(series[b]["mw"]) for b in ORDER}
print("  by applications:", tot_n)
print("  by capacity MW :", tot_mw)
