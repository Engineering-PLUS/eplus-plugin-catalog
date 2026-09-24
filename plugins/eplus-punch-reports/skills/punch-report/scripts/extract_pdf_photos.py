#!/usr/bin/env python3
"""
extract_pdf_photos.py -- FALLBACK photo source: recover site photos and sheet
names from the PlanGrid Task Report PDF.

Use this only after scripts/fetch_photos.py reported failures. The PDF embeds
each photo at roughly 350 x 620 px, well below the originals, so a report built
this way has visibly softer photos. When it is used, PROCESS-LOG.md must say
so ("photo route: pdf") and the reason (which host failed).

Per item page in the Task Report it:
  1. Skips table-of-contents pages (no "Sheet" line resolves on them).
  2. Reads the "Sheet" label text for the item -> sheets.json.by_item.json,
     which adapt_mcp_pull.py joins to sheet uids (the MCP pull's own
     sheets.json is often empty).
  3. Finds every embedded image that is camera-sized: not the wide header
     logo, not the ~2000 px full sheet drawing (both repeat on every page).
  4. Recovers each image's on-page clip rectangle by parsing the content
     stream: the path "x y m ... l h W n" immediately before "<cm> /imgN Do"
     is the true crop box. PyMuPDF's get_image_rects() was off by a constant
     on nested-form content streams; do not trust it here.
  5. Renders just that rectangle with PyMuPDF (annotations off); the render
     applies the page transform, so the crop comes out oriented as displayed.
  6. Matches photos to PlanGrid photo uids by order: the left-to-right,
     top-to-bottom order in the content stream matches the order the MCP
     lists them for that item (verified against the caption text under each).

    python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp
    python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp --items 41,42,45-50

Writes <pull>/pdf_photos/<uid>__<title>.jpg and <pull>/sheets.json.by_item.json.
Photos already present in <pull>/photos/ (live originals) are skipped unless
--all is given, so a partial live fetch is topped up rather than replaced.
"""
import argparse
import json
import os
import re
import sys

import fitz  # pymupdf

ITEM_RE = re.compile(r"^#(\d+)\b", re.M)
SHEET_RE = re.compile(r"Sheet\s*\n(\S+)")
POINT_RE = re.compile(r"([\-\d.]+) ([\-\d.]+) [ml]")
# PlanGrid's clip paths close either with an explicit point back to the start
# or with "h" alone, so capture any run of m/l points and take their extent.
DO_RE = re.compile(
    r"((?:[\-\d.]+ [\-\d.]+ [ml]\s*\n)+)"
    r"h\s*\nW\s*\nn\s*\n"
    r"q ([\-\d.]+ [\-\d.]+ [\-\d.]+ [\-\d.]+ [\-\d.]+ [\-\d.]+) cm /(\w+) Do Q"
)
DRAWING_DIM_MIN = 1000   # the full sheet drawing is ~2000 x 1500
BANNER_ASPECT = 3.5      # header logo is a wide strip (~500 x 101)
PHOTO_DIM_MIN = 120      # icons are smaller than any site photo


