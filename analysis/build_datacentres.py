#!/usr/bin/env python3
"""Turn the raw PlanIt free-text search into a defensible data-centre dataset.

Why this is more than a groupby: data centres have no planning use class of
their own (usually B8 or sui generis), so the only way to find them is to match
application descriptions. That pulls in three kinds of false positive:

  1. Condition discharges / amendments that merely REFERENCE an existing data
     centre permission. One scheme can generate a dozen of these.
  2. Incidental mentions — a substation or office whose description happens to
     name a neighbouring data centre.
  3. Resubmissions of the same scheme at the same site.

So we keep only substantive application types, drop descriptions that are
clearly about administering a prior consent, and dedupe by site. Every stage
reports how much it removed, and --audit prints samples of what was kept and
dropped so the matching can be hand-checked.

Run:  py analysis/build_datacentres.py [--audit]
"""
import json, pathlib, re, sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "planit_datacentres.json"
OUT = ROOT / "data" / "processed" / "datacentres.json"
SAMPLE = ROOT / "data" / "processed" / "datacentres_sample.csv"

# PlanIt's app_type is unreliable in BOTH directions (it labels condition
# discharges "Full", and leaves genuine new-build applications blank), so we do
# NOT gate on it. All filtering is on the description text instead.

# Descriptions that administer a prior permission rather than propose anything.
ADMIN_RE = re.compile(
    r"^\s*(details? of|discharge of|approval of details|submission of details|"
    r"non[- ]material|variation of|removal of|compliance with|confirmation of|"
    r"screening opinion|scoping opinion|screening request|certificate of)\b"
    r"|\bpursuant to\b|\bcondition[s]? \d+\b|\breserved matters?\b",
    re.I)

# Cross-boundary consultations: a neighbouring council notified of someone else's
# application. Counting these would double-count against the deciding authority.
CONSULT_RE = re.compile(
    r"\b(consultation (from|received|request)|article 16|adjoining (authority|"
    r"borough)|neighbouring authority|notification from)\b", re.I)

# Genuine proposal language.
PROPOSE_RE = re.compile(
    r"\b(erection|construction|construct|demolition|develop|development|"
    r"redevelopment|provision|provide|creation|change of use|installation|new)\b",
    re.I)

DC_RE = re.compile(r"data\s*cent(re|er)s?", re.I)
# Reverse conversions: a data centre being changed to something else (gym, offices).
# These name a data centre but propose removing it — not a data-centre application.
REVERSE_RE = re.compile(
    r"from\s+(a\s+|an\s+|the\s+|former\s+|existing\s+)*data\s*cent\w*\s+to\b", re.I)
# The data centre must be a SUBJECT of the proposal, not merely nearby (e.g. not
# "substation to serve the neighbouring data centre").
DC_SUBJECT_RE = re.compile(
    r"(use (as|for)[^.]{0,40}data\s*cent"
    r"|(a|an|the|two|three|new|proposed|erection of|construction of|provide|"
    r"providing|comprising|redevelopment[^.]{0,40}(to|for))[^.]{0,40}data\s*cent"
    r"|data\s*cent\w*\s+(building|development|facility|campus|use|scheme|park|"
    r"and associated))",
    re.I)


def norm(r):
    of = r.get("other_fields") or {}
    return {
        "authority": (r.get("area_name") or "").strip(),
        "uid": r.get("uid") or r.get("name"),
        "desc": (r.get("description") or "").strip(),
        "address": (r.get("address") or "").strip(),
        "postcode": (r.get("postcode") or "").strip(),
        "type": (r.get("app_type") or "").strip(),
        "state": (r.get("app_state") or "").strip(),
        "size": (r.get("app_size") or "").strip(),
        "start": (r.get("start_date") or "")[:10],
        "decided": (r.get("decided_date") or "")[:10],
        "link": r.get("link") or r.get("url"),
        "lat": r.get("location_y"), "lon": r.get("location_x"),
        "applicant": (of.get("applicant_name") or "").strip(),
    }


