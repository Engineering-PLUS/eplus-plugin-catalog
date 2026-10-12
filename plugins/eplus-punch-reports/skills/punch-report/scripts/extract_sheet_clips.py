#!/usr/bin/env python3
"""
extract_sheet_clips.py, pull the per-item annotated drawing clip (sheet + pin
stamp) out of a PlanGrid Task Report PDF.

This is a rewrite of an earlier script, which was hardcoded to one job in four
ways that all broke on the next project:
  - absolute input/output paths baked into the source
  - the heading string literal '#N <filler title>' (the next report used
    '#N General' and other real titles)
  - FIRST_CONTENT_PAGE = 3 hardcoded
  - the clip image size hardcoded to 2100x1500 (this report is 2000x1500) and
    a set of pixel offsets from the 'Sheet' label tuned to US Letter geometry
    (this report is A4, so the offsets landed in the wrong place entirely)

THE THREE TRAPS, and how this version handles them:

1. Table of Contents. The opening pages repeat every item heading with dot
   leaders and a page number, so a naive search for '#N' matches the ToC entry
   and every clip resolves to the wrong page. Handled by auto-detecting where
   the ToC ends (last page carrying dot-leader lines) rather than hardcoding.

2. The reported image bbox is LARGER than the visible region. PlanGrid draws
   the clip through a clip path that pymupdf does not expose via
   get_image_info(), so the reported bbox overruns the visible box, and on A4
   it overruns the page edge entirely (x1=658 on a 595pt page). The earlier fix
   was tuned pixel offsets from the 'Sheet' text label, which do not transfer
   between page sizes. This version instead locates the CLIP BOX BORDER, which
   PlanGrid draws as a real vector rectangle, and crops to that. No tuning, and
   it self-corrects across page sizes and layout changes.

3. Overflow. An item near a page bottom pushes its clip to the following page
   with no repeated heading. Detected and handled by falling back to the next
   page.

4. Duplicate clips. Two pins must never share a clip. It happened once: two
   items carried byte-identical clips and one was therefore showing the wrong
   drawing. Every emitted clip is sha1-hashed and a collision exits non-zero.

5. Adjacent pins. The MCP task rows carry no pin coordinates, but PlanGrid
   centres every clip on its pin, so two clips that look the same are two pins
   at (nearly) the same spot on the same sheet. Each clip gets a 64-bit
   difference hash; pairs within a small Hamming distance are written to
   build/sheet_clip_similarity.json as "near_identical". That file, with the
   shared-photo check in consolidate.py, is the only evidence a draft may cite
   for "these two items might be the same condition". Similar-looking site
   photos are not evidence (field result 2026-09-09: two distinct blank-wall
   pins were flagged as a possible duplicate photo and the reviewer had to
   disprove it).

Usage:
    bash scripts/install_deps.sh
    python3 extract_sheet_clips.py "<Task Report>.pdf" build/sheet_clips_jpg \
        --items-from data/items.json --dims-out build/sheet_clip_dims_jpg.json
"""
import argparse
import hashlib
import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf required:  bash scripts/install_deps.sh")

LEADER_RE = re.compile(r"\.{6,}\s*\d+")


def first_content_page(doc):
    """Last page carrying ToC dot-leader lines, plus one."""
    last_toc = -1
    for p in range(min(12, doc.page_count)):
        if len(LEADER_RE.findall(doc[p].get_text())) >= 3:
            last_toc = p
    return last_toc + 1


def find_heading(doc, number, start):
    """Page index and rect of the '#<number>' heading token, skipping the ToC."""
    token = f"#{number}"
    for p in range(start, doc.page_count):
        for w in doc[p].get_text("words"):
            # words -> (x0, y0, x1, y1, text, block, line, word_no)
            if w[4] == token:
                return p, pymupdf.Rect(w[0], w[1], w[2], w[3])
    return None, None


