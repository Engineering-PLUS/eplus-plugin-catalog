#!/usr/bin/env python3
"""
task_report_filter.py -- the PlanGrid task-list URL that limits a Task Report
export to this report's pins.

    python3 scripts/task_report_filter.py --project-uid <uid> [--items data/items.json]

PlanGrid's Export button exports whatever the task list shows: "Export (All)"
on the plain list, "Export (Filtered)" once a filter is set. The task list
takes its Date created filter from the URL:

    https://app.plangrid.com/projects/<uid>/issues/?created_after=YYYY-MM-DD&created_before=YYYY-MM-DD

Both dates are inclusive, and they are the date part of each pin's created_at
exactly as PlanGrid gives it: PlanGrid's own filter and its "Created ... on"
line use that date. Field result 2026-10-06, Project Miner Warehouse: a pin
created "2026-10-06T00:36" is "Created on Oct 6" in PlanGrid and is not in a
10/05 filter, so converting the stamp from UTC to local time (as 0.9.9 did)
moves it to the wrong day. prefill_config.py dates the cover the same way.
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


def pin_date(stamp):
    """The date part of created_at, as PlanGrid itself dates the pin."""
    try:
        return dt.date.fromisoformat(str(stamp or "").strip()[:10])
    except ValueError:
        return None


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
    dates = sorted(d for d in (pin_date(i.get("created_at")) for i in items if isinstance(i, dict)) if d)
    if not dates:
        sys.exit("ERROR: no item in data/items.json carries a created_at; export unfiltered (Export (All))")
    lo, hi = dates[0], dates[-1]
    url = (f"https://app.plangrid.com/projects/{a.project_uid}/issues/"
           f"?created_after={lo.isoformat()}&created_before={hi.isoformat()}")
    print(f"filter url   : {url}")
    print(f"date window  : {lo.isoformat()} to {hi.isoformat()} (PlanGrid's pin dates, inclusive)")
    print(f"in scope     : {len(items)} items; the export panel must say at least {len(items)} filtered tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
