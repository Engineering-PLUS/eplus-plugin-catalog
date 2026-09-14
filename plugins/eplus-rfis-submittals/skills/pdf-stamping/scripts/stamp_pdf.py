#!/usr/bin/env python3
"""
stamp_pdf.py -- apply EPLUS Bluebeam review stamps to a submittal PDF.

Output carries LIVE annotations, not flattened content: the review stamp is a
/Stamp annot whose appearance stream is the firm's stamp artwork, and the
comment block is a /FreeText annot. A reviewer can open the result in Bluebeam
and move the stamp or edit the comment text before issuing.

Key facts this script encodes (see ../reference/LESSONS-LEARNED.md):
  * The stamp PDFs are Bluebeam ANNOTATION stamps. Their artwork lives in
    /Annots appearance streams, NOT in the page content stream. A naive
    pypdf merge_page() produces a silently blank overlay. We call
    Document.bake() (PyMuPDF) to flatten annotations into page content, then
    re-wrap that content as a Form XObject to serve as our annot's /AP /N.
  * Bluebeam token fields such as "&[User]" / "&[Date]" are FreeText annots.
    They are substituted at apply-time by Bluebeam, so a file-level copy
    still contains the literal tokens. We capture those annots, drop them,
    bake, then re-draw real text in the same rect.
  * Stamp pages are full US Letter with the artwork in one corner. We compute
    the ink bounding box and use it as the Form XObject /BBox, so scale and
    position are controlled entirely by the annot /Rect.
  * House format (measured from a real issued response, see LESSONS-LEARNED
    section 6): review stamp 286 x 143 pt, comment box the SAME WIDTH directly
    beneath it with a 5 pt gap, red 1pt border, red Helvetica 6pt text.

Usage:
  # what goes where -- report only, writes nothing
  python3 stamp_pdf.py INPUT.pdf --stamp "Exceptions As Noted" \
      --comments-file comments.txt --stamp-page 3 --plan

  # apply
  python3 stamp_pdf.py INPUT.pdf \
      --watermark Draft \
      --stamp "Exceptions As Noted" --stamp-page 3 --stamp-fit auto \
      --comments-file comments.txt \
      --reviewer "<reviewer name>" --date 09/01/2026

  # many submittals in one process, one JSON result line per job
  python3 stamp_pdf.py --batch manifest.json [--plan] [--skip-existing]

Stamps are read from ../stamps relative to this script unless --stamps-dir
is given.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import inspect
import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover
    raise SystemExit(
        "PyMuPDF is not installed.\n"
        "  pip install pymupdf\n"
        "  (cloud container / Cowork: add --break-system-packages)")


def check_environment() -> None:
    """Fail loudly and early on an environment that cannot do the job.

    Capability checks, not a version number: the Cowork VM runs Python 3.10
    with whatever PyMuPDF pip resolves that day, and a missing feature here
    otherwise surfaces as a black border or a TypeError deep in a call stack.
    """
    if sys.version_info < (3, 9):
        raise SystemExit("needs Python 3.9+; this is %d.%d"
                         % sys.version_info[:2])
    problems = []
    if not hasattr(pymupdf.Document, "bake"):
        problems.append("Document.bake() is missing (PyMuPDF < 1.22). Annotation "
                        "stamps cannot be flattened, so every stamp would come "
                        "out blank.")
    try:
        params = inspect.signature(pymupdf.Page.add_freetext_annot).parameters
    except (TypeError, ValueError):  # pragma: no cover - C-implemented signature
        params = {}
    if params and "richtext" not in params:
        problems.append("Page.add_freetext_annot() has no `richtext` parameter "
                        "(PyMuPDF < 1.25). The comment box cannot be drawn.")
    if problems:
        raise SystemExit("PyMuPDF %s is too old:\n  - %s\n\nUpgrade:\n"
                         "  pip install --upgrade pymupdf\n"
                         "  (Cowork: add --break-system-packages)"
                         % (getattr(pymupdf, "__version__", "?"),
                            "\n  - ".join(problems)))


TOKEN_RE = re.compile(r"&\[(\w+)\]")

# Stamps fall into two classes and are NOT interchangeable. A review stamp is a
# boxed disposition block with a reviewer/date cell, applied to ONE page. A
# watermark is a diagonal mark with no reviewer cell, applied to EVERY page.
REVIEW_STAMPS = {
    "Exceptions As Noted",
    "For Information Only",
    "For Record",
    "No Exception",
    "Rejected (Resubmit)",
    "Review Required",
}
WATERMARKS = {"Draft", "For Reference Only"}

# The skill ships its stamps in ../stamps relative to this script.
DEFAULT_STAMPS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stamps"))

# House format, measured from an issued "EPLUS RESPONSE - <submittal> - <initials> COMMENTS.pdf"
HOUSE_STAMP_W = 286.3      # pt -- review stamp width as issued
HOUSE_MARGIN = 42.0        # pt -- from the page edges
HOUSE_GAP = 5.1            # pt -- between stamp bottom and comment box top
COMMENT_FONTSIZE = 6.0
# House red. --comment-color overrides it (text AND border) for reviewers who
# issue comments in another colour; see LESSONS-LEARNED section 12 for every
# place the colour has to be written.
DEFAULT_COMMENT_COLOR = "FF0000"
# The issued file declares 6.9pt leading / 3pt margin in its /DS. PyMuPDF's rich
# text layout actually renders at 1.2x fontsize leading with a 2pt inset, so the
# box-sizing math below uses the values PyMuPDF will really use -- otherwise the
# last line or two get clipped. The house numbers still go into /DS and /RC,
# which is what Bluebeam reads when someone edits the box.
COMMENT_LEADING = COMMENT_FONTSIZE * 1.2
COMMENT_MARGIN = 2.0
HOUSE_LEADING = 6.9
HOUSE_MARGIN_DS = 3.0


# --------------------------------------------------------------------------
# raster helpers (pure Python -- no numpy, so this runs on a bare PyMuPDF env)
# --------------------------------------------------------------------------
def _gray_samples(page: pymupdf.Page, dpi: int):
    """Return (samples, width, height, scale) for a grayscale render of a page."""
    pm = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    return pm.samples, pm.width, pm.height, dpi / 72.0


def ink_bbox(doc: pymupdf.Document, pno: int = 0, dpi: int = 100,
             thresh: int = 250) -> pymupdf.Rect:
    """Tight bounding box (MuPDF page coords) of everything drawn on a page."""
    page = doc[pno]
    samples, W, H, scale = _gray_samples(page, dpi)
    minx, miny, maxx, maxy = W, H, -1, -1
    for y in range(H):
        row = samples[y * W:(y + 1) * W]
        first = last = -1
        for x in range(W):
            if row[x] < thresh:
                first = x
                break
        if first < 0:
            continue
        for x in range(W - 1, first - 1, -1):
            if row[x] < thresh:
                last = x
                break
        if first < minx:
            minx = first
        if last > maxx:
            maxx = last
        if y < miny:
            miny = y
        maxy = y
    if maxx < 0:
        return page.rect
    return pymupdf.Rect(minx / scale, miny / scale,
                        (maxx + 1) / scale, (maxy + 1) / scale)


class InkMap:
    """Summed-area table over a page's ink mask, for O(1) region queries."""

    def __init__(self, page: pymupdf.Page, dpi: int = 50, thresh: int = 250):
        samples, W, H, scale = _gray_samples(page, dpi)
        self.W, self.H, self.scale = W, H, scale
        # sat[(y+1)*(W+1) + (x+1)] = count of ink pixels in [0..y] x [0..x]
        sat = [0] * ((W + 1) * (H + 1))
        for y in range(H):
            row = samples[y * W:(y + 1) * W]
            run = 0
            base = (y + 1) * (W + 1)
            prev = y * (W + 1)
            for x in range(W):
                if row[x] < thresh:
                    run += 1
                sat[base + x + 1] = sat[prev + x + 1] + run
        self.sat = sat
        self.total = sat[-1]

    def _clampi(self, v, hi):
        return 0 if v < 0 else (hi if v > hi else v)

    def count(self, rect: pymupdf.Rect) -> int:
        """Ink pixels inside a rect given in MuPDF page points."""
        x0 = self._clampi(int(rect.x0 * self.scale), self.W)
        x1 = self._clampi(int(rect.x1 * self.scale + 0.999), self.W)
        y0 = self._clampi(int(rect.y0 * self.scale), self.H)
        y1 = self._clampi(int(rect.y1 * self.scale + 0.999), self.H)
        if x1 <= x0 or y1 <= y0:
            return 0
        s, W1 = self.sat, self.W + 1
        return (s[y1 * W1 + x1] - s[y0 * W1 + x1]
                - s[y1 * W1 + x0] + s[y0 * W1 + x0])

    def is_blank(self, rect: pymupdf.Rect, tol: int = 0) -> bool:
        return self.count(rect) <= tol


