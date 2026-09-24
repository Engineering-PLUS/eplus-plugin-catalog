#!/usr/bin/env python3
"""
consolidate.py, generalized PlanGrid pull consolidator.

Replaces an earlier script that hardcoded a single export directory. Two pull
shapes it handles, both of which quietly corrupt a report if missed:

  1. Delta folders. A pull may contain one or MORE `delta_<from>_to_<to>/`
     folders, each holding the tasks touched in that window plus only the NEW
     photo binaries. A later delta is NOT a superset of an earlier one. The
     base and every delta are layered oldest first, tasks keyed by uid so a
     later revision replaces an earlier one, and photos are indexed across
     every layer's photos/ directory.
  2. Sheet resolution lives in the base. A delta's sheets.json is usually an
     empty array, so sheet names are resolved from the union, base included.

Usage:
    python3 consolidate.py <project_root> -o data/items.json [--only 11-30]

`--only` accepts ranges and comma lists ("11-30", "2,5,9-12") and scopes the
output to those PlanGrid issue numbers.

Deleted and archived pins are dropped unless `--keep-deleted` is given, in
which case they are kept and every item carries `deleted_in_plangrid`
(true/false). That flag is an intake decision (keep the PlanGrid numbering
intact, show the pin as deleted): the renderer prints a red DELETED IN
PLANGRID banner on such items and the TOC marks them. Field result
2026-09-14: without this flag two workers hand-typed the deleted pins back
into items.json, which is exactly the retyping the pipeline exists to prevent.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_only(spec):
    if not spec:
        return None
    keep = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            keep.update(range(int(lo), int(hi) + 1))
        else:
            keep.add(int(chunk))
    return keep


def find_deltas(root):
    """
    Every delta folder, oldest first.

    A pull can carry MORE THAN ONE delta. One project pull had
    delta_<d1>_to_<d2> (30 tasks) and delta_<d3>_to_<d4> (8 tasks). The later
    one is NOT a superset: it holds only that window's tasks. Taking the newest
    delta alone dropped items 12-30 and every photo belonging to them, with no
    error.

    Sort by the window start date parsed out of the folder name rather than
    lexically, so the merge order is chronological whatever the naming.
    """
    hits = glob.glob(os.path.join(root, "delta_*_to_*"))
    hits = [h for h in hits if os.path.isdir(h)]

    def key(path):
        m = re.search(r"delta_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})",
                      os.path.basename(path))
        return (m.group(1), m.group(2)) if m else ("", os.path.basename(path))

    return sorted(hits, key=key)


def index_photo_files(dirs):
    """uid -> absolute path, across every photo directory in the pull."""
    index = {}
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.jpg")):
            uid = os.path.basename(p).split("__")[0]
            index[uid] = p
    return index


def detect_filler_title(tasks):
    """
    Field staff reuse a marker string as the title on nearly every pin
    (a personal initials-plus-digit marker on one job, "General" on another).
    It is a personal bookmark, not content.
    Returns the title to treat as empty, or None.
    """
    titles = [(t.get("title") or "").strip() for t in tasks]
    titles = [t for t in titles if t]
    if not titles:
        return None
    title, count = Counter(titles).most_common(1)[0]
    return title if count >= max(3, 0.5 * len(titles)) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_root")
    ap.add_argument("-o", "--out", default="data/items.json")
    ap.add_argument("--only", default=None, help='e.g. "11-30" or "2,5,9-12"')
    ap.add_argument("--drop-phrase", action="append", default=[],
                    help="drop items whose whole description equals this phrase (case-insensitive, "
                         "repeatable). Near misses are reported, never dropped.")
    ap.add_argument("--title", default=None,
                    help="keep only items whose title equals this (case-insensitive), e.g. the walk marker")
    ap.add_argument("--created-after", default=None,
                    help="keep only items created after this date, YYYY-MM-DD (exclusive)")
    ap.add_argument("--keep-deleted", action="store_true",
                    help="keep deleted/archived pins, marked deleted_in_plangrid, so the item "
                         "numbering matches PlanGrid (run_pipeline.sh always passes it; build_master.py applies deleted_pins)")
    args = ap.parse_args()

    root = os.path.abspath(args.project_root)
    deltas = find_deltas(root)
    keep = parse_only(args.only)
    drop_phrases = [p.strip().lower() for p in args.drop_phrase if p.strip()]
    # A near miss is a description that shares the first two words of a drop
    # phrase but is not the phrase itself ("Observation only, ignore." against
    # "Observation only for record"). It is a question for the user, not a call
    # this script makes.
    near_keys = {" ".join(p.split()[:2]) for p in drop_phrases if len(p.split()) >= 2}
    title_filter = args.title.strip().lower() if args.title else None
    created_after = args.created_after

    # Layers, oldest first: the base pull, then every delta in date order.
    # Later layers overwrite earlier ones on collision, so the newest state of
    # a task wins, but nothing that appears only in an older layer is lost.
    layers = [root] + deltas

    # tasks: merged by uid across every layer, keyed so a task revised in a
    # later delta replaces its earlier version rather than duplicating it.
    by_uid = {}
    for layer in layers:
        for t in load_json(os.path.join(layer, "tasks.json"), []) or []:
            by_uid[t["uid"]] = t
    tasks = list(by_uid.values())
    tasks_src = " + ".join(os.path.basename(l) or "." for l in layers)

    # sheets: the base is authoritative, a delta's sheets.json is usually empty
    sheets = []
    for layer in layers:
        sheets += load_json(os.path.join(layer, "sheets.json"), []) or []
    sheet_by_uid = {s["uid"]: s for s in sheets}

    # photo binaries: each layer ships only its own new files
    photo_dirs = [os.path.join(l, "photos") for l in layers]
    photo_files = index_photo_files([d for d in photo_dirs if os.path.isdir(d)])

    # task_details, merged, later layers win on collision
    details = {}
    for base_dir in layers:
        for f in glob.glob(os.path.join(base_dir, "task_details", "*.json")):
            d = load_json(f)
            if d:
                details[d["task_uid"]] = d

    filler = detect_filler_title(tasks)

    items, missing_photos = [], []
    dropped_deleted, dropped_title, dropped_date, dropped_phrase, near_miss = [], [], [], [], []
    kept_deleted = []
    for t in sorted(tasks, key=lambda z: z.get("number", 0)):
        num = t.get("number")
        if keep is not None and num not in keep:
            continue
        is_deleted = bool(t.get("deleted") or t.get("archived"))
        if is_deleted and not args.keep_deleted:
            dropped_deleted.append(num)
            continue
        if is_deleted:
            kept_deleted.append(num)

        title = (t.get("title") or "").strip()
        if title_filter is not None and title.lower() != title_filter:
            dropped_title.append(num)
            continue
        if created_after and str(t.get("created_at") or "")[:10] <= created_after:
            dropped_date.append(num)
            continue
        desc_norm = " ".join((t.get("description") or "").split()).strip().lower().rstrip(".")
        if drop_phrases:
            if desc_norm in {p.rstrip(".") for p in drop_phrases}:
                dropped_phrase.append(num)
                continue
            if any(k in desc_norm for k in near_keys):
                near_miss.append((num, (t.get("description") or "").strip()))

        if filler and title == filler:
            title = ""

        ann = t.get("current_annotation") or {}
        sheet = sheet_by_uid.get((ann.get("sheet") or {}).get("uid"), {})
        detail = details.get(t["uid"], {})

        photos = []
        for p in detail.get("photos", []):
            path = photo_files.get(p["uid"])
            if path is None:
                missing_photos.append((num, p["uid"]))
                continue
            stamp = None
            m = re.search(r"(\d{8})_(\d{6})", p.get("title") or "")
            if m:
                stamp = f"{m.group(1)}T{m.group(2)}"
            photos.append({
                "uid": p["uid"],
                "title": p.get("title"),
                "path": path,
                "captured": stamp,
                "photographer": (p.get("created_by") or {}).get("email"),
            })

        items.append({
            "number": num,
            "uid": t["uid"],
            "title": title,
            "description": (t.get("description") or "").strip(),
            "status": t.get("status"),
            "room": t.get("room", ""),
            "sheet_name": sheet.get("name"),
            "sheet_description": sheet.get("description"),
            "pin_stamp": ann.get("stamp"),
            "photo_count_field": (t.get("photos") or {}).get("total_count"),
            "photos": photos,
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "created_by": (t.get("created_by") or {}).get("email"),
            # True only under --keep-deleted; the renderer banners such items.
            "deleted_in_plangrid": is_deleted,
        })

    # Possible duplicate pins, from data only: two items sharing a photo uid, or
    # two photo files with identical bytes. Similar-looking photos are NOT a
    # signal (field result 2026-09-09: two distinct blank-wall pins were raised as
    # a possible duplicate and the reviewer had to disprove it). Pin proximity
    # comes from extract_sheet_clips.py's clip similarity, not from here.
    import hashlib
    by_uid_items, by_hash_items = {}, {}
    for i in items:
        for p in i["photos"]:
            by_uid_items.setdefault(p["uid"], set()).add(i["number"])
            try:
                with open(p["path"], "rb") as fh:
                    h = hashlib.sha1(fh.read()).hexdigest()
                by_hash_items.setdefault(h, set()).add(i["number"])
            except OSError:
                pass
    dup_pairs = set()
    for group in list(by_uid_items.values()) + list(by_hash_items.values()):
        nums = sorted(group)
        for a_i, a in enumerate(nums):
            for b in nums[a_i + 1:]:
                dup_pairs.add((a, b))
    for i in items:
        others = sorted({b if a == i["number"] else a for a, b in dup_pairs if i["number"] in (a, b)})
        i["possible_duplicate"] = others
    possible_duplicates = sorted(dup_pairs)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2)
    # Structured copy of the triage summary for run_record.py, beside items.json.
    triage_path = os.path.join(os.path.dirname(os.path.abspath(args.out)), "triage.json")
    with open(triage_path, "w", encoding="utf-8") as fh:
        json.dump({
            "tasks_source": tasks_src, "filler_title": filler,
            "dropped_deleted_or_archived": dropped_deleted, "kept_deleted_marked": kept_deleted,
            "dropped_title": dropped_title,
            "dropped_created_on_or_before": dropped_date, "dropped_phrase": dropped_phrase,
            "near_miss": near_miss,
            "possible_duplicates": possible_duplicates,
            "rules": {"only": args.only, "title": args.title, "created_after": created_after,
                      "drop_phrases": args.drop_phrase, "keep_deleted": args.keep_deleted},
        }, fh, indent=1)

    # triage summary, read this before anything else
    described = [i for i in items if i["description"]]
    photo_only = [i for i in items if not i["description"] and i["photos"]]
    no_content = [i for i in items if not i["description"] and not i["photos"]]
    with_room = [i for i in items if (i["room"] or "").strip()]
    no_sheet = [i["number"] for i in items if not i["sheet_name"]]

    print(f"tasks source     : {tasks_src}")
    print(f"filler title     : {filler!r}" if filler else "filler title     : none detected")
    if dropped_deleted:
        print(f"dropped, deleted/archived : {dropped_deleted}  (KEEP_DELETED=1 keeps them, marked)")
    if kept_deleted:
        print(f"kept, deleted/archived (marked deleted_in_plangrid) : {kept_deleted}")
    if title_filter is not None:
        print(f"dropped, title != {args.title!r} : {dropped_title}")
    if created_after:
        print(f"dropped, created on/before {created_after} : {dropped_date}")
    if drop_phrases:
        print(f"dropped, record-only phrase : {dropped_phrase}")
    if near_miss:
        print("NEAR-MISS (kept; ask the user before drafting):")
        for num, desc in near_miss:
            print(f"   #{num}: {desc!r}")
    print(f"items            : {len(items)}")
    print(f"  described      : {len(described)} -> {[i['number'] for i in described]}")
    print(f"  photo_only     : {len(photo_only)} -> {[i['number'] for i in photo_only]}")
    print(f"  no_photos      : {len(no_content)} -> {[i['number'] for i in no_content]}")
    print(f"  with_room      : {len(with_room)}")
    print(f"  no_sheet_ref   : {len(no_sheet)} -> {no_sheet}")
    print(f"photos resolved  : {sum(len(i['photos']) for i in items)}"
          f" (declared {sum(i['photo_count_field'] or 0 for i in items)})")
    if missing_photos:
        print(f"MISSING BINARIES : {missing_photos}", file=sys.stderr)
    if possible_duplicates:
        print(f"POSSIBLE DUPLICATE PINS (shared photo) : {possible_duplicates}  <- ask the user; the only photo-based duplicate signal")
    print("sheet usage      :", dict(Counter(i["sheet_name"] for i in items)))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