def main():
    if not RAW.exists():
        sys.exit(f"missing {RAW} — run analysis/fetch_planit_datacentres.py first")
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    recs = [norm(r) for r in raw["records"]]
    n0 = len(recs)

    # stage 1: must genuinely mention a data centre
    s1 = [r for r in recs if DC_RE.search(r["desc"]) or DC_RE.search(r["address"])]
    # stage 2: drop administration of prior consents (and mis-typed ones)
    s2 = [r for r in s1 if not ADMIN_RE.search(r["desc"])]
    # stage 3: drop cross-boundary consultation notifications
    s3 = [r for r in s2 if not CONSULT_RE.search(r["desc"])]
    # stage 4: require proposal language + data centre as subject, and NOT a
    # reverse conversion (a data centre being changed into something else).
    s4 = [r for r in s3 if PROPOSE_RE.search(r["desc"]) and DC_SUBJECT_RE.search(r["desc"])
          and not REVERSE_RE.search(r["desc"])]
    # stage 5: dedupe by site (authority + postcode/address), keep earliest
    seen, kept = set(), []
    for r in sorted(s4, key=lambda x: x["start"] or "9999"):
        key = (r["authority"].lower(), (r["postcode"] or r["address"][:60]).lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)

    print("filter funnel")
    print(f"  raw records fetched          {n0:>6}")
    print(f"  mentions a data centre       {len(s1):>6}  (-{n0-len(s1)})")
    print(f"  not admin of prior consent   {len(s2):>6}  (-{len(s1)-len(s2)})")
    print(f"  not a cross-boundary consult {len(s3):>6}  (-{len(s2)-len(s3)})")
    print(f"  proposes a data centre       {len(s4):>6}  (-{len(s3)-len(s4)})")
    print(f"  deduped by site              {len(kept):>6}  (-{len(s4)-len(kept)})")

    if "--audit" in sys.argv:
        print("\napp_type distribution (kept — note PlanIt's type is unreliable):")
        for t, c in Counter(r["type"] for r in kept).most_common():
            print(f"    {t or '(blank)':<24} {c}")
        print("\napp_state distribution (kept):")
        for t, c in Counter(r["state"] for r in kept).most_common():
            print(f"    {t or '(blank)':<24} {c}")
        print("\n-- sample KEPT --")
        for r in kept[:6]:
            print(f"  [{r['authority']}] {r['type']}/{r['state']} {r['start']}\n      {r['desc'][:150]}")
        dropped = [r for r in s1 if r not in s4]
        print("\n-- sample DROPPED --")
        for r in dropped[:6]:
            print(f"  [{r['authority']}] {r['type']}/{r['state']}\n      {r['desc'][:150]}")

    by_auth = Counter(r["authority"] for r in kept)
    by_year = Counter(r["start"][:4] for r in kept if r["start"][:4].isdigit())
    by_state = Counter(r["state"] for r in kept)

    OUT.write_text(json.dumps({
        "source": "planit.org.uk free-text search over application descriptions",
        "caveats": [
            "Data centres have no dedicated planning use class, so identification is free-text matching, not an official flag.",
            "PlanIt scrapes council portals and historical depth varies by authority, so absolute counts are not safely comparable across the full time range.",
            "Planning records rarely state IT load, so this counts applications, not megawatts.",
        ],
        "funnel": {"raw": n0, "mentions": len(s1), "notAdmin": len(s2),
                   "substantive": len(s3), "proposes": len(s4), "deduped": len(kept)},
        "nKept": len(kept), "nAuthorities": len(by_auth),
        "byAuthority": [{"authority": a, "n": n} for a, n in by_auth.most_common()],
        "byYear": [{"year": int(y), "n": n} for y, n in sorted(by_year.items())],
        "byState": [{"state": s or "(blank)", "n": n} for s, n in by_state.most_common()],
        "records": kept,
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    import csv
    with SAMPLE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["authority", "type", "state", "start", "decided",
                                          "address", "postcode", "applicant", "desc", "link"])
        w.writeheader()
        for r in kept:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    print(f"\n{len(kept)} applications across {len(by_auth)} authorities")
    print(f"wrote {OUT.name} and {SAMPLE.name}")


if __name__ == "__main__":
    main()