# --------------------------------------------------------------------------
# stamp loading
# --------------------------------------------------------------------------
def load_stamp(path: str, tokens: dict[str, str] | None = None) -> pymupdf.Document:
    """Open a Bluebeam stamp PDF, substitute &[Token] fields, flatten to content."""
    doc = pymupdf.open(path)
    tokens = tokens or {}
    pending = []

    page = doc[0]
    for annot in list(page.annots() or []):
        content = (annot.info or {}).get("content", "")
        if content and TOKEN_RE.search(content):
            filled = TOKEN_RE.sub(
                lambda m: tokens.get(m.group(1), tokens.get(m.group(1).lower(), m.group(0))),
                content,
            )
            pending.append((pymupdf.Rect(annot.rect), filled))
            page.delete_annot(annot)

    doc.bake()  # <- the critical step: annotations -> page content

    page = doc[0]
    for rect, text in pending:
        # Bluebeam draws these cells as bold ~5pt black, centered.
        size = 5.0
        box = pymupdf.Rect(rect.x0, rect.y0 + (rect.height - size * 1.4) / 2,
                           rect.x1, rect.y1)
        leftover = page.insert_textbox(box, text, fontname="hebo", fontsize=size,
                                       color=(0, 0, 0), align=pymupdf.TEXT_ALIGN_CENTER)
        # PyMuPDF returns the unused height; NEGATIVE means the text did not
        # fit and nothing was drawn -- the cell would ship blank.
        if leftover < 0:
            raise SystemExit("token cell text %r does not fit its %.1f x %.1f pt "
                             "cell (short by %.1f pt); shorten the reviewer name "
                             "or date rather than shipping a blank cell"
                             % (text, box.width, box.height, -leftover))
    return doc


