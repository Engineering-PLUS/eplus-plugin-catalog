#!/usr/bin/env python3
"""
inspect_stamp.py -- dump the structure of a Bluebeam stamp PDF.

Run this FIRST whenever a new stamp is added to the stamps folder. It tells
you whether the artwork is annotation-based or content-based, whether it is
raster or vector, what token fields exist, and the ink bounding box the
stamper will use as the annotation appearance /BBox.

  python inspect_stamp.py "../stamps/Exceptions As Noted.pdf"
"""
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stamp_pdf import REVIEW_STAMPS, WATERMARKS, ink_bbox  # noqa: E402


def main(path: str) -> int:
    name = os.path.basename(path)[:-4] if path.lower().endswith(".pdf") else path
    doc = pymupdf.open(path)
    page = doc[0]
    print("file        : %s" % path)
    print("pages       : %d" % len(doc))
    print("mediabox    : %s  rotation=%d" % (page.rect, page.rotation))

    if name in REVIEW_STAMPS:
        cls = "review stamp (single page, --stamp)"
    elif name in WATERMARKS:
        cls = "watermark (every page, --watermark)"
    else:
        cls = ("UNCLASSIFIED -- add it to REVIEW_STAMPS or WATERMARKS in "
               "stamp_pdf.py before using it")
    print("class       : %s" % cls)

    raw_len = len(page.get_text().strip())
    annots = list(page.annots() or [])
    print("annotations : %d" % len(annots))
    print("artwork lives in: %s"
          % ("ANNOTATIONS (must bake())" if annots else "page content stream"))

    tokens = []
    for a in annots:
        info = a.info or {}
        c = (info.get("content") or "").replace("\r", " | ")
        print("  - %-10s %-46s %s" % (a.type[1], str(a.rect), c[:70]))
        if "&[" in c:
            tokens.append(c)
    print("token fields: %s" % (tokens or "none"))

    baked = pymupdf.open(path)
    baked.bake()
    images = baked[0].get_images(full=True)
    box = ink_bbox(baked)
    print("ink bbox (baked): %s  -> %.0f x %.0f pt"
          % (box, box.width, box.height))
    print("rendering   : %s"
          % ("RASTER (%s) -- will soften when scaled up"
             % ", ".join("%dx%dpx" % (i[2], i[3]) for i in images)
             if images else "vector"))
    print("text chars  : raw=%d baked=%d" % (raw_len, len(baked[0].get_text().strip())))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_stamp.py <stamp.pdf>")
    raise SystemExit(main(sys.argv[1]))
