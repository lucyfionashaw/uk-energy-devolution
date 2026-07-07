#!/usr/bin/env python3
"""Classify every REPD applicant (Operator field) by OWNERSHIP TYPE:

  public-council   local government: county/borough/city/district councils, combined
                   authorities, national park authorities
  public-nhs       NHS trusts, foundation trusts, health boards, ambulance services
  public-education state schools, academy trusts, colleges, universities
  public-other     other public bodies: MoD, agencies, Scottish Water, fire, police,
                   Network Rail, research bodies (STFC)
  community        community energy proper: co-ops, CICs, community benefit societies,
                   "X Community Energy", development trusts
  charity          charities / non-profits that are NOT community energy: National Trust,
                   wildlife trusts, churches, housing associations
  private          everything else: developers, utilities, supermarkets, farms, and the
                   REPD's own "Private Developer" placeholder
  unknown          blank or "Unknown"

Hard-won pitfalls (encoded below, in match order):
  * "trust" alone means nothing: NHS Foundation Trust -> public-nhs; Academy Trust ->
    education; investment/unit/infrastructure trusts (ABRDN, Octopus) -> private;
    National Trust -> charity; development trusts -> community.
  * "Community Windpower Ltd" is a COMMERCIAL developer despite the name -> private.
  * "Solar Options for Schools Ltd" is a private installer, not a school -> private.
  * "Moto Hospitality" is not a hospital; "Science and Technology Facilities Council"
    is not a local council.
  * Scottish Water is publicly owned; Dwr Cymru is a private not-for-profit -> charity.

Output: data/processed/ownership.json + printed summary.
"""
import re, json, pathlib, sys, collections

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import repd_records as R

OUT = HERE.parent / "data" / "processed" / "ownership.json"

def num(x):
    x = (x or "").strip().replace(",", "")
    try: return float(x)
    except ValueError: return None
has = lambda x: bool((x or "").strip())

# --- named exceptions checked before any keyword rule (lower-cased substring) ---
FORCE_PRIVATE = [
    "community windpower", "community wind power",   # commercial onshore developer
    "solar options for schools",                     # private schools-market installer
    "moto hospitality",
    "abrdn", "octopus renewables infrastructure trust", "unit trust",
    "investment trust", "boreal uk",
]
FORCE_PUBLIC_OTHER = [
    "science and technology facilities council",     # research body, not local gov
]

RULES = [
    # (category, regex) — first match wins
    ("public-nhs", r"\bnhs\b|health board|\bhospitals?\b|ambulance service|\bhscni\b"),
    ("public-education", r"academy trust|academies\b.*\btrust|multi[- ]academy|learning trust|"
                         r"education trust|academy transformation|\buniversity\b|"
                         r"\bcolleges?\b|\bschools?\b(?!.*(ltd|limited|plc))"),
    ("public-council", r"(county|borough|city|district|town|parish|metropolitan)\s+council|"
                       r"\bcouncil\b(?!.*(research|facilities|sports|british))|"
                       r"combined authority|greater london authority|national park"),
    ("public-other", r"ministry of defence|\bmod\b|environment agency|forestry commission|"
                     r"forestry england|forestry and land scotland|natural resources wales|"
                     r"scottish water|network rail|fire and rescue|\bpolice\b|hm prison|"
                     r"\bdefra\b|transport for london|scottish government|welsh government|"
                     r"scottish enterprise|highways england|national highways"),
    ("community", r"community (energy|power|solar|wind|hydro|heat|benefit|interest)|"
                  r"co-?operative|\bco-?op\b|\bcic\b|\bbencom\b|development trust|"
                  r"energy4all|community council|transition (town|community)"),
    ("charity", r"national trust|wildlife trust|\bcharity\b|\bchurch\b|\bdiocese\b|"
                r"parochial|cathedral|housing association|\brspb\b|\bymca\b|salvation army|"
                r"dwr cymru|welsh water|wwf\b"),
]

def classify(op):
    o = (op or "").strip()
    if not o or o.lower() == "unknown":
        return "unknown"
    lo = o.lower()
    for s in FORCE_PRIVATE:
        if s in lo: return "private"
    for s in FORCE_PUBLIC_OTHER:
        if s in lo: return "public-other"
    for cat, pat in RULES:
        if re.search(pat, lo): return cat
    return "private"

GCOL = "Planning Permission  Granted"
GRANT_ST = {"Awaiting Construction", "Under Construction", "Operational",
            "Planning Permission Expired", "Decommissioned"}
OP_ST = {"Operational", "Decommissioned"}

CATS = ["private", "public-council", "public-nhs", "public-education", "public-other",
        "community", "charity", "unknown"]
node = lambda: {"n": 0, "mw": 0.0, "granted": 0, "grantedMW": 0.0, "op": 0, "opMW": 0.0}
agg = {c: node() for c in CATS}
bytech = collections.defaultdict(lambda: collections.Counter())
samples = collections.defaultdict(collections.Counter)

for r in R.live():
    cat = classify(r["Operator (or Applicant)"])
    mw = num(r["Installed Capacity (MWelec)"]) or 0.0
    st = r["Development Status (short)"].strip()
    a = agg[cat]
    a["n"] += 1; a["mw"] += mw
    if has(r[GCOL]) or st in GRANT_ST:
        a["granted"] += 1; a["grantedMW"] += mw
    if has(r["Operational"]) or st in OP_ST:
        a["op"] += 1; a["opMW"] += mw
    bytech[cat][r["Technology Type"].strip()] += 1
    samples[cat][(r["Operator (or Applicant)"] or "").strip()] += 1

out = {"categories": {}, "note": __doc__.strip().split("\n")[0]}
for c in CATS:
    a = agg[c]
    out["categories"][c] = {
        "n": a["n"], "mw": round(a["mw"]), "granted": a["granted"],
        "grantedMW": round(a["grantedMW"]), "op": a["op"], "opMW": round(a["opMW"]),
        "topTech": bytech[c].most_common(3),
        "topOperators": samples[c].most_common(10),
    }
OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")

tot_n = sum(a["n"] for a in agg.values())
print(f"{'category':18s} {'projects':>8s} {'share':>6s} {'MW applied':>10s} {'MW granted':>10s} {'MW op':>8s}")
for c in CATS:
    a = agg[c]
    print(f"{c:18s} {a['n']:8d} {100*a['n']/tot_n:5.1f}% {a['mw']:10,.0f} {a['grantedMW']:10,.0f} {a['opMW']:8,.0f}")
print(f"\nwrote {OUT}")