def stamp_residual_tokens(doc: pymupdf.Document) -> list[str]:
    """Any &[Token] still visible in the flattened stamp -- must be empty on output."""
    text = doc[0].get_text()
    return sorted(set(TOKEN_RE.findall(text)))


# --------------------------------------------------------------------------
# live-annotation plumbing
# --------------------------------------------------------------------------
def _form_xobject_from_stamp(doc: pymupdf.Document, stamp: pymupdf.Document,
                             clip: pymupdf.Rect) -> int:
    """Import a baked stamp page into `doc` as a Form XObject; return its xref.

    `clip` is the ink bbox in MuPDF page coords (y down from the top). The form
    /BBox must be in PDF user space (y up from the bottom), so we flip it
    against the source page height. Viewers map /BBox onto the annot /Rect, so
    the caller controls scale and position purely through the rect.
    """
    src_page = stamp[0]
    mb = src_page.mediabox
    height = mb.y1 - mb.y0
    bbox = (mb.x0 + clip.x0, mb.y0 + height - clip.y1,
            mb.x0 + clip.x1, mb.y0 + height - clip.y0)

    pno = doc.page_count
    doc.insert_pdf(stamp, from_page=0, to_page=0, annots=False)
    page = doc[pno]
    content = page.read_contents()
    res = doc.xref_get_key(page.xref, "Resources")

    xref = doc.get_new_xref()
    doc.update_object(xref, "<< /Type /XObject /Subtype /Form /FormType 1 "
                            "/BBox [ %g %g %g %g ] /Matrix [ 1 0 0 1 0 0 ] >>" % bbox)
    if res[0] != "null":
        doc.xref_set_key(xref, "Resources", res[1])
    doc.update_stream(xref, content, new=1, compress=1)

    doc.delete_page(pno)
    return xref