def parse_only(spec):
    keep = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            keep.update(range(int(lo), int(hi) + 1))
        elif chunk:
            keep.add(int(chunk))
    return keep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf_path")
    ap.add_argument("--pull", default="../plangrid_mcp",
                    help="folder holding mcp_photo_urls.json; pdf_photos/ is created inside it")
    ap.add_argument("--items", default=None, help='restrict to e.g. "19,21,22-30" (default: every item in the PDF)')
    ap.add_argument("--scale", type=float, default=3.0)
    ap.add_argument("--all", action="store_true", help="extract even photos already present in photos/")
    args = ap.parse_args()

    pull = os.path.abspath(args.pull)
    meta_path = os.path.join(pull, "mcp_photo_urls.json")
    photo_meta = json.load(open(meta_path, encoding="utf-8")) if os.path.isfile(meta_path) else {}
    if not photo_meta:
        # photos inline on get_tasks rows (MCP 0.7+); fetch_photos.py normally
        # materialises mcp_photo_urls.json from them first, but do not depend on it
        tp = os.path.join(pull, "tasks.json")
        if os.path.isfile(tp):
            data = json.load(open(tp, encoding="utf-8"))
            rows = data.get("tasks", []) if isinstance(data, dict) else data
            for t in rows or []:
                if isinstance(t.get("photos"), list) and t.get("number") is not None:
                    photo_meta[str(t["number"])] = [p for p in t["photos"] if isinstance(p, dict) and p.get("uid")]
    if not photo_meta:
        print(f"WARNING: {meta_path} missing or empty; photos will be named by position, "
              f"and consolidate.py will not be able to index them", file=sys.stderr)
    wanted = parse_only(args.items) if args.items else None
    live_dir = os.path.join(pull, "photos")
    dest = os.path.join(pull, "pdf_photos")
    os.makedirs(dest, exist_ok=True)

    doc = fitz.open(args.pdf_path)

    sheet_by_item = {}
    items_found = []
    saved = skipped = failed = 0

    for pidx in range(len(doc)):
        page = doc[pidx]
        text = page.get_text()
        m = ITEM_RE.search(text)
        if not m:
            continue
        sm = SHEET_RE.search(text)
        if not sm:
            continue  # ToC page
        num = int(m.group(1))
        if wanted is not None and num not in wanted:
            continue
        sheet_by_item[str(num)] = sm.group(1)
        items_found.append(num)

        photo_xrefs = {}
        for img in page.get_images(full=True):
            xref, name = img[0], img[7]
            base = doc.extract_image(xref)
            w, h = base["width"], base["height"]
            if w >= DRAWING_DIM_MIN or h >= DRAWING_DIM_MIN:
                continue
            if w < PHOTO_DIM_MIN or h < PHOTO_DIM_MIN:
                continue
            if w / max(h, 1) >= BANNER_ASPECT:
                continue
            photo_xrefs[name] = xref
        if not photo_xrefs:
            continue

        content = page.read_contents().decode("latin-1", errors="replace")
        ph = page.rect.height
        ordered, rects = [], {}
        for dm in DO_RE.finditer(content):
            path_block, _cm, name = dm.groups()
            if name not in photo_xrefs:
                continue
            pts = POINT_RE.findall(path_block)
            if not pts:
                continue
            xs = [float(x) for x, _ in pts]
            ys = [float(y) for _, y in pts]
            rects[name] = (min(xs), min(ys), max(xs), max(ys))
            ordered.append(name)

        meta_list = photo_meta.get(str(num), [])
        if meta_list and len(ordered) != len(meta_list):
            print(f"item {num}: WARNING {len(ordered)} photos on the page but the MCP lists "
                  f"{len(meta_list)}; matching by order may be wrong for this item", file=sys.stderr)

        matrix = fitz.Matrix(args.scale, args.scale)
        for i, name in enumerate(ordered):
            if i < len(meta_list):
                uid, title = meta_list[i]["uid"], meta_list[i].get("title") or meta_list[i]["uid"]
            else:
                uid, title = f"unmatched-{num}-{i}", f"item{num}_photo{i}"
            fname = f"{uid}__{title}.jpg"
            if not args.all and os.path.isfile(os.path.join(live_dir, fname)):
                skipped += 1
                continue
            # content-stream coordinates are PDF user space (y up); PyMuPDF's page
            # space has y down from the top-left corner, so flip through page height
            x0, y0, x1, y1 = rects[name]
            clip = fitz.Rect(x0, ph - y1, x1, ph - y0)
            try:
                pix = page.get_pixmap(matrix=matrix, clip=clip, annots=False, alpha=False)
                pix.save(os.path.join(dest, fname), output="jpg", jpg_quality=92)
                saved += 1
            except Exception as e:  # noqa: BLE001
                print(f"item {num}: failed to crop {name}: {e}", file=sys.stderr)
                failed += 1

    with open(os.path.join(pull, "sheets.json.by_item.json"), "w", encoding="utf-8") as f:
        json.dump(sheet_by_item, f, indent=1)

    print(f"items in PDF       : {len(items_found)} -> {sorted(items_found)}")
    if wanted is not None:
        miss = sorted(wanted - set(items_found))
        if miss:
            print(f"items NOT in PDF   : {miss} (different export window?)", file=sys.stderr)
    print(f"sheet names        : {len(set(sheet_by_item.values()))} distinct -> sheets.json.by_item.json")
    print(f"photos saved       : {saved} -> {dest}  (about 350 x 620 px; originals are larger)")
    if skipped:
        print(f"skipped, live copy : {skipped}")
    if failed:
        print(f"failed             : {failed}")
    print("photo route        : pdf for the saved photos. Say so in PROCESS-LOG.md, with the host that failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
