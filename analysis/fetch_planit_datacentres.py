#!/usr/bin/env python3
"""Fetch UK data-centre planning applications from the PlanIt API.

PlanIt (planit.org.uk) aggregates the planning portals of UK local authorities.
There is no official national dataset of data-centre applications, so this is a
free-text search over application descriptions — inherently noisy, which is why
the raw payload is cached verbatim here and all filtering happens downstream in
build_datacentres.py where it can be audited and adjusted.

Politeness: the API is a free community service and is rate limited. We page at
300 (their default max) with a delay, and cache to disk so re-runs cost nothing.

Run:  py analysis/fetch_planit_datacentres.py [--refresh]
"""
import json, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "planit_datacentres.json"
API = "https://www.planit.org.uk/api/applics/json"
TERMS = ["data centre", "datacentre", "data center", "datacenter"]
# The API docs advise a smaller page size with an incrementing 'page' param
# (NOT an offset), and expose Retry-After on 429. Anonymous limits are strict.
PAGE = 200
DELAY = 20          # seconds between successful requests
BACKOFF = 120       # fallback wait after a 429 if no Retry-After header
MAX_RETRY = 6
UA = "uk-energy-devolution-dashboard/1.0 (research; contact via github.com/lucyfionashaw)"


def get(params):
    """GET honouring Retry-After on 429, and retrying transient network errors."""
    url = API + "?" + urllib.parse.urlencode({**params, "compress": "on"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRY - 1:
                ra = e.headers.get("Retry-After")
                try:
                    wait = int(ra) + 5
                except (TypeError, ValueError):
                    wait = BACKOFF * (attempt + 1)
                print(f"    429 — Retry-After={ra}, waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < MAX_RETRY - 1:
                wait = 30 * (attempt + 1)
                print(f"    network error ({e}); retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("exhausted retries")


def fetch_term(term):
    """Page through a search term using the incrementing 'page' param."""
    out, page, total = [], 1, None
    while True:
        d = get({"search": term, "pg_sz": PAGE, "page": page})
        if total is None:
            total = d.get("total", 0)
            print(f"  '{term}': {total} records", flush=True)
        recs = d.get("records", [])
        if not recs:
            break
        out.extend(recs)
        print(f"    page {page}: {len(out)}/{total}", flush=True)
        if len(out) >= total:
            break
        page += 1
        time.sleep(DELAY)
    return out


CACHE = ROOT / "data" / "raw" / ".planit_cache"


def main():
    if OUT.exists() and "--refresh" not in sys.argv:
        cached = json.loads(OUT.read_text(encoding="utf-8"))
        print(f"cached: {cached['n']} records — use --refresh to re-pull")
        return

    CACHE.mkdir(parents=True, exist_ok=True)
    # Fetch each term, caching its raw result to disk. A crash on a later term
    # never loses an earlier term's pages, and re-runs skip completed terms.
    for t in TERMS:
        cf = CACHE / (re.sub(r"\W+", "_", t) + ".json")
        if cf.exists() and "--refresh" not in sys.argv:
            print(f"  '{t}': cached ({len(json.loads(cf.read_text())['records'])})")
            continue
        recs = fetch_term(t)
        cf.write_text(json.dumps({"term": t, "records": recs}, ensure_ascii=False),
                      encoding="utf-8")
        time.sleep(DELAY)

    # Combine all cached terms, de-duplicating by application id.
    seen, records = set(), []
    for cf in CACHE.glob("*.json"):
        for r in json.loads(cf.read_text(encoding="utf-8"))["records"]:
            key = r.get("name") or r.get("uid")
            if key and key not in seen:
                seen.add(key)
                records.append(r)

    OUT.write_text(json.dumps(
        {"source": "planit.org.uk/api/applics", "terms": TERMS,
         "n": len(records), "records": records}, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(records)} unique records -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
