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
    tasks.json                the get_tasks packet fetched by pull_mcp.sh ({"coverage","tasks"}),
                              or a bare list of rows (pull_tasks / get_task per item).
                              Rows from MCP 0.7+ carry `description`, `sheet`
                              {uid,name,description} and `photos` inline.
    mcp_photo_urls.json       optional when photos are inline; {"<number>": [{"uid",
                              "title","created_at","url"|"download_url"|"source_url"}]}
    photos/                   originals downloaded by fetch_photos.py (preferred)
    pdf_photos/               fallback crops from extract_pdf_photos.py
    sheets.json               optional: the list_sheets packet (pull_mcp.sh), or an
                              exported pull's [{"uid","name","description"}]
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
import re
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


def normalize(sheet):
    """Sheet number as a lookup key: upper-case, trimmed, PlanGrid's OCR letter-O
    after a leading T read as a zero (TO2-01A -> T02-01A), matching build_master."""
    s = str(sheet or "").strip().upper()
    return re.sub(r"^T[O0]", "T0", s)


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
    if not photo_meta:
        # get_tasks (MCP 0.7+) carries each task's photos inline
        for t in tasks:
            if isinstance(t.get("photos"), list) and t.get("number") is not None:
                photo_meta[str(as_int(t["number"]))] = [p for p in t["photos"] if isinstance(p, dict) and p.get("uid")]
    by_item = load(os.path.join(pull, "sheets.json.by_item.json"), {})
    mcp_sheets = load(os.path.join(pull, "sheets.json"), [])
    if isinstance(mcp_sheets, dict):
        mcp_sheets = mcp_sheets.get("sheets", [])   # list_sheets packet shape

    # --- sheets, best source first --------------------------------------------
    #   1. the resolved `sheet` object on each task row (get_tasks / pull_tasks, MCP 0.7+)
    #   2. sheets.json: a list_sheets result or an exported pull's sheet list
    #   3. sheet numbers recovered from the Task Report PDF (no titles)
    sheet_uid_to_name, sheet_uid_to_desc = {}, {}
    for t in tasks:
        s = t.get("sheet")
        if isinstance(s, dict) and s.get("uid") and s.get("name"):
            sheet_uid_to_name.setdefault(s["uid"], s["name"])
            if s.get("description"):
                sheet_uid_to_desc.setdefault(s["uid"], s["description"])
    for s in mcp_sheets if isinstance(mcp_sheets, list) else []:
        if s.get("uid") and s.get("name"):
            sheet_uid_to_name.setdefault(s["uid"], s["name"])
            if s.get("description"):
                sheet_uid_to_desc.setdefault(s["uid"], s["description"])
    for t in tasks:
        name = by_item.get(str(as_int(t.get("number"))))
        if name and t.get("sheet_uid"):
            sheet_uid_to_name.setdefault(t["sheet_uid"], name)

    # Sheet TITLES ("TECHNOLOGY SITE PLAN") are not in the Task Report PDF text
    # and, as of 2026-09-10, the MCP pull returns an empty sheet list, so the
    # report shows the number alone (field result: a reviewer noticed the title
    # was present on an export-folder run and missing on an MCP run). Until the
    # server returns sheets, titles come from a per-project map: <pull>/
    # sheet_titles.json or the client profile's "sheet_titles", {number: title}.
    titles = {}
    for cand in (os.path.join(pull, "sheet_titles.json"),
                 os.path.join(os.path.dirname(dest), "client-profile.json")):
        data = load(cand, {})
        m = data.get("sheet_titles", data) if isinstance(data, dict) else {}
        if isinstance(m, dict):
            titles.update({normalize(k): v for k, v in m.items() if isinstance(v, str) and v.strip()})
    for uid, name in sheet_uid_to_name.items():
        if uid not in sheet_uid_to_desc and normalize(name) in titles:
            sheet_uid_to_desc[uid] = titles[normalize(name)]
    sheets_out = [{"uid": uid, "name": name, "description": sheet_uid_to_desc.get(uid, "")}
                  for uid, name in sheet_uid_to_name.items()]
    with open(os.path.join(dest, "sheets.json"), "w", encoding="utf-8") as f:
        json.dump(sheets_out, f, indent=1)
    untitled = sorted(s["name"] for s in sheets_out if not s["description"])

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
    src = ("task rows" if any(isinstance(t.get("sheet"), dict) and t["sheet"].get("name") for t in tasks)
           else "sheet list" if mcp_sheets else "PDF")
    print(f"sheets       : {len(sheets_out)} named ({src} source)"
          + ("" if sheets_out else "  <- no sheet names; items will show no sheet ref"))
    if untitled:
        print(f"sheet titles : MISSING for {untitled}. The MCP pull carries no sheet list and the Task "
              f"Report prints only the number, so the report will show the number alone. Add "
              f"{{\"<number>\": \"<title>\"}} to the client profile's sheet_titles (or {os.path.basename(pull)}/sheet_titles.json) "
              f"and re-run adapt, or tell the user the titles are missing.")
    else:
        print(f"sheet titles : all {len(sheets_out)} sheets titled")
    print(f"photos       : {from_live} live originals, {from_pdf} from the Task Report PDF")
    if missing:
        print(f"MISSING      : {missing}  (neither photos/ nor pdf_photos/ has them)")
    route = "live" if from_live and not from_pdf else ("pdf" if from_pdf and not from_live else "mixed")
    if not from_live and not from_pdf:
        route = "none"
    with open(os.path.join(dest, "photo_route.json"), "w", encoding="utf-8") as f:
        json.dump({"route": route, "live": from_live, "pdf": from_pdf, "missing": missing}, f, indent=1)
    print(f"photo route  : {route}  (recorded in {dest}/photo_route.json for run_record.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
