"""Shared REPD record loader with de-duplication of resubmitted applications.

REPD lists a resubmitted ("Revised") application as its own row, linked to the one it
replaced via `Are they re-applying (New REPD Ref)` (old->new) and the reverse
`Are they re-applying (Old REPD Ref)` (new->old). So the same physical project can appear
several times. Counting every row double-counts capacity and mislabels the superseded
copies (they land in "approved" or "withdrawn" when they were really just resubmitted).

This module exposes:
  load()                 -> list of all rows (each dict gets helper keys below)
  is_superseded(row)     -> True if a NEWER record replaces this one (i.e. a dup to drop)
  original_submission(r) -> earliest application date across the resubmission chain
                            (so "time to approve" reflects the true start, not the last
                             resubmission), as a datetime.date or None

Each row also gets:
  row["_sub"]   parsed Planning Application Submitted date (or None)
  row["_origsub"] earliest submission across its resubmission chain (or _sub)
  row["_superseded"] bool
"""
import csv, datetime, pathlib

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw" / "REPD_publication_Q1_2026.csv"
REF, NEW, OLD = "Ref ID", "Are they re-applying (New REPD Ref)", "Are they re-applying (Old REPD Ref) "
SUB = "Planning Application Submitted"

def _pdate(s):
    s = (s or "").strip()
    try:
        d, m, y = s.split("/")
        return datetime.date(int(y), int(m), int(d))
    except (ValueError, IndexError):
        return None

def _clean(x):
    return (x or "").strip()

_rows = None
_byref = None

def load():
    global _rows, _byref
    if _rows is not None:
        return _rows
    rows = list(csv.DictReader(open(RAW, encoding="latin-1")))
    byref = {}
    for r in rows:
        rid = _clean(r[REF])
        if rid:
            byref[rid] = r
    # a row is superseded if its NEW-ref points to a record we actually hold
    for r in rows:
        newref = _clean(r[NEW])
        r["_superseded"] = bool(newref and newref in byref)
        r["_sub"] = _pdate(r[SUB])
    # walk each row's OLD-ref chain back to the earliest submission date
    for r in rows:
        seen = set()
        cur, earliest = r, r["_sub"]
        while True:
            oldref = _clean(cur[OLD])
            if not oldref or oldref in seen or oldref not in byref:
                break
            seen.add(oldref)
            cur = byref[oldref]
            d = _pdate(cur[SUB])
            if d and (earliest is None or d < earliest):
                earliest = d
        r["_origsub"] = earliest
    _rows, _byref = rows, byref
    return rows

def live():
    """All rows except superseded duplicates (one row per physical project)."""
    return [r for r in load() if not r["_superseded"]]

def is_superseded(row):
    return row["_superseded"]

def original_submission(row):
    return row.get("_origsub") or row.get("_sub")
