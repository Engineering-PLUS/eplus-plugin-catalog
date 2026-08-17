"""Extract the per-item annotated sheet clip from a PlanGrid Task Report PDF.

The clip -- a crop of the drawing showing that item's pin stamp -- exists ONLY
in the Task Report PDF export. An API pull's sheet_packets/*.pdf contains the
raw drawings with NO pin stamps; do not look for it there.

Three traps, all of which cost real time the first time round and are handled
below:

 1. The first pages are a Table of Contents that repeats every item heading
    with a dot leader and page number, so a naive search for "#N" matches the
    ToC entry instead of the real block. Content pages are skipped past.
 2. The image's reported bbox is LARGER than what is actually visible -- a
    clip path in the content stream is not exposed through get_image_info --
    so the crop is anchored off the "Sheet" text label instead, with an
    empirically tuned offset.
 3. An item whose block runs into the bottom margin has its clip pushed onto
    the NEXT page with no repeated heading. Detected (no image near the
    expected crop) and handled by taking the image off the following page.

Requires: pip install pymupdf

Usage:
  python extract_sheet_clips.py <task_report.pdf> <out_dir> [--items 3,4,5]
  python extract_sheet_clips.py report.pdf clips/ --items-from master.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pymupdf

# The heading marker on each item block. PlanGrid renders "#<number> <title>",
# where the title is often a per-engineer marker string ("Jim2"). Matching on
# the number alone plus a word boundary is more portable across projects.
HEADING_RE = "#{n}"

# Full-page drawing raster embedded per item, in pixels. PlanGrid is
# consistent here, but tolerate small variation.
CLIP_W, CLIP_H, CLIP_TOL = 2100, 1500, 5

# Offsets from the "Sheet" label's top-left to the visible clip box, in points.
LABEL_DX, LABEL_DY, CLIP_BOX_W, CLIP_BOX_H = -12, -6, 199, 200

RENDER_SCALE = 4  # 4x supersample; the clip is small on the page


def find_first_content_page(doc) -> int:
    """Skip the Table of Contents. ToC lines carry dot leaders ('..... 12');
    the first page without them is where real item blocks start."""
    for p in range(min(len(doc), 12)):
        text = doc[p].get_text()
        if text.count(".....") >= 3:
            continue
        if re.search(r"#\d+", text):
            return p
    return min(3, len(doc) - 1)


def extract(pdf_path: Path, out_dir: Path, numbers: list[int]) -> dict:
    doc = pymupdf.open(pdf_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    first = find_first_content_page(doc)
    print(f"content starts on page index {first} (ToC skipped)")

    headings = {}
    for n in numbers:
        for p in range(first, len(doc)):
            hits = doc[p].search_for(HEADING_RE.format(n=n))
            if hits:
                headings[n] = (p, hits[0])
                break
        else:
            print(f"  WARNING: heading not found for item #{n}")

    results, fallbacks = {}, []
    for n in numbers:
        if n not in headings:
            continue
        page_idx, hrect = headings[n]
        page = doc[page_idx]

        page_images = [
            i["bbox"] for i in page.get_image_info(xrefs=True)
            if abs(i["width"] - CLIP_W) < CLIP_TOL and abs(i["height"] - CLIP_H) < CLIP_TOL
        ]

        crop_rect, crop_page, used_fallback = None, page, False
        labels = sorted((r for r in page.search_for("Sheet") if r.y0 >= hrect.y0 - 2),
                        key=lambda r: r.y0)
        if labels:
            lab = labels[0]
            cand = pymupdf.Rect(lab.x0 + LABEL_DX, lab.y0 + LABEL_DY,
                                lab.x0 + LABEL_DX + CLIP_BOX_W,
                                lab.y0 + LABEL_DY + CLIP_BOX_H)
            # Only trust the anchor if a clip image is actually near it --
            # otherwise this is the overflow case and the box would be blank.
            near = any(cand.intersects(pymupdf.Rect(*b)) for b in page_images)
            if cand.y1 <= page.rect.height and near:
                crop_rect = cand

        if crop_rect is None:
            used_fallback = True
            cands = []
            for pidx in (page_idx, page_idx + 1):
                if pidx >= len(doc):
                    continue
                for i in doc[pidx].get_image_info(xrefs=True):
                    if (abs(i["width"] - CLIP_W) < CLIP_TOL
                            and abs(i["height"] - CLIP_H) < CLIP_TOL):
                        cands.append((pidx, i["bbox"]))
            if not cands:
                print(f"  WARNING: no clip image anywhere for item #{n}")
                continue
            cands.sort(key=lambda c: (c[0] != page_idx + 1, c[0]))
            pidx, bbox = cands[0]
            crop_page = doc[pidx]
            crop_rect = pymupdf.Rect(bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)

        pix = crop_page.get_pixmap(clip=crop_rect,
                                   matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE))
        dest = out_dir / f"item_{n}.png"
        if dest.exists():          # never overwrite in place
            dest = out_dir / f"item_{n}_r2.png"
        pix.save(dest)
        results[n] = {"path": str(dest), "fallback": used_fallback}
        if used_fallback:
            fallbacks.append(n)

    (out_dir / "_index.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"extracted {len(results)}/{len(numbers)} clips")
    if fallbacks:
        print(f"  used next-page fallback for: {fallbacks}")
    missing = [n for n in numbers if n not in results]
    if missing:
        print(f"  MISSING entirely: {missing}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--items", help="comma-separated item numbers")
    ap.add_argument("--items-from", help="JSON file: a list of objects with a 'number' key")
    args = ap.parse_args()

    if args.items:
        numbers = [int(x) for x in args.items.split(",") if x.strip()]
    elif args.items_from:
        raw = json.loads(Path(args.items_from).read_text(encoding="utf-8"))
        rows = raw.get("items", raw) if isinstance(raw, dict) else raw
        numbers = [r["number"] for r in rows]
    else:
        raise SystemExit("give --items or --items-from")

    extract(Path(args.pdf), Path(args.out_dir), numbers)


if __name__ == "__main__":
    main()
