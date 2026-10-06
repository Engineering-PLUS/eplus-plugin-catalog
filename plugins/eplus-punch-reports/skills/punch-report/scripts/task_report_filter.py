#!/usr/bin/env python3
"""
task_report_filter.py -- the PlanGrid task-list URL that limits a Task Report
export to this report's pins.

    python3 scripts/task_report_filter.py --project-uid <uid> [--items data/items.json]

PlanGrid's Export button exports whatever the task list shows: "Export (All)"
on the plain list, "Export (Filtered)" once a filter is set. The task list
takes its Date created filter from the URL:

    https://app.plangrid.com/projects/<uid>/issues/?created_after=YYYY-MM-DD&created_before=YYYY-MM-DD

Both dates are inclusive and are the user's local dates, so this script turns
each in-scope pin's created_at (UTC) into the seat's local date (the sandbox
runs in the host's time zone) and prints the URL for the earliest and latest.
Field result 2026-10-06: an unfiltered export of a 94-task project took about
6.5 minutes and 12.4 MB for a 36-item report; filtered to the walk date it
lists exactly those 36.

The window can hold pins outside the report's scope (another walk the same
day); extract_sheet_clips.py cuts clips only for the items in data/items.json,
so extra pages cost time, never correctness. The ID filter takes one number
only, so it cannot express a range.

Prints the URL, the date window and how many in-scope pins it covers. Exits
nonzero when data/items.json is missing or no item carries a created_at.
"""
import argparse
import datetime as dt
import json
import sys


def local_date(stamp):
    s = str(stamp or "").strip()
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            return dt.date.fromisoformat(s[:10])
        except ValueError:
            return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)  # PlanGrid timestamps are UTC
    return t.astimezone().date()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project-uid", required=True)
    ap.add_argument("--items", default="data/items.json")
    a = ap.parse_args()
    try:
        with open(a.items, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: {a.items}: {e}; run the data pass (bash scripts/run_pipeline.sh) first")
    items = items.get("items", items) if isinstance(items, dict) else items
    dates = sorted(d for d in (local_date(i.get("created_at")) for i in items if isinstance(i, dict)) if d)
    if not dates:
        sys.exit("ERROR: no item in data/items.json carries a created_at; export unfiltered (Export (All))")
    lo, hi = dates[0], dates[-1]
    url = (f"https://app.plangrid.com/projects/{a.project_uid}/issues/"
           f"?created_after={lo.isoformat()}&created_before={hi.isoformat()}")
    print(f"filter url   : {url}")
    print(f"date window  : {lo.isoformat()} to {hi.isoformat()} (local, inclusive)")
    print(f"in scope     : {len(items)} items; the export panel must say at least {len(items)} filtered tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
