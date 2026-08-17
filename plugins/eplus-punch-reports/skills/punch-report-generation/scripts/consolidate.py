"""Consolidate a PlanGrid project pull into one per-item record per punch item.

Input  : a PlanGrid rescue folder (tasks.json, task_details/*.json, sheets.json,
         photos.json, photos/)
Output : items.json -- one clean record per live item, plus a triage summary

Written to be robust to the data actually arriving messy, because it always
does: `room` is usually empty, titles are often a meaningless marker string,
descriptions exist on a minority of pins, and some pins are camera misfires.
Nothing here guesses -- it labels what is missing so the report step can
decide what to do about it.

Usage:
  python consolidate.py <rescue_dir> [-o items.json]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# A title that is the same string on every item carries no information (field
# staff use it as a personal marker, e.g. "Jim2"). Detected, not hardcoded.
MEANINGLESS_TITLE_RATIO = 0.8

# Sheet number -> what that drawing covers. Populated from sheets.json; this is
# usually the ONLY structured location signal on the whole pull.
SHEET_HINT_RE = re.compile(r"(?i)\b(site|first|second|third|ground|roof|level\s*\d+)\b")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def live(records):
    return [r for r in records if not r.get("deleted")]


def build(rescue: Path) -> dict:
    tasks = live(load(rescue / "tasks.json"))
    sheets = {s["uid"]: s for s in live(load(rescue / "sheets.json"))}
    photos = {p["uid"]: p for p in live(load(rescue / "photos.json"))}

    titles = Counter((t.get("title") or "").strip() for t in tasks)
    junk_title = ""
    if tasks and titles:
        top, n = titles.most_common(1)[0]
        if top and n / len(tasks) >= MEANINGLESS_TITLE_RATIO:
            junk_title = top

    items = []
    for t in sorted(tasks, key=lambda x: x.get("number") or 0):
        detail = {}
        f = rescue / "task_details" / f"{t['uid']}.json"
        if f.exists():
            detail = json.loads(f.read_text(encoding="utf-8"))

        # --- photos, resolved to files on disk with their capture metadata
        item_photos = []
        for ph in detail.get("photos") or []:
            meta = photos.get(ph.get("uid"), ph)
            title = meta.get("title") or ph.get("uid", "")
            matches = list((rescue / "photos").glob(f"{ph.get('uid','')}*"))
            item_photos.append({
                "uid": ph.get("uid"),
                "file": matches[0].name if matches else None,
                "original_name": title,
                "taken_at": meta.get("created_at"),
                "by": (meta.get("created_by") or {}).get("email"),
            })
        item_photos.sort(key=lambda p: p.get("taken_at") or "")

        ann = t.get("current_annotation") or {}
        sheet = sheets.get((ann.get("sheet") or {}).get("uid"), {})
        sheet_name = sheet.get("name") or ""
        loc_hint = ""
        m = SHEET_HINT_RE.search(sheet.get("description") or sheet_name)
        if m:
            loc_hint = m.group(1)

        desc = (t.get("description") or "").strip()
        title = (t.get("title") or "").strip()
        items.append({
            "number": t.get("number"),
            "uid": t.get("uid"),
            "title": "" if title == junk_title else title,
            "description": desc,
            "has_description": bool(desc),
            "status": t.get("status"),
            "sheet_ref": sheet_name,
            "sheet_location_hint": loc_hint,
            "pin_stamp": ann.get("stamp") or "",
            "room": (t.get("room") or "").strip(),
            "created_at": t.get("created_at"),
            "closed_at": t.get("closed_at"),
            "assignees": [a.get("email") for a in (t.get("assignees") or []) if a.get("email")],
            "photo_count": len(item_photos),
            "photos": item_photos,
            # Triage flags -- consumed by the report step, never guessed past here.
            "needs_description_from_photos": not desc,
            "no_photo_evidence": len(item_photos) == 0,
        })

    summary = {
        "items": len(items),
        "with_description": sum(1 for i in items if i["has_description"]),
        "photo_only": sum(1 for i in items if i["needs_description_from_photos"]),
        "no_photos": sum(1 for i in items if i["no_photo_evidence"]),
        "with_room": sum(1 for i in items if i["room"]),
        "total_photos": sum(i["photo_count"] for i in items),
        "sheets": sorted({i["sheet_ref"] for i in items if i["sheet_ref"]}),
        "statuses": dict(Counter(i["status"] for i in items)),
        "meaningless_title_dropped": junk_title or None,
    }
    return {"summary": summary, "items": items}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rescue_dir")
    ap.add_argument("-o", "--out", default="items.json")
    args = ap.parse_args()

    data = build(Path(args.rescue_dir))
    Path(args.out).write_text(json.dumps(data, indent=1, ensure_ascii=False),
                              encoding="utf-8")
    s = data["summary"]
    print(f"items: {s['items']}  ({s['with_description']} authored, "
          f"{s['photo_only']} photo-only, {s['no_photos']} with NO photo)")
    print(f"photos: {s['total_photos']}   sheets: {', '.join(s['sheets']) or '(none)'}")
    print(f"room field populated on: {s['with_room']}/{s['items']}")
    if s["meaningless_title_dropped"]:
        print(f"dropped uninformative title on every item: "
              f"{s['meaningless_title_dropped']!r}")
    print(f"statuses: {s['statuses']}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
