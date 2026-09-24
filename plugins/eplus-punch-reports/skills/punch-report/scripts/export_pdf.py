#!/usr/bin/env python3
"""
export_pdf.py -- produce a CONVENIENCE PDF of a rendered report, on request only.

The Word file is the file of record. The reviewer issues the report by exporting
it from Word, which recalculates every field. This script exists for the case
where the user asks for a PDF from the pipeline anyway (to read on a phone, to
forward a draft, to mark up in Bluebeam before the Word pass).

Why it is two passes. LibreOffice does not update fields on conversion and
paginates differently from Word, so a plain `soffice --convert-to pdf` ships a
table of contents whose page numbers are blank (that shipped once). This script
converts once to learn where LibreOffice put each item, writes those numbers
into the cached PAGEREF results of a scratch copy of the document, and converts
that copy. The numbers in the PDF therefore match the PDF, because both come
from the same renderer. The working .docx is never modified.

    python3 scripts/export_pdf.py build/<report>.docx            # -> build/<report>-convenience.pdf
    python3 scripts/export_pdf.py build/<report>.docx -o <path>

Deliver it only when asked: `package.py --pdf` places the newest PDF from
build/ beside the zip. Describe it to the user as a convenience copy whose page
numbers come from LibreOffice; the issued document is Word's export.

Needs a `soffice` binary on PATH (the sandbox has one; a Windows host may not)
and pymupdf. Never overwrites an existing PDF; it suffixes -2, -3.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HEADING_RE = re.compile(r"^\s*Item (\d+)\.", re.M)
# The renderer emits each TOC entry's page number as a compact PAGEREF field with
# no cached result, immediately after a "p. " run inside the entry's hyperlink.
FIELD_RE = re.compile(
    r'(<w:r>(?P<rpr><w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)<w:t xml:space="preserve">p\. </w:t></w:r>)'
    r'<w:r><w:fldChar w:fldCharType="begin"[^>]*/>'
    r'<w:instrText xml:space="preserve"> PAGEREF (?P<anchor>punchitem(?P<num>\d+)) \\h </w:instrText>'
    r'<w:fldChar w:fldCharType="end"/></w:r>',
    re.S,
)


def convert(docx, outdir):
    try:
        r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, docx],
                           capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        sys.exit("ERROR: soffice is not on PATH. A convenience PDF needs LibreOffice; "
                 "the reviewer's Word export is the issued PDF regardless.")
    hits = glob.glob(os.path.join(outdir, "*.pdf"))
    if not hits:
        sys.exit(f"ERROR: conversion produced no PDF.\n{r.stdout}\n{r.stderr}")
    return hits[0]


def page_map(pdf_path):
    """display number -> 1-based page of the item's heading, from the PDF text."""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    pages = {}
    for i in range(doc.page_count):
        text = doc[i].get_text()
        if "Table of Contents" in text:
            continue
        for m in HEADING_RE.finditer(text):
            n = int(m.group(1))
            line_end = text.find("\n", m.end())
            line = text[m.start():line_end if line_end > 0 else m.end() + 80]
            if "(continued)" in line:
                continue
            pages.setdefault(n, i + 1)
    total = doc.page_count
    doc.close()
    return pages, total


def patch_docx(src, dst, pages):
    """Copy src to dst with each TOC PAGEREF given a cached result run."""
    filled, missing = 0, []

    def repl(m):
        nonlocal filled
        n = int(m.group("num"))
        page = pages.get(n)
        if page is None:
            missing.append(n)
            return m.group(0)
        filled += 1
        rpr = m.group("rpr")
        anchor = m.group("anchor")
        return (m.group(1)
                + f'<w:r>{rpr}<w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
                + f'<w:r>{rpr}<w:instrText xml:space="preserve"> PAGEREF {anchor} \\h </w:instrText></w:r>'
                + f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r>'
                + f'<w:r>{rpr}<w:t>{page}</w:t></w:r>'
                + f'<w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>')

    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "word/document.xml":
                xml = data.decode("utf-8")
                xml = FIELD_RE.sub(repl, xml)
                data = xml.encode("utf-8")
            zout.writestr(info, data)
    return filled, missing


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
    ap.add_argument("docx")
    ap.add_argument("-o", "--out", default=None,
                    help="output PDF (default: <same folder>/<stem>-convenience.pdf)")
    ap.add_argument("--keep-scratch", action="store_true", help="leave the scratch folder for inspection")
    args = ap.parse_args()

    src = os.path.abspath(args.docx)
    if not os.path.isfile(src):
        sys.exit(f"ERROR: no such file: {src}")
    stem = os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(args.out) if args.out else os.path.join(os.path.dirname(src), f"{stem}-convenience.pdf")
    out = free_name(out)

    scratch = tempfile.mkdtemp(prefix="export_pdf_")
    try:
        first = convert(src, os.path.join(scratch, "pass1"))
        pages, total = page_map(first)
        patched = os.path.join(scratch, "pass2", os.path.basename(src))
        os.makedirs(os.path.dirname(patched), exist_ok=True)
        filled, missing = patch_docx(src, patched, pages)
        second = convert(patched, os.path.join(scratch, "pass2"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(second, out)
    finally:
        if args.keep_scratch:
            print(f"scratch kept  : {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)

    print(f"items located : {len(pages)} headings across {total} pages")
    print(f"TOC numbers   : {filled} filled" + (f", {len(missing)} not found for items {missing}" if missing else ""))
    print(f"wrote         : {out}")
    print("This is a CONVENIENCE copy: pagination and page numbers are LibreOffice's. The reviewer's "
          "Word export is the issued document. Deliver it only if the user asked (package.py --pdf).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
