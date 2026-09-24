#!/usr/bin/env python3
"""
build_master.py, assemble the render-ready master_report_items.json.

This closes the gap an earlier pipeline left open: master_report_items.json was
assembled ad hoc from items.json plus hand-written drafts, so a report could not
be rebuilt from source without redoing that step by hand. This script makes the
assembly reproducible.

Inputs
  data/items.json           consolidate.py output, the PlanGrid facts
  data/drafted_items.json   the human/model judgment layer, keyed by PlanGrid number.
                            Either a bare list of entries, or an object
                            {"items": [...], "merges": [...]} (schema in SKILL.md)
Output
  build/master_report_items.json

Rules enforced here so the renderer never has to care:
  - NO EM OR EN DASHES anywhere in any string. Swept and asserted, not hoped for.
    (Standing EPLUS report rule; verify_report.py asserts zero in the document.)
  - Corrective actions always start with a capital letter.
  - photo_paths are BASENAMES ONLY. The renderer resolves them against its own
    thumbs_uniform directory. Passing absolute source paths silently renders the
    unnormalized, EXIF-sideways original.
  - Items with no drafted entry fail loudly rather than rendering blank.
  - Entries with origin "reviewer_final" or "user_reviewed" are human-approved
    text: never sanitized, never recapitalised, exempt from the voice guard, and
    the build FAILS if sanitize() would have changed them.
  - Reviewer pin merges ("merges": [{"into": N, "from": M, "drop_photos": [..]}])
    are applied in memory: the absorbed pin's photos fold into the target in
    chronological order (deduped by uid, named photos dropped) and the absorbed
    pin is omitted. items.json is never mutated to record a human decision.
  - date_recorded is the PIN's created_at (MM/DD/YYYY), never a photo timestamp.
    Field result 2026-09-14: the renderer used to take the date from photo
    titles, so 27 of 38 photo-less items printed "N/A" and the report had to be
    re-delivered. photo_date is still carried for the record.
  - Pins PlanGrid deleted or archived arrive flagged deleted_in_plangrid
    (run_pipeline.sh always consolidates with --keep-deleted since 0.9.0).
    This step applies the decision: report.config.json "deleted_pins" is
    "drop" (default) or "keep"; KEEP_DELETED=1 still means keep. Kept pins
    carry the flag so the renderer banners them and marks the TOC. Changing
    the decision is therefore a re-render, never a data re-run.
  - drafted_items.json may carry "omit": [N, ...], pins the reviewer dropped
    from the report (update_report.py --drop). items.json is never edited.
  - Entries with "blank": true (blank_template.py, an empty fill-in report)
    render as empty pages: no title, no description, no N/A, no voice check.

Usage:
    python3 build_master.py --items data/items.json \
        --drafted data/drafted_items.json -o build/master_report_items.json
"""
import argparse
import json
import os
import re
import sys

DASH_RE = re.compile(r"[–—]")
UNDETERMINED_CA = "N/A, see Editor's Note"

# Item descriptions are written in field-report voice: the engineer stating what the
# condition IS. Two failure modes get caught here because both read badly to a client
# and both are easy to slip back into:
#   1. Narrating the evidence ("the photograph shows...", "not visible in the frame").
#      The report describes the site, not the photo library.
#   2. Third person self-reference ("the field engineer recorded..."). This report is
#      written BY the field engineer, so that reads as someone else talking about them.
# Editor's Notes are internal and exempt, they may discuss photos and pins freely.
#
# The patterns match NARRATION, not the bare nouns. "No accompanying photograph"
# is field-report voice stating an absence of evidence and is allowed; "the
# photograph shows" is not. Field result 2026-09-14: the bare-noun rule blocked a
# render on a deleted pin whose whole note was one word, and those thin pins are
# exactly the ones that need to say no photo exists. verify_report.py imports
# this list so the two never disagree.
VOICE_BANNED = [
    r"\b(photo(graph)?s?|images?|pictures?|frames?)\s+(show|depict|capture|indicate|reveal|confirm|suggest)",
    r"\b(in|from|per|within)\s+(the|this|that|each|these|both)\s+(photo(graph)?s?|images?|pictures?|frames?)\b",
    r"\b(as|is|are|was|were)\s+(shown|seen|pictured|visible|evident)\s+(in|from)\s+(the|this|that)\s+(photo|image|picture|frame)",
    r"\bthis photo", r"\bin the frame", r"\bnot determinable from",
    r"\bfield engineer", r"\bno description was recorded",
    # Statements ABOUT the photo instead of the site. Field result 2026-09-23
    # (test-punch step 7 and a live CTX2 run): "The image is unclear." passed the
    # narration patterns above because it has no narration verb.
    # ("frame" is left out on purpose: "the frame is bent" is a rack or door
    # frame, a real site condition.)
    r"\b(the|this|that|these|those)\s+(photo(graph)?s?|images?|pictures?)\s+(is|are|was|were|appears?|seems?|looks?)\b",
    r"\b(photo(graph)?|image|picture)s?\s+(is|are)?\s*(unclear|blurry|blurred|out of focus|inconclusive|too dark)\b",
    # Statements about the pin note instead of the site ("the note says ...").
    # "reads" stays allowed: "The field note reads only Up, with no accompanying
    # photograph." is how a thin pin states that nothing more was recorded.
    # Field result 2026-09-23 (CTX2 build-first run): 16 drafts said "the pin note
    # requests / records / flags ..." and passed, so the verb list is wide.
    r"\b(the|this)\s+(pin\s+|field\s+)?note\s+(says|states|mentions|indicates|describes|requests|records"
    r"|flags|asks|calls|notes|reports|lists|identifies|references|documents|suggests|specifies|asserts)\b",
    r"\b(the|this)\s+pin\s+(says|states|mentions|indicates|describes|requests|records|flags|asks|calls"
    r"|notes|reports|identifies|references|documents|suggests)\b",
    r"\bper the (pin |field )?note\b",
]


