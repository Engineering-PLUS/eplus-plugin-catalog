#!/usr/bin/env python3
"""
staple_pdf.py -- put a coversheet PDF in front of a report PDF.

The report body is rendered with a BLANK page 1 so its page numbers and its
"of N" count already allow for a cover. Stapling therefore REPLACES page 1 of
the body PDF with page 1 of the cover PDF; nothing shifts.

    python3 scripts/staple_pdf.py <cover.pdf> <body.pdf> [-o <out.pdf>]

Both inputs are PDFs the user already has: the cover from Word (theirs, or the
generated <report>-Cover.docx exported from Word) or from scripts/export_pdf.py,
and the body the same way. Offer this only after the user has approved both
files; it is a convenience, and the Word files remain the files of record.
Never overwrites; the output name is suffixed if taken.
"""
import argparse
import os
import sys


def free_name(path):
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}-{n}{ext}"):
        n += 1
    return f"{stem}-{n}{ext}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cover")
    ap.add_argument("body")
    ap.add_argument("-o", "--out", default=None, help="default: <body stem>-stapled.pdf beside the body")
    ap.add_argument("--keep-body-page-1", action="store_true",
                    help="insert the cover in front instead of replacing the body's page 1 "
                         "(only for a body rendered with cover_mode none)")
    args = ap.parse_args()

    import pymupdf
    for p in (args.cover, args.body):
        if not os.path.isfile(p):
            sys.exit(f"ERROR: no such file: {p}")
    cover = pymupdf.open(args.cover)
    body = pymupdf.open(args.body)
    if cover.page_count < 1 or body.page_count < 1:
        sys.exit("ERROR: an input has no pages")
    out = free_name(os.path.abspath(args.out) if args.out
                    else os.path.splitext(os.path.abspath(args.body))[0] + "-stapled.pdf")

    result = pymupdf.open()
    result.insert_pdf(cover, from_page=0, to_page=0)
    start = 0 if args.keep_body_page_1 else 1
    if start < body.page_count:
        result.insert_pdf(body, from_page=start, to_page=body.page_count - 1)
    result.save(out, garbage=3, deflate=True)
    replaced = "kept" if args.keep_body_page_1 else "replaced by the cover"
    print(f"cover  : {args.cover} (page 1 of {cover.page_count} used)")
    print(f"body   : {args.body} ({body.page_count} pages; page 1 {replaced})")
    print(f"wrote  : {out} ({result.page_count} pages)")
    print("The Word files remain the files of record; this PDF is the stapled copy the user asked for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