def _pdf_date(when: _dt.datetime) -> str:
    """PDF date string carrying the machine's real UTC offset, not a fixed zone."""
    if when.tzinfo is None:
        when = when.astimezone()
    off = when.utcoffset() or _dt.timedelta(0)
    total = int(off.total_seconds())
    sign = "-" if total < 0 else "+"
    total = abs(total)
    return (when.strftime("D:%Y%m%d%H%M%S")
            + "%s%02d'%02d'" % (sign, total // 3600, (total % 3600) // 60))


def add_stamp_annot(page: pymupdf.Page, form_xref: int, rect: pymupdf.Rect,
                    author: str, opacity: float | None = None,
                    subject: str = "Stamp") -> pymupdf.Annot:
    """Place a live /Stamp annot whose appearance is `form_xref`."""
    doc = page.parent
    annot = page.add_stamp_annot(rect, stamp=0)
    # add_stamp_annot squeezes the rect to the aspect ratio of the BUILT-IN
    # stamp it thinks it is drawing (~3.8:1), so a 2:1 review stamp comes out
    # half height. Put the rect back before swapping in the real appearance.
    annot.set_rect(rect)
    doc.xref_set_key(annot.xref, "AP/N", "%d 0 R" % form_xref)
    doc.xref_set_key(annot.xref, "Name", "/Stamp")
    doc.xref_set_key(annot.xref, "Subj", pymupdf.get_pdf_str(subject))
    doc.xref_set_key(annot.xref, "T", pymupdf.get_pdf_str(author))
    doc.xref_set_key(annot.xref, "C", "[ 1 0 0 ]")
    doc.xref_set_key(annot.xref, "F", "4")  # print
    now = _pdf_date(_dt.datetime.now())
    doc.xref_set_key(annot.xref, "CreationDate", pymupdf.get_pdf_str(now))
    doc.xref_set_key(annot.xref, "M", pymupdf.get_pdf_str(now))
    if opacity is not None and opacity < 1.0:
        doc.xref_set_key(annot.xref, "CA", "%g" % opacity)
    return annot


# --------------------------------------------------------------------------
# comment box
# --------------------------------------------------------------------------
def _wrap(text: str, width: float, font: pymupdf.Font, size: float) -> list[str]:
    """Greedy wrap honouring explicit newlines; returns display lines."""
    lines = []
    for para in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if font.text_length(trial, size) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def comment_lines(text: str, width: float) -> list[str]:
    font = pymupdf.Font("helv")
    return _wrap(text, width - 2 * COMMENT_MARGIN, font, COMMENT_FONTSIZE)


def comment_box_height(text: str, width: float) -> float:
    """Height the comment box needs to hold `text` at `width`.

    Two spare lines: one is consumed by the <div> wrapper's leading offset (see
    _rich_html), the other is slack because PyMuPDF's wrapper breaks on
    slightly different boundaries than ours on long unbroken tokens. A clipped
    last line is a silent defect on an issued document.
    """
    return (len(comment_lines(text, width)) + 2) * COMMENT_LEADING + 2 * COMMENT_MARGIN


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def parse_color(value: str) -> str:
    """Normalise a user colour ('8000FF', '#8000ff') to six upper-case hex digits."""
    m = _HEX_RE.match((value or "").strip())
    if not m:
        raise SystemExit("--comment-color must be a six-digit hex colour such as "
                         "FF0000 or #8000FF, got %r" % value)
    return m.group(1).upper()


def _rgb(hex6: str) -> tuple:
    """'8000FF' -> (0.502, 0.0, 1.0), the 0-1 floats PDF operators take."""
    return tuple(round(int(hex6[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4))


def _pdf_rgb(hex6: str) -> str:
    return "%g %g %g" % _rgb(hex6)


def _rich_html(text: str) -> str:
    """Body HTML handed to PyMuPDF's rich-text layout.

    Wrapped in a <div>: PyMuPDF splices the caller's HTML into an indented
    template, and without a block element that template's own leading
    whitespace renders as literal spaces in front of the first line. The <div>
    costs about one line of top offset, which comment_box_height accounts for.
    """
    body = "<br>".join(_esc(line) or "&#160;"
                       for line in text.replace("\r\n", "\n").split("\n"))
    return "<div>" + body + "</div>"


_TM_RE = re.compile(rb"1 0 0 -1 [-\d.]+ ([-\d.]+) Tm")


def verify_comment_fit(annot: pymupdf.Annot) -> bool:
    """True if every laid-out line of the box clears its bottom edge.

    Reads the appearance stream rather than the rendered pixels: text sits only
    a couple of points above the border, so a raster probe cannot separate the
    last legitimate line from an overflowing one. The stream is unambiguous --
    one TJ per line, first baseline in the Tm, `leading` between them.
    """
    doc = annot.parent.parent
    ap = doc.xref_get_key(annot.xref, "AP/N")
    if ap[0] != "xref":
        return True
    stream = doc.xref_stream(int(ap[1].split()[0]))
    m = _TM_RE.search(stream)
    lines = stream.count(b"TJ")
    if not m or not lines:
        return True
    last_baseline = float(m.group(1)) + (lines - 1) * COMMENT_LEADING
    descent = COMMENT_FONTSIZE * 0.25
    return last_baseline + descent <= annot.rect.height - COMMENT_MARGIN


def _rich_content(text: str, color: str = DEFAULT_COMMENT_COLOR) -> str:
    """Bluebeam-style /RC so the box stays styled when edited in Revu."""
    style = ("font:Helvetica %gpt; text-align:left; margin:%gpt; "
             "line-height:%gpt; color:#%s"
             % (COMMENT_FONTSIZE, HOUSE_MARGIN_DS, HOUSE_LEADING, color))
    paras = "".join(
        '<p style="line-height:%gpt; font-size:%gpt">%s</p>'
        % (HOUSE_LEADING, COMMENT_FONTSIZE, _esc(line) or "&#160;")
        for line in text.replace("\r\n", "\n").split("\n")
    )
    return ('<?xml version="1.0"?><body xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"'
            ' xfa:contentType="text/html" xfa:APIVersion="EPLUS:stamp_pdf"'
            ' xfa:spec="2.2.0" style="%s" xmlns="http://www.w3.org/1999/xhtml">%s</body>'
            % (style, paras))


def add_comment_box(page: pymupdf.Page, rect: pymupdf.Rect, text: str,
                    author: str, fill: bool = True,
                    color: str = DEFAULT_COMMENT_COLOR) -> pymupdf.Annot:
    """Place the live EPLUS comment box, text and border in `color` (hex6).

    PyMuPDF only honours `border_color` in rich-text mode, and even then it
    writes a black stroke into the appearance stream. We draw through it and
    patch the one stroke-colour operator -- see LESSONS-LEARNED section 7.
    """
    doc = page.parent
    annot = page.add_freetext_annot(
        rect, _rich_html(text),
        fontsize=COMMENT_FONTSIZE, fontname="Helv",
        text_color=_rgb(color),
        fill_color=(1.0, 1.0, 1.0) if fill else None,
        border_width=1.0, align=pymupdf.TEXT_ALIGN_LEFT, richtext=True,
        style="font-family:Helvetica; font-size:%gpx; color:#%s; text-align:left"
              % (COMMENT_FONTSIZE, color),
    )

    ap = doc.xref_get_key(annot.xref, "AP/N")
    if ap[0] == "xref":
        ap_xref = int(ap[1].split()[0])
        stream = doc.xref_stream(ap_xref)
        if b"0 0 0 RG" in stream:
            doc.update_stream(ap_xref, stream.replace(
                b"0 0 0 RG", (_pdf_rgb(color) + " RG").encode("ascii"), 1))
        else:
            sys.stderr.write("warning: comment box border stroke not found in the "
                             "appearance stream -- the border may render black\n")

    doc.xref_set_key(annot.xref, "CL", "null")  # PyMuPDF leaves a stray callout
    doc.xref_set_key(annot.xref, "Contents", pymupdf.get_pdf_str(text))
    doc.xref_set_key(annot.xref, "Subj", pymupdf.get_pdf_str("Text Box"))
    doc.xref_set_key(annot.xref, "T", pymupdf.get_pdf_str(author))
    doc.xref_set_key(annot.xref, "C", "[ 1 1 1 ]" if fill else "[ ]")
    doc.xref_set_key(annot.xref, "F", "4")
    doc.xref_set_key(annot.xref, "DA", pymupdf.get_pdf_str(
        "%s rg /Helv %g Tf" % (_pdf_rgb(color), COMMENT_FONTSIZE)))
    doc.xref_set_key(annot.xref, "DS", pymupdf.get_pdf_str(
        "font: Helvetica %gpt; text-align:left; margin:%gpt; line-height:%gpt; color:#%s"
        % (COMMENT_FONTSIZE, HOUSE_MARGIN_DS, HOUSE_LEADING, color)))
    doc.xref_set_key(annot.xref, "RC", pymupdf.get_pdf_str(_rich_content(text, color)))
    now = _pdf_date(_dt.datetime.now())
    doc.xref_set_key(annot.xref, "CreationDate", pymupdf.get_pdf_str(now))
    doc.xref_set_key(annot.xref, "M", pymupdf.get_pdf_str(now))
    return annot


# --------------------------------------------------------------------------
# placement
# --------------------------------------------------------------------------
ANCHORS = ("top-left", "top-right", "bottom-left", "bottom-right")


def anchor_rect(page_rect: pymupdf.Rect, w: float, h: float, anchor: str,
                margin: float = HOUSE_MARGIN) -> pymupdf.Rect:
    if anchor.endswith("left"):
        x0 = page_rect.x0 + margin
    else:
        x0 = page_rect.x1 - margin - w
    if anchor.startswith("top"):
        y0 = page_rect.y0 + margin
    else:
        y0 = page_rect.y1 - margin - h
    return pymupdf.Rect(x0, y0, x0 + w, y0 + h)


def find_blank(inkmap: InkMap, page_rect: pymupdf.Rect, w: float, h: float,
               margin: float = HOUSE_MARGIN, step: float = 6.0,
               tol: int = 0, bias: str = "top") -> pymupdf.Rect | None:
    """Leftmost fully blank w x h rect inside the margins.

    `bias` picks which end of the page to scan from: "top" reproduces the house
    placement (the issued example puts the stamp top-left), "bottom" prefers the
    footer margin, which is usually the free space on a framed drawing sheet.
    """
    x_lo, x_hi = page_rect.x0 + margin, page_rect.x1 - margin - w
    y_lo, y_hi = page_rect.y0 + margin, page_rect.y1 - margin - h
    if x_hi < x_lo or y_hi < y_lo:
        return None
    ys = []
    y = y_lo
    while y <= y_hi:
        ys.append(y)
        y += step
    if bias == "bottom":
        ys.reverse()
    for y in ys:
        x = x_lo
        while x <= x_hi:
            r = pymupdf.Rect(x, y, x + w, y + h)
            if inkmap.is_blank(r, tol):
                return r
            x += step
    return None


def plan_placement(page: pymupdf.Page, block_w: float, block_h: float,
                   scales=(1.0, 0.85, 0.7)) -> dict:
    """Evaluate where the stamp+comment block can go. Never writes anything.

    Returns a dict with a ranked candidate list. A candidate is `clean` when it
    sits entirely on blank paper. When nothing is clean the caller must ASK the
    user before covering content -- see SKILL.md.
    """
    inkmap = InkMap(page)
    page_rect = page.rect
    px_per_pt = inkmap.scale ** 2
    candidates = []

    for scale in scales:
        w, h = block_w * scale, block_h * scale
        if w > page_rect.width or h > page_rect.height:
            continue
        for bias in ("top", "bottom"):
            blank = find_blank(inkmap, page_rect, w, h, bias=bias)
            if blank is not None:
                candidates.append({
                    "anchor": "auto-blank:" + bias, "scale": scale,
                    "rect": [round(v, 1) for v in blank],
                    "clean": True, "covers_ink_pct": 0.0,
                })
        for anchor in ANCHORS:
            r = anchor_rect(page_rect, w, h, anchor)
            covered = inkmap.count(r)
            candidates.append({
                "anchor": anchor, "scale": scale,
                "rect": [round(v, 1) for v in r],
                "clean": covered == 0,
                "covers_ink_pct": round(100.0 * covered / max(1.0, w * h * px_per_pt), 2),
            })

    # clean first, then least ink covered, then largest scale.
    candidates.sort(key=lambda c: (not c["clean"], c["covers_ink_pct"], -c["scale"]))
    return {
        "page_size": [round(page_rect.width, 1), round(page_rect.height, 1)],
        "block_size": [round(block_w, 1), round(block_h, 1)],
        "page_ink_pct": round(100.0 * inkmap.total / max(1, inkmap.W * inkmap.H), 2),
        "clean_placement_exists": any(c["clean"] for c in candidates),
        "candidates": candidates[:8],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
class JobError(Exception):
    """A refusal or bad input for one stamping job.

    Single-file runs turn it into SystemExit with the same message; batch runs
    record it against the job and carry on with the next one.
    """

    def __init__(self, message: str, candidates=None):
        super().__init__(message)
        self.candidates = candidates


# Every per-job setting, with the CLI default. A batch manifest may set any of
# these in its "defaults" block or per job (hyphens or underscores).
JOB_DEFAULTS = {
    "input": None,
    "stamps_dir": DEFAULT_STAMPS_DIR,
    "watermark": None,
    "watermark_scale": 0.55,
    "watermark_opacity": 1.0,
    "stamp": None,
    "stamp_page": 1,
    "stamp_fit": "auto",
    "stamp_scale": 1.0,
    "blank_bias": "top",
    "stamp_width": HOUSE_STAMP_W,
    "comments": None,
    "comments_file": None,
    "comment_fill": "white",
    "comment_color": DEFAULT_COMMENT_COLOR,
    "allow_overlap": False,
    "reviewer": None,
    "date": None,
    "prefix": "EPLUS RESPONSE - ",
    "out_dir": None,
    "out": None,
}


def _read_comments(job: dict) -> str | None:
    if job["comments_file"]:
        with open(job["comments_file"], encoding="utf-8") as fh:
            return fh.read().rstrip("\n")
    return job["comments"]


def _stamp_path(stamps_dir: str, name: str) -> str:
    path = os.path.join(stamps_dir, name + ".pdf")
    if not os.path.exists(path):
        available = sorted(f[:-4] for f in os.listdir(stamps_dir)
                           if f.lower().endswith(".pdf"))
        raise JobError("stamp %r not found in %s\navailable: %s"
                       % (name, stamps_dir, ", ".join(available)))
    return path


class StampCache:
    """Baked stamp documents and their ink boxes, shared across batch jobs.

    load_stamp() bakes the Bluebeam file and ink_bbox() walks ~1M pixels in pure
    Python; both depend only on the stamp and its token values, so a batch of
    thirty submittals pays for them once per stamp instead of twice per file.
    """

    def __init__(self):
        self._docs = {}

    def get(self, stamps_dir: str, name: str, tokens: dict | None = None):
        key = (stamps_dir, name, tuple(sorted((tokens or {}).items())))
        if key not in self._docs:
            doc = load_stamp(_stamp_path(stamps_dir, name), tokens)
            self._docs[key] = (doc, ink_bbox(doc))
        return self._docs[key]

    def close(self):
        for doc, _ in self._docs.values():
            doc.close()
        self._docs.clear()


def _output_path(job: dict) -> str:
    if job["out"]:
        return job["out"]
    base = os.path.basename(job["input"])
    out_dir = job["out_dir"] or os.path.dirname(os.path.abspath(job["input"]))
    return os.path.join(out_dir, job["prefix"] + base)


def run_job(job: dict, cache: StampCache, plan: bool = False) -> dict:
    """Stamp one submittal (or plan it). Returns a result dict; raises JobError."""
    if job["stamp"] and job["stamp"] in WATERMARKS:
        raise JobError("%r is a watermark, not a review stamp -- pass it as "
                       "--watermark. Review stamps: %s"
                       % (job["stamp"], ", ".join(sorted(REVIEW_STAMPS))))
    if job["watermark"] and job["watermark"] in REVIEW_STAMPS:
        raise JobError("%r is a review stamp, not a watermark -- pass it as "
                       "--stamp. Watermarks: %s"
                       % (job["watermark"], ", ".join(sorted(WATERMARKS))))
    if not job["input"]:
        raise JobError("no input PDF given")
    if not job["stamp"] and not job["watermark"]:
        raise JobError("nothing to do: pass --stamp and/or --watermark")
    if job["comments"] and job["comments_file"]:
        raise JobError("pass --comments or --comments-file, not both")
    if (job["comments"] or job["comments_file"]) and not job["stamp"]:
        raise JobError("--comments needs --stamp (the box hangs off the stamp)")

    color = parse_color(job["comment_color"])
    reviewer = job["reviewer"]
    date = job["date"] or _dt.date.today().strftime("%m/%d/%Y")
    comments = _read_comments(job)
    result = {"input": job["input"], "warnings": []}

    doc = pymupdf.open(job["input"])
    try:
        # ---- geometry of the stamp + comment block -----------------------
        stamp_rect_size = None
        block_w = block_h = 0.0
        if job["stamp"]:
            _, pbox = cache.get(job["stamps_dir"], job["stamp"],
                                {"User": reviewer or "", "Date": date})
            sw = job["stamp_width"] * job["stamp_scale"]
            sh = sw * pbox.height / pbox.width
            stamp_rect_size = (sw, sh)
            block_w, block_h = sw, sh
            if comments:
                block_h += HOUSE_GAP + comment_box_height(comments, sw)

        # ---- planning mode -----------------------------------------------
        if plan:
            if not job["stamp"]:
                raise JobError("--plan needs --stamp")
            if not (1 <= job["stamp_page"] <= doc.page_count):
                raise JobError("--stamp-page %d out of range (1-%d)"
                               % (job["stamp_page"], doc.page_count))
            report = plan_placement(doc[job["stamp_page"] - 1], block_w, block_h)
            report["stamp"] = job["stamp"]
            report["stamp_page"] = job["stamp_page"]
            report["comment_lines"] = (len(comments.split("\n")) if comments else 0)
            result["plan"] = report
            return result

        if job["stamp"] and not reviewer:
            raise JobError("--reviewer is required: the stamp's &[User] cell would "
                           "otherwise ship with the raw Bluebeam token visible")

        out = _output_path(job)
        if os.path.abspath(out) == os.path.abspath(job["input"]):
            raise JobError("refusing to overwrite the original submittal")

        author = reviewer or "Engineering PLUS"

        # ---- watermark, every page, FIRST so the review stamp can't land on it
        if job["watermark"]:
            wm, wbox = cache.get(job["stamps_dir"], job["watermark"])
            wm_xref = _form_xobject_from_stamp(doc, wm, wbox)
            for page in doc:
                w = page.rect.width * job["watermark_scale"]
                h = w * wbox.height / wbox.width
                if h > page.rect.height * 0.9:
                    h = page.rect.height * 0.9
                    w = h * wbox.width / wbox.height
                rect = pymupdf.Rect(0, 0, w, h)
                rect += (page.rect.width / 2 - w / 2, page.rect.height / 2 - h / 2) * 2
                add_stamp_annot(page, wm_xref, rect, author,
                                opacity=job["watermark_opacity"], subject="Watermark")

        # ---- review stamp + comment block --------------------------------
        if job["stamp"]:
            if not (1 <= job["stamp_page"] <= doc.page_count):
                raise JobError("--stamp-page %d out of range (1-%d)"
                               % (job["stamp_page"], doc.page_count))
            stamp, sbox = cache.get(job["stamps_dir"], job["stamp"],
                                    {"User": reviewer, "Date": date})
            residual = stamp_residual_tokens(stamp)
            if residual:
                raise JobError("stamp still contains unfilled Bluebeam tokens: %s"
                               % ", ".join("&[%s]" % t for t in residual))
            sw, sh = stamp_rect_size

            # Build the XObject BEFORE taking a Page handle: insert_pdf/delete_page
            # inside the helper reshuffles the page tree and orphans live Page
            # objects (page.parent goes None).
            st_xref = _form_xobject_from_stamp(doc, stamp, sbox)

            page = doc[job["stamp_page"] - 1]
            inkmap = InkMap(page)
            if job["stamp_fit"] == "auto":
                block = find_blank(inkmap, page.rect, block_w, block_h,
                                   bias=job["blank_bias"])
                if block is None:
                    report = plan_placement(page, block_w, block_h)
                    raise JobError(
                        "no blank %.0fx%.0fpt area on page %d for the stamp%s. "
                        "Refusing to guess. Pick a placement with --stamp-fit, "
                        "shrink with --stamp-scale, or re-run with --allow-overlap "
                        "once the user has chosen a spot."
                        % (block_w, block_h, job["stamp_page"],
                           " + comment block" if comments else ""),
                        candidates=report["candidates"][:4])
            else:
                if job["stamp_fit"] not in ANCHORS:
                    raise JobError("stamp_fit must be auto or one of %s, got %r"
                                   % (", ".join(ANCHORS), job["stamp_fit"]))
                block = anchor_rect(page.rect, block_w, block_h, job["stamp_fit"])
                covered = inkmap.count(block)
                if covered and not job["allow_overlap"]:
                    raise JobError(
                        "--stamp-fit %s covers page content on page %d. Re-run with "
                        "--allow-overlap only after the user has approved covering it "
                        "(--comment-fill white hides what is underneath)."
                        % (job["stamp_fit"], job["stamp_page"]))

            srect = pymupdf.Rect(block.x0, block.y0, block.x0 + sw, block.y0 + sh)
            add_stamp_annot(page, st_xref, srect, author)

            if comments:
                ch = comment_box_height(comments, sw)
                crect = pymupdf.Rect(block.x0, srect.y1 + HOUSE_GAP,
                                     block.x0 + sw, srect.y1 + HOUSE_GAP + ch)
                cannot = add_comment_box(page, crect, comments, author,
                                         fill=(job["comment_fill"] == "white"),
                                         color=color)
                if not verify_comment_fit(cannot):
                    result["warnings"].append(
                        "comment text reaches the bottom border of the box -- "
                        "it may be clipped. Shorten the comments or widen the block, "
                        "and check the rendered page before issuing.")
            result.update(stamp=job["stamp"], stamp_page=job["stamp_page"],
                          rect=[round(v, 1) for v in block])

        # ---- write -------------------------------------------------------
        doc.save(out, garbage=3, deflate=True)
        result["out"] = out
        return result
    finally:
        doc.close()


def _normalise_keys(entry: dict, where: str) -> dict:
    job = {}
    for key, value in entry.items():
        k = key.replace("-", "_")
        if k not in JOB_DEFAULTS:
            raise JobError("%s: unknown setting %r (known: %s)"
                           % (where, key, ", ".join(sorted(JOB_DEFAULTS))))
        job[k] = value
    return job


def _load_manifest(path: str, base: dict) -> list:
    """Expand a batch manifest into complete job dicts.

    Shape: {"defaults": {...}, "jobs": [{...}, ...]} or a bare list of jobs.
    Precedence per setting: job > manifest defaults > command line. Relative
    paths (input, comments_file, out, out_dir, stamps_dir) resolve against
    the manifest's own folder.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        data = {"jobs": data}
    root = os.path.dirname(os.path.abspath(path))
    defaults = _normalise_keys(data.get("defaults") or {}, "defaults")
    jobs = []
    for i, entry in enumerate(data.get("jobs") or [], 1):
        job = dict(base)
        job.update(defaults)
        try:
            job.update(_normalise_keys(entry, "job %d" % i))
        except JobError as exc:
            job["_error"] = str(exc)
        for k in ("input", "comments_file", "out", "out_dir", "stamps_dir"):
            if job.get(k) and not os.path.isabs(job[k]):
                job[k] = os.path.join(root, job[k])
        jobs.append(job)
    if not jobs:
        raise SystemExit("manifest %s has no jobs" % path)
    return jobs


def _emit(record: dict) -> None:
    print(json.dumps(record), flush=True)


def run_batch(jobs: list, plan: bool, skip_existing: bool) -> int:
    """One JSON line per job as it finishes, then a summary line.

    Lines are flushed as they are written, so a run cut off by a tool timeout
    still leaves a record of what finished; re-run with --skip-existing to
    pick up where it stopped.
    """
    cache = StampCache()
    counts = {"ok": 0, "planned": 0, "skipped": 0, "failed": 0}
    try:
        for i, job in enumerate(jobs, 1):
            record = {"job": i, "input": job.get("input")}
            if job.get("_error"):
                record.update(status="failed", error=job["_error"])
            elif not plan and skip_existing and job.get("input") \
                    and os.path.exists(_output_path(job)):
                record.update(status="skipped", out=_output_path(job))
            else:
                try:
                    result = run_job(job, cache, plan=plan)
                    record.update(result)
                    record["status"] = "planned" if plan else "ok"
                except JobError as exc:
                    record.update(status="failed", error=str(exc))
                    if exc.candidates:
                        record["candidates"] = exc.candidates
                except SystemExit as exc:  # parse_color and friends
                    record.update(status="failed", error=str(exc))
                except Exception as exc:  # one bad PDF must not sink the batch
                    record.update(status="failed",
                                  error="%s: %s" % (type(exc).__name__, exc))
            counts[record["status"]] += 1
            _emit(record)
    finally:
        cache.close()
    _emit({"summary": counts, "jobs": len(jobs)})
    return 1 if counts["failed"] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default=None,
                    help="submittal PDF (omit when using --batch)")
    ap.add_argument("--batch", default=None, metavar="MANIFEST.json",
                    help="stamp many submittals in one process; see the manifest "
                         "format in SKILL.md. Writes one JSON line per job")
    ap.add_argument("--skip-existing", action="store_true",
                    help="batch only: skip jobs whose output file already exists "
                         "(resume a run that was cut off)")
    ap.add_argument("--stamps-dir", default=DEFAULT_STAMPS_DIR,
                    help="folder holding the stamp PDFs (default: the skill's "
                         "stamps/ folder next to this script)")
    ap.add_argument("--watermark", default=None,
                    help="watermark stamp applied to EVERY page (Draft, For Reference Only)")
    ap.add_argument("--watermark-scale", type=float, default=0.55,
                    help="fraction of page width")
    ap.add_argument("--watermark-opacity", type=float, default=1.0,
                    help="0-1; extra /CA applied ON TOP of whatever transparency "
                         "the stamp file itself declares. Default 1.0 honours the "
                         "stamp as authored -- Draft.pdf is already 40%% grey, and "
                         "dialling this down as well compounds the two")
    ap.add_argument("--stamp", default=None, help="review stamp, single page")
    ap.add_argument("--stamp-page", type=int, default=1, help="1-based")
    ap.add_argument("--stamp-fit", default="auto",
                    choices=("auto",) + ANCHORS,
                    help="auto = first fully blank spot; otherwise a fixed corner")
    ap.add_argument("--stamp-scale", type=float, default=1.0)
    ap.add_argument("--blank-bias", default="top", choices=("top", "bottom"),
                    help="which end of the page --stamp-fit auto searches from")
    ap.add_argument("--stamp-width", type=float, default=HOUSE_STAMP_W,
                    help="issued width of the review stamp in pt")
    ap.add_argument("--comments", default=None,
                    help="EPLUS comment block text, placed beneath the stamp")
    ap.add_argument("--comments-file", default=None)
    ap.add_argument("--comment-fill", default="white", choices=("white", "none"),
                    help="'white' hides page content beneath the box -- last resort "
                         "when the block cannot sit on blank paper")
    ap.add_argument("--comment-color", default=DEFAULT_COMMENT_COLOR,
                    help="hex colour for the comment text and border (default "
                         "FF0000, the house red); the review stamp is unaffected")
    ap.add_argument("--allow-overlap", action="store_true",
                    help="permit a placement that covers page content; without this "
                         "the script refuses and tells you to re-plan")
    ap.add_argument("--reviewer", default=None, help="fills &[User]")
    ap.add_argument("--date", default=None, help="fills &[Date] (default: today, MM/DD/YYYY)")
    ap.add_argument("--plan", action="store_true",
                    help="report candidate placements as JSON and exit; writes nothing")
    ap.add_argument("--prefix", default="EPLUS RESPONSE - ")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--out", default=None, help="explicit output path")
    args = ap.parse_args(argv)
    check_environment()

    base = {k: getattr(args, k) for k in JOB_DEFAULTS}
    parse_color(base["comment_color"])  # fail on a bad colour before any work

    if args.batch:
        if args.input:
            raise SystemExit("pass an input PDF or --batch, not both")
        if args.out:
            raise SystemExit("--out names one file; give each batch job its own out")
        return run_batch(_load_manifest(args.batch, base), args.plan,
                         args.skip_existing)
    if not args.input:
        raise SystemExit("no input PDF given (or pass --batch MANIFEST.json)")

    cache = StampCache()
    try:
        result = run_job(base, cache, plan=args.plan)
    except JobError as exc:
        if exc.candidates:
            sys.stderr.write("Candidate placements:\n%s\n"
                             % json.dumps(exc.candidates, indent=2))
        raise SystemExit(str(exc))
    finally:
        cache.close()
    for w in result["warnings"]:
        sys.stderr.write("warning: %s\n" % w)
    if args.plan:
        print(json.dumps(result["plan"], indent=2))
    else:
        print(result["out"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