# PlanGrid's sheet-name OCR reads the character after a leading T as the LETTER O
# rather than a ZERO when drawings are uploaded, so a set that is really T02-01A1
# comes back as TO2-01A1. The upload-side fix is to correct each sheet name by hand
# at upload time, which is easy to forget and is not something the report can rely on.
# Every sheet in the punch corpus (85 distinct, all T-series) uses a zero, so the
# correct form is unambiguous.
#
# Scoped deliberately narrowly: a leading T, then a LETTER O, then a DIGIT. That
# matches TO2-01A1 and TO5-09 while leaving any genuine word starting with "TO"
# alone, because a real sheet designator always has a digit in that position.
SHEET_OCR_RE = re.compile(r"\bT[Oo](?=\d)")


def normalize_sheet(name):
    """Repair the PlanGrid letter-O-for-zero OCR error in a sheet designator."""
    return SHEET_OCR_RE.sub("T0", name or "")


def sanitize(s):
    """Remove em/en dashes and hyphens used as em dashes. Preserve real hyphens.

    A dash between digits is a range and becomes a hyphen ("10–12" -> "10-12").
    Any other dash becomes a comma with its spacing normalised: field result
    2026-09-23, "Switch Cabinet Position – Cabinets 201 & 202" rendered as
    "Position , Cabinets" because the dash was replaced in place.
    """
    if not isinstance(s, str):
        return s
    s = re.sub(r"(?<=\d)\s*[–—]\s*(?=\d)", "-", s)
    s = re.sub(r"\s*[–—]\s*", ", ", s)
    s = re.sub(r" - ", ", ", s)
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip().strip(",").strip()


def walk_sanitize(obj):
    if isinstance(obj, str):
        return sanitize(obj)
    if isinstance(obj, list):
        return [walk_sanitize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: walk_sanitize(v) for k, v in obj.items()}
    return obj


def capitalize_first(s):
    if not s:
        return s
    return s[0].upper() + s[1:]


