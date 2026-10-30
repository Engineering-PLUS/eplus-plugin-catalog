#!/usr/bin/env python3
"""
notes_to_items.py -- the data for a report built from notes and photos, no PlanGrid.

For a walk that was never put into PlanGrid: the engineer has site photos and
notes (a Word or text file, or typed in chat). The model reads the notes and
the photos and writes ONE file, data/notes_items.json, with an entry per item:

    {"items": [
      {"title": "Missing Cable Labels",
       "location": "IDF-POR03C, cabinet 1:6",          optional
       "date": "2026-10-22",                            optional, the walk date
       "description": "Horizontal cabling is missing barrel labels at both ends.",
       "corrective_action": "Contractor to provide matching labels on both ends.",
       "photos": ["IMG_0412.jpg", "IMG_0413.jpg"],      file names in --photos
       "editor_note": "..."}                            optional, internal
    ]}

Then, from _pipeline/:

    python3 scripts/notes_to_items.py data/notes_items.json --photos "<folder with the photos>"
    python3 scripts/prefill_config.py --project-name "<project as the user named it>" --version <next>
    RENDER_ONLY=1 bash scripts/run_pipeline.sh

It writes data/items.json and data/drafted_items.json (numbered 1..N in the
file's order), copies each photo into ../notes_photos/ so the package carries
it, normalises the photos (scripts/normalize_photos.py), and sets
"sheet_clips": false in build/report.config.json: the item pages carry
Location and Date Recorded, with no drawing-sheet clip column.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys


def slug(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "photo"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("notes", help="data/notes_items.json")
    ap.add_argument("--photos", default="..", help="folder the photo names are relative to")
    ap.add_argument("--pipeline", default=".")
    args = ap.parse_args()

    pipe = os.path.abspath(args.pipeline)
    ws = os.path.dirname(pipe)
    with open(args.notes, encoding="utf-8") as f:
        doc = json.load(f)
    entries = doc.get("items", doc) if isinstance(doc, dict) else doc
    if not entries:
        sys.exit("ERROR: no items in " + args.notes)

    dest = os.path.join(ws, "notes_photos")
    os.makedirs(dest, exist_ok=True)
    items, drafted, missing = [], [], []
    for n, e in enumerate(entries, 1):
        for key in ("title", "description"):
            if not str(e.get(key) or "").strip():
                sys.exit(f"ERROR: item {n} has no {key}")
        photos = []
        for k, name in enumerate(e.get("photos") or [], 1):
            src = name if os.path.isabs(name) else os.path.join(args.photos, name)
            if not os.path.isfile(src):
                missing.append(f"item {n}: {name}")
                continue
            uid = f"note-{n}-{k}"
            target = os.path.join(dest, f"{uid}__{slug(os.path.basename(name))}")
            shutil.copyfile(src, target)
            photos.append({"uid": uid, "title": os.path.splitext(os.path.basename(name))[0],
                           "path": target, "captured": None, "photographer": None})
        day = str(e.get("date") or "").strip()
        if day and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            sys.exit(f"ERROR: item {n} date {day!r} is not YYYY-MM-DD")
        items.append({
            "number": n, "uid": f"note-{n}", "title": e["title"].strip(),
            "description": e["description"].strip(), "status": "open",
            "room": str(e.get("location") or "").strip(),
            "sheet_name": "", "sheet_description": "", "pin_stamp": None,
            "photo_count_field": len(photos), "photos": photos,
            "created_at": f"{day}T00:00:00" if day else None, "updated_at": None,
            "created_by": None, "deleted_in_plangrid": False,
        })
        d = {"number": n, "title": e["title"].strip(), "description": e["description"].strip(),
             "corrective_action": str(e.get("corrective_action") or "").strip(),
             "origin": "authored", "confidence": "high", "field_note": e["description"].strip()}
        if e.get("editor_note"):
            d["editor_note"] = str(e["editor_note"]).strip()
        if not photos:
            d["photo_mode"] = "own_photos"  # an empty paste row for a photo added in Word
        drafted.append(d)
    if missing:
        sys.exit("ERROR: photo(s) not found under " + os.path.abspath(args.photos) + ":\n  " + "\n  ".join(missing))

    data = os.path.join(pipe, "data")
    os.makedirs(data, exist_ok=True)
    with open(os.path.join(data, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    with open(os.path.join(data, "drafted_items.json"), "w", encoding="utf-8") as f:
        json.dump({"items": drafted}, f, indent=2)

    cfg_path = os.path.join(pipe, "build", "report.config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["sheet_clips"] = False
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    n_photos = sum(len(i["photos"]) for i in items)
    print(f"notes        : {len(items)} item(s), {n_photos} photo(s) -> data/items.json, data/drafted_items.json")
    if n_photos:
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "normalize_photos.py"),
                            "--items", os.path.join(data, "items.json"),
                            "--dest", os.path.join(pipe, "build", "thumbs_uniform"),
                            "--dims-out", os.path.join(data, "thumb_dims.json")],
                           cwd=pipe, capture_output=True, text=True)
        print((r.stdout or "").strip())
        if r.returncode:
            sys.exit("ERROR: normalize_photos.py failed:\n" + (r.stderr or "")[-2000:])
    print("sheet clips  : off (no PlanGrid drawing; item pages show Location and Date Recorded)")
    print("next         : prefill_config.py, then RENDER_ONLY=1 bash scripts/run_pipeline.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
