#!/usr/bin/env python3
"""
blank_template.py -- the data for an empty, fill-in punch report.

For a user who asked for an empty report instead of one built from PlanGrid
(run order, section 1, "No match"): N blank item pages the engineer fills in by
hand in Word, each with an empty Drawing Sheet and Date Recorded, an empty
Item Description and Corrective Action, and one empty photo row to paste into.

Writes data/items.json and data/drafted_items.json. The rest is the normal
render path, from _pipeline/:

    python3 scripts/blank_template.py [--pages 3]
    python3 scripts/prefill_config.py --project-name "<what the user typed>" --version <next>
    RENDER_ONLY=1 bash scripts/run_pipeline.sh
    python3 scripts/package.py <workspace> "<deliver to>" --template-only

build_master.py keeps blank items blank (no title, no N/A, no voice check), and
package.py --template-only delivers the body and the cover only.
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3, help="blank item pages (default 3)")
    ap.add_argument("--data", default="data", help="data folder (default data/)")
    args = ap.parse_args()
    if args.pages < 1:
        sys.exit("ERROR: --pages must be at least 1.")

    os.makedirs(args.data, exist_ok=True)
    items = [{"number": n, "title": "", "photos": [], "sheet_name": "", "sheet_description": "",
              "room": "", "status": "", "created_at": None} for n in range(1, args.pages + 1)]
    drafted = {"items": [{"number": n, "blank": True} for n in range(1, args.pages + 1)]}
    for name, doc in (("items.json", items), ("drafted_items.json", drafted)):
        with open(os.path.join(args.data, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
    print(f"blank template: {args.pages} empty item page(s) -> {args.data}/items.json, {args.data}/drafted_items.json")


if __name__ == "__main__":
    main()
