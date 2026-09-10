#!/usr/bin/env python3
"""
adapt_mcp_pull.py -- turn raw plangrid MCP material into the pull layout that
consolidate.py and run_pipeline.sh expect.

The plangrid MCP's pull_tasks/get_task tools return FLAT task rows, and every
value as a string ("deleted": "False", "number": "41", "photos_count": "1").
consolidate.py reads the older PlanGrid export shape:

    number: int, deleted: bool
    current_annotation: {"stamp": ..., "sheet": {"uid": ...}}
    photos: {"total_count": int}
    created_by: {"email": ...}
    <pull>/sheets.json          [{"uid", "name", "description"}]
    <pull>/task_details/<task_uid>.json   {"task_uid", "photos": [{"uid", "title", "created_by"}]}
    <pull>/photos/<uid>__<title>.jpg

Input folder (default ../plangrid_mcp, i.e. beside _pipeline/):
    tasks.json                raw MCP rows (pull_tasks, or get_task per item)
    mcp_photo_urls.json       {"<number>": [{"uid","title","created_at","url"}, ...]}
    photos/                   originals downloaded by fetch_photos.py (preferred)
    pdf_photos/               fallback crops from extract_pdf_photos.py
    sheets.json               optional, if the MCP returned sheet names
    sheets.json.by_item.json  optional, {"<number>": "<sheet name>"} from extract_pdf_photos.py

Output folder (default ../plangrid_pull, beside _pipeline/, which is where
run_pipeline.sh auto-detects the pull). The raw MCP folder is left untouched.

Photo source per photo: photos/ first, pdf_photos/ second. The summary line
"photo route" says which was used; copy that into PROCESS-LOG.md.

    python3 scripts/adapt_mcp_pull.py                       # ../plangrid_mcp -> ../plangrid_pull
    python3 scripts/adapt_mcp_pull.py --pull X --dest Y
"""
import argparse
import json
import os
import shutil
import sys

BOOL_FIELDS = ("deleted", "archived", "published")
INT_FIELDS = ("number", "photos_count", "comments_count")


def as_bool(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


def as_int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def load(path, default):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pull", default="../plangrid_mcp", help="raw MCP material")
    ap.add_argument("--dest", default="../plangrid_pull", help="pull in consolidate.py shape")
    args = ap.parse_args()

    pull = os.path.abspath(args.pull)
    dest = os.path.abspath(args.dest)
    if os.path.abspath(dest) == os.path.abspath(pull):
        sys.exit("ERROR: --dest must differ from --pull")
    if not os.path.isfile(os.path.join(pull, "tasks.json")):
        sys.exit(f"ERROR: {pull}/tasks.json not found")

    os.makedirs(os.path.join(dest, "task_details"), exist_ok=True)
    os.makedirs(os.path.join(dest, "photos"), exist_ok=True)

    tasks = load(os.path.join(pull, "tasks.json"), [])
    if isinstance(tasks, dict) and "tasks" in tasks:
        tasks = tasks["tasks"]
    photo_meta = load(os.path.join(pull, "mcp_photo_urls.json"), {})
    by_item = load(os.path.join(pull, "sheets.json.by_item.json"), {})
    mcp_sheets = load(os.path.join(pull, "sheets.json"), [])

    # --- sheets: MCP names if present, else names recovered from the PDF ----
    sheet_uid_to_name = {}
    for s in mcp_sheets if isinstance(mcp_sheets, list) else []:
        if s.get("uid") and s.get("name"):
            sheet_uid_to_name[s["uid"]] = s["name"]
    for t in tasks:
        name = by_item.get(str(as_int(t.get("number"))))
        if name and t.get("sheet_uid"):
            sheet_uid_to_name.setdefault(t["sheet_uid"], name)
    sheets_out = [{"uid": uid, "name": name, "description": ""}
                  for uid, name in sheet_uid_to_name.items()]
    with open(os.path.join(dest, "sheets.json"), "w", encoding="utf-8") as f:
        json.dump(sheets_out, f, indent=1)

    # --- tasks and photos ---------------------------------------------------
    nested = []
    from_live = from_pdf = 0
    missing = []
    for t in tasks:
        nt = dict(t)
        for k in INT_FIELDS:
            if k in nt:
                nt[k] = as_int(nt[k])
        for k in BOOL_FIELDS:
            if k in nt:
                nt[k] = as_bool(nt[k])
        num = nt.get("number")
        nt["current_annotation"] = {"stamp": t.get("stamp"), "sheet": {"uid": t.get("sheet_uid")}}
        nt["photos"] = {"total_count": nt.get("photos_count", 0)}
        email = t.get("created_by")
        if isinstance(email, str):
            nt["created_by"] = {"email": email}
        nested.append(nt)

        photos = photo_meta.get(str(num), [])
        detail = {"task_uid": t["uid"], "photos": [
            {"uid": p["uid"], "title": p.get("title"),
             "created_by": {"email": email if isinstance(email, str) else None}}
            for p in photos]}
        with open(os.path.join(dest, "task_details", f"{t['uid']}.json"), "w", encoding="utf-8") as f:
            json.dump(detail, f, indent=1)

        for p in photos:
            fname = f"{p['uid']}__{p.get('title') or p['uid']}.jpg"
            live = os.path.join(pull, "photos", fname)
            pdf = os.path.join(pull, "pdf_photos", fname)
            out = os.path.join(dest, "photos", fname)
            if os.path.isfile(live) and os.path.getsize(live) > 0:
                shutil.copyfile(live, out)
                from_live += 1
            elif os.path.isfile(pdf):
                shutil.copyfile(pdf, out)
                from_pdf += 1
            else:
                missing.append((num, p["uid"]))

    with open(os.path.join(dest, "tasks.json"), "w", encoding="utf-8") as f:
        json.dump(nested, f, indent=1)

    print(f"tasks        : {len(nested)} -> {dest}/tasks.json")
    print(f"sheets       : {len(sheets_out)} named "
          f"({'MCP' if mcp_sheets else 'PDF'} source)"
          + ("" if sheets_out else "  <- no sheet names; items will show no sheet ref"))
    print(f"photos       : {from_live} live originals, {from_pdf} from the Task Report PDF")
    if missing:
        print(f"MISSING      : {missing}  (neither photos/ nor pdf_photos/ has them)")
    route = "live" if from_live and not from_pdf else ("pdf" if from_pdf and not from_live else "mixed")
    print(f"photo route  : {route}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