def find_clip_box(page, below_y):
    """
    The clip box is a real drawn rectangle. Pick the plausible one lowest on the
    page but still below the heading. Filtering by aspect and size keeps this
    from matching table rules or photo frames.
    """
    best = None
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.y0 < below_y:
            continue
        if not (90 < r.width < 340 and 55 < r.height < 280):
            continue
        aspect = r.width / r.height if r.height else 0
        if not (1.1 < aspect < 2.2):
            continue
        if best is None or r.y0 < best.y0:
            best = r
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--items-from", default="data/items.json")
    ap.add_argument("--dims-out", default="build/sheet_clip_dims_jpg.json")
    # PlanGrid draws the clip box at a fixed 178 x 122 pt regardless of page size
    # (verified identical on Letter 612x792 and A4 595x842), so the source is small and
    # the render zoom is what determines print quality. The renderer now shows the clip
    # at double its previous width, about 3.17in, so 4x would land at roughly 225 dpi.
    # 6x gives about 337 dpi, which holds up in print. Raise this if the clip column is
    # ever widened again: display width and zoom have to move together or the clip just
    # gets bigger and blurrier.
    ap.add_argument("--zoom", type=float, default=6.0)
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--near-threshold", type=int, default=6,
                    help="max Hamming distance (of 64) between clip difference hashes to call two pins adjacent")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    items = json.load(open(args.items_from, encoding="utf-8"))
    targets = [i["number"] for i in items]

    start = first_content_page(doc)
    print(f"pages={doc.page_count}  content starts at page {start + 1} (auto-detected)")

    os.makedirs(args.out_dir, exist_ok=True)
    dims, fallback, missing = {}, [], []
    seen_hashes = {}  # sha1 of clip bytes -> first pin that produced it
    duplicates = []

    for n in targets:
        pno, hrect = find_heading(doc, n, start)
        if pno is None:
            missing.append(n)
            continue

        page = doc[pno]
        box = find_clip_box(page, hrect.y1)
        used_fb = False

        if box is None and pno + 1 < doc.page_count:
            # overflow: clip pushed to the following page, no repeated heading
            page = doc[pno + 1]
            box = find_clip_box(page, 0)
            used_fb = box is not None

        if box is None:
            missing.append(n)
            continue

        # inset by the border stroke so the frame line is not baked into the image
        clip = pymupdf.Rect(box.x0 + 0.8, box.y0 + 0.8, box.x1 - 0.8, box.y1 - 0.8) & page.rect
        pix = page.get_pixmap(clip=clip, matrix=pymupdf.Matrix(args.zoom, args.zoom))
        name = f"item_{n}.jpg"
        out_path = os.path.join(args.out_dir, name)
        pix.pil_save(out_path, format="JPEG",
                     quality=args.quality, optimize=True)
        # Two pins must never share a clip. It happened in circulation once: two
        # items carried byte-identical clips and one was therefore showing the
        # wrong drawing (segment A1 for a pin on segment A2). Byte-hash every
        # emitted clip and flag collisions loudly.
        with open(out_path, "rb") as fh:
            h = hashlib.sha1(fh.read()).hexdigest()
        if h in seen_hashes:
            duplicates.append((seen_hashes[h], n))
        else:
            seen_hashes[h] = n
        dims[name] = [pix.width, pix.height]
        if used_fb:
            fallback.append(n)

    os.makedirs(os.path.dirname(os.path.abspath(args.dims_out)) or ".", exist_ok=True)
    json.dump(dims, open(args.dims_out, "w", encoding="utf-8"), indent=1)

    # Adjacent pins: difference-hash every clip and compare all pairs. Clips are
    # centred on their pin, so a small Hamming distance means two pins at nearly
    # the same spot. Written beside the dims file for run_record.py and drafting.
    near = []
    try:
        from PIL import Image
        hashes = {}
        for name in dims:
            im = Image.open(os.path.join(args.out_dir, name)).convert("L").resize((9, 8), Image.BILINEAR)
            px = im.tobytes()  # 72 grey values, row-major
            bits = 0
            for row in range(8):
                for col in range(8):
                    bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
            hashes[int(name[5:-4])] = bits
        nums = sorted(hashes)
        for i, a in enumerate(nums):
            for b in nums[i + 1:]:
                dist = bin(hashes[a] ^ hashes[b]).count("1")
                if dist <= args.near_threshold:
                    near.append([a, b, dist])
    except ImportError:
        print("  (Pillow missing; clip similarity not computed)")
    sim_path = os.path.join(os.path.dirname(os.path.abspath(args.dims_out)), "sheet_clip_similarity.json")
    json.dump({"near_identical": near, "byte_identical": duplicates,
               "threshold": args.near_threshold,
               "meaning": "near_identical pairs are pins at nearly the same spot on the same sheet; "
                          "the only clip-based evidence for a possible duplicate item"},
              open(sim_path, "w", encoding="utf-8"), indent=1)

    print(f"extracted {len(dims)}/{len(targets)} sheet clips -> {args.out_dir}")
    print(f"  used overflow fallback : {fallback or 'none'}")
    print(f"  missing                : {missing or 'none'}")
    print(f"  duplicate clips        : {duplicates or 'none'}")
    print(f"  near-identical clips   : {[(a, b) for a, b, _ in near] or 'none'}  (adjacent pins; see {os.path.basename(sim_path)})")
    print(f"  wrote {args.dims_out}")
    if missing:
        print("  CHECK the missing items by hand before rendering.")
    if duplicates:
        pairs = ", ".join(f"pins {a} and {b}" for a, b in duplicates)
        sys.exit(f"ERROR: byte-identical clips for {pairs}. One of each pair is "
                 f"showing the wrong drawing. A wrong drawing has shipped this "
                 f"way before; fix the Task Report or the heading match before "
                 f"rendering.")


if __name__ == "__main__":
    main()