def fmt_date(iso):
    """'2026-08-27T20:41:19.233746' or '2026-08-27' -> '08/27/2026'; None if unparsable."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return f"{m.group(2)}/{m.group(3)}/{m.group(1)}" if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/items.json")
    ap.add_argument("--drafted", default="data/drafted_items.json")
    ap.add_argument("-o", "--out", default="build/master_report_items.json")
    ap.add_argument("--omit", default="", help="comma list of PlanGrid numbers to drop")
    ap.add_argument("--config", default=None,
                    help="report.config.json (default: beside the output); read for deleted_pins")
    args = ap.parse_args()

    items = json.load(open(args.items, encoding="utf-8"))
    cfg_path = args.config or os.path.join(os.path.dirname(os.path.abspath(args.out)), "report.config.json")
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}

    # drafted_items.json is either the historical bare list, or an object
    # {"items": [...], "merges": [...], "omit": [...]} so reviewer decisions
    # (pin merges, pins dropped from the report) live in the judgment layer
    # instead of as a mutation of items.json.
    drafted_doc = json.load(open(args.drafted, encoding="utf-8"))
    omit_doc = []
    if isinstance(drafted_doc, dict):
        drafted_list = drafted_doc["items"]
        merges = drafted_doc.get("merges", [])
        omit_doc = [int(x) for x in drafted_doc.get("omit", [])]
    else:
        drafted_list = drafted_doc
        merges = []
    # Workers sometimes emit the number as a string; the join is on PlanGrid ints.
    for d in drafted_list:
        d["number"] = int(d["number"])
    lacking = [f"#{d['number']} ({', '.join(f for f in ('title', 'description') if not d.get(f))})"
               for d in drafted_list if not d.get("blank") and (not d.get("title") or not d.get("description"))]
    if lacking:
        sys.exit("ERROR: every drafted item needs a title and a description. Missing on: "
                 + ", ".join(lacking))
    drafted = {d["number"]: d for d in drafted_list}
    omit = {int(x) for x in args.omit.split(",") if x.strip()} | set(omit_doc)

    # Pins PlanGrid has deleted or archived. Since 0.9.0 consolidate keeps them
    # (flagged deleted_in_plangrid) and THIS step applies the decision, so
    # changing it is a re-render, not a re-run of the data steps:
    #   report.config.json "deleted_pins": "drop" (default) | "keep"
    #   KEEP_DELETED=1 in the environment still means keep (older runs).
    keep_deleted = str(cfg.get("deleted_pins") or "").lower() == "keep" \
        or os.environ.get("KEEP_DELETED", "").strip() not in ("", "0")
    deleted_nums = [i["number"] for i in items if i.get("deleted_in_plangrid")]
    if not keep_deleted:
        omit |= set(deleted_nums)

    # Apply merges in memory: fold the absorbed pin's photos in, dedupe by uid,
    # keep chronological order, drop named photos, and auto-omit the absorbed pin.
    by_num = {i["number"]: i for i in items}
    for mg in merges:
        into, src_n = mg["into"], mg["from"]
        if into not in by_num or src_n not in by_num:
            sys.exit(f"ERROR: merge {src_n} -> {into} names a pin not in {args.items}.")
        dst, src = by_num[into], by_num[src_n]
        have = {p["uid"] for p in dst["photos"]}
        drops = mg.get("drop_photos", [])
        for p in src["photos"]:
            title = p.get("title") or ""
            if any(d in title for d in drops):
                continue
            if p["uid"] in have:
                continue
            dst["photos"].append(p)
        dst["photos"].sort(key=lambda p: p.get("captured") or "")
        dst["merged_from"] = sorted(set(dst.get("merged_from", []) + [src_n]))
        omit.add(src_n)

    missing = [i["number"] for i in items if i["number"] not in drafted and i["number"] not in omit]
    if missing:
        hint = ""
        if keep_deleted and set(missing) & set(deleted_nums):
            hint = (f" {sorted(set(missing) & set(deleted_nums))} are pins PlanGrid deleted, kept by "
                    f"deleted_pins=keep; draft them, or set deleted_pins back to drop.")
        sys.exit(f"ERROR: no drafted entry for PlanGrid items {missing}. "
                 f"Every item must be drafted, including undeterminable ones." + hint)

    master, display_n = [], 0
    for it in sorted(items, key=lambda x: x["number"]):
        num = it["number"]
        if num in omit:
            continue
        d = drafted[num]
        display_n += 1

        # An empty fill-in page (blank_template.py): every field stays empty so
        # the engineer types into it in Word; nothing reads "N/A".
        if d.get("blank"):
            master.append({
                "display_number": display_n, "plangrid_ref": f"#{num}", "blank": True,
                "title": "", "description": "", "corrective_action": "", "location": "",
                "sheet_display": "", "sheet_name": "", "sheet_description": "",
                "photo_paths": [], "photo_titles": [], "origin": "blank_template",
                "confidence": None, "field_note_original": None, "precedent_note": None,
                "editor_note": None, "photo_mode": None, "status": None,
                "date_recorded": "", "created_at": None, "photo_date": None,
                "deleted_in_plangrid": False,
            })
            continue

        # Text that a human approved is never altered by the pipeline. It must
        # arrive already clean; anything sanitize would change is an error, not
        # a silent rewrite.
        protected = d.get("origin") in ("reviewer_final", "user_reviewed")
        if protected:
            for field in ("title", "description", "corrective_action"):
                val = d.get(field)
                if val and sanitize(val) != val:
                    sys.exit(f"ERROR: pin {num} has origin {d['origin']!r} but its "
                             f"{field} is not sanitize-clean. Fix the source text "
                             f"explicitly instead of letting the pipeline rewrite "
                             f"approved wording. Offending value: {val!r}")

        ca = d.get("corrective_action") or UNDETERMINED_CA
        sheet_name = normalize_sheet(it.get("sheet_name") or "")
        sheet_desc = it.get("sheet_description") or ""
        sheet_display = f"{sheet_name}, {sheet_desc}" if sheet_desc else (sheet_name or "N/A")

        room = (it.get("room") or "").strip()

        master.append({
            "display_number": display_n,
            "plangrid_ref": f"#{num}",
            "title": d["title"],
            "description": d["description"],
            "corrective_action": ca if protected else capitalize_first(ca),
            # PlanGrid room is empty on 100% of pins in this pull. Say so rather
            # than printing a bare "N/A" the reader has to interpret.
            "location": room or "Not recorded in PlanGrid, see sheet reference",
            "sheet_display": sheet_display,
            "sheet_name": sheet_name,
            "sheet_description": sheet_desc,
            "photo_paths": [os.path.basename(p["path"]).split("__")[0] + ".jpg"
                            for p in it["photos"]],
            "photo_titles": [p["title"] for p in it["photos"]],
            "origin": d.get("origin"),
            "confidence": d.get("confidence"),
            # the engineer's verbatim pin note, carried for traceability and the
            # review spreadsheet; never rendered
            "field_note_original": d.get("field_note"),
            "precedent_note": d.get("precedent_note"),
            "editor_note": d.get("editor_note"),
            # For items without photos: "own_photos" renders the blank paste
            # grid, "none" suppresses the grid and the Photos label entirely,
            # "followup" renders the blank grid (an editor_note should say a
            # revisit is planned). Absent means own_photos.
            "photo_mode": d.get("photo_mode"),
            "status": it.get("status"),
            # The pin's own creation date, which every PlanGrid item has. This is
            # what the Date Recorded row prints; photo_date is record only.
            "date_recorded": fmt_date(it.get("created_at")),
            "created_at": it.get("created_at"),
            "photo_date": (it["photos"][0]["captured"][:8] if it["photos"] else None),
            # True when consolidate.py ran with --keep-deleted and PlanGrid had the
            # pin deleted or archived. Rendered as a red banner plus a TOC marker.
            "deleted_in_plangrid": bool(it.get("deleted_in_plangrid")),
        })

    master = walk_sanitize(master)

    # Belt and braces: assert the dash rule actually held.
    blob = json.dumps(master)
    bad = DASH_RE.findall(blob)
    if bad:
        sys.exit(f"ERROR: {len(bad)} em/en dashes survived sanitization.")

    # voice guard, descriptions only. Human-approved text is exempt: the
    # reviewer outranks the style rule.
    offenders = []
    for m in master:
        if m.get("origin") in ("reviewer_final", "user_reviewed"):
            continue
        for pat in VOICE_BANNED:
            hit = re.search(pat, m["description"], re.I)
            if hit:
                offenders.append(f"  {m['plangrid_ref']}: {hit.group(0)!r} in description")
    if offenders:
        sys.exit("ERROR: item descriptions must be in field-report voice, not photo "
                 "narration or third person.\n" + "\n".join(offenders))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    json.dump(master, open(args.out, "w", encoding="utf-8"), indent=2)

    origins = {}
    for m in master:
        origins[m["origin"]] = origins.get(m["origin"], 0) + 1
    print(f"wrote {args.out}")
    print(f"  items          : {len(master)} (omitted {sorted(omit) or 'none'})")
    print(f"  photos         : {sum(len(m['photo_paths']) for m in master)}")
    print(f"  origins        : {origins}")
    print(f"  with precedent : {sum(1 for m in master if m['precedent_note'])}")
    print(f"  editor notes   : {sum(1 for m in master if m['editor_note'])}")
    undated = [m["plangrid_ref"] for m in master if not m["date_recorded"] and not m.get("blank")]
    print(f"  date recorded  : {len(master) - len(undated)} from pin created_at"
          + (f", MISSING on {undated}" if undated else ""))
    deleted = [m["plangrid_ref"] for m in master if m["deleted_in_plangrid"]]
    if deleted:
        print(f"  deleted, kept  : {deleted} (marked in the document; deleted_pins=keep)")
    elif deleted_nums:
        print(f"  deleted, dropped: {['#' + str(n) for n in deleted_nums]} (deleted_pins=drop, the default)")
    print(f"  em/en dashes   : 0 (asserted)")


if __name__ == "__main__":
    main()
