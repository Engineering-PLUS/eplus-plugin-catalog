# Lessons learned — EPLUS PDF stamping

Written while building and testing `stamp_pdf.py`. These are the things that
cost time, so the next session doesn't rediscover them. Sections 1–5 come from
the original 2026-09-01 scaffold session; 6–11 from the live-annotation
rebuild.

## 1. The stamps are annotation stamps, and that breaks the obvious approach

Every file in `stamps/` was authored in **Bluebeam Revu**. The visible artwork
is stored in `/Annots` appearance streams attached to the page — the page
*content stream* is essentially empty.

Consequence: the standard watermarking recipe

```python
# WRONG for these files — produces a silently blank overlay
from pypdf import PdfReader, PdfWriter
page.merge_page(stamp_reader.pages[0])
```

runs without error and writes a valid PDF **with no stamp on it**. Same for
PyMuPDF's `show_pdf_page()` used directly on the stamp document. The first
attempt in the original session did exactly this and the failure was invisible
until the output was rendered to PNG and looked at.

**Fix:** flatten annotations into page content with `Document.bake()` before
doing anything else with a stamp.

**Rule for future sessions: always render the output and look at it.** A PDF
that opens fine is not evidence the stamp landed.

## 2. Bluebeam token fields are literal text in the file

`Exceptions As Noted.pdf` contains a FreeText annotation whose content is the
literal string `&[User] &[Date]`. Bluebeam substitutes those at *apply* time
inside Revu; a copy of the stamp file on disk still has the raw tokens, and
`bake()` bakes the tokens in as-is.

Handled in `stamp_pdf.py::load_stamp()`: find FreeText annots matching
`&\[(\w+)\]`, record rect + substituted text, delete the annot, `bake()`, then
re-draw the real text into the same rect with `insert_textbox(..., align=CENTER)`.
The cell renders as Arial-Bold 5pt black — matched with the base-14 `hebo`
(Helvetica-Bold), which is visually indistinguishable at 5pt.

Known token fields: `&[User]`, `&[Date]`. If Bluebeam stamps later add
`&[Company]`, `&[Time]`, `&[Project]` etc., they need no code change — just add
the key to the `tokens` dict. `stamp_residual_tokens()` re-reads the flattened
stamp and aborts the run if any token survived, so an unfilled cell can never
reach an issued document.

## 3. Stamp pages are full US Letter; the artwork is not

Each stamp is a 612x792 page with the graphic parked in one corner. Compositing
the page 1:1 puts the stamp wherever the author happened to leave it.

Fix: `ink_bbox()` rasterizes at 100 dpi, finds all non-white pixels, and returns
the tight box. That box becomes the appearance stream's `/BBox`, so the viewer
maps it onto the annotation `/Rect` — scale and position are the caller's.

Measured, and what `inspect_stamp.py` reports today:

| stamp                | class        | ink (pt)  | rendering | token cell |
|----------------------|--------------|-----------|-----------|------------|
| Exceptions As Noted  | review stamp | 215 x 108 | vector    | yes        |
| For Information Only | review stamp | 215 x 108 | vector +  | yes        |
|                      |              |           | 750dpi logo |          |
| For Record           | review stamp | 215 x 108 | vector    | yes        |
| No Exception         | review stamp | 215 x 108 | vector    | yes        |
| Rejected (Resubmit)  | review stamp | 215 x 108 | vector    | yes        |
| Review Required      | review stamp | 215 x 108 | vector    | yes        |
| Draft                | watermark    | 145 x 153 | vector    | no         |
| For Reference Only   | watermark    | 502 x 523 | vector    | no         |

`inspect_stamp.py` flags `For Information Only` as RASTER because it embeds the
EP logo as a 675x450 px image. That is not a problem: the logo occupies only
65 x 31 pt, so it lands at ~750 dpi. Read that check with the placed size in
mind, not the pixel count alone — `Draft` was a real problem at 286 px across
148 pt, this one is not.

`Draft.pdf` was a 286x286 px raster until 2026-09-01; re-saving it out of
Bluebeam did **not** help, because the artwork was an image *stamp* and a
resave just rewrites the container around the same PNG (identical SHA-1, same
xref, same 1831 bytes). The stamp owner re-authored it as a Bluebeam text box — Arial
Black, #969696, 40% opacity — and `inspect_stamp.py` now reports it as vector.
Every stamp's artwork is vector today. If a new stamp reports RASTER at a low
placed dpi, that is the fix to ask for.

The two classes are **not interchangeable** and `stamp_pdf.py` refuses to swap
them: a review stamp is a disposition block for one page, a watermark is a
diagonal mark for every page.

## 4. "Where it fits" needs an actual whitespace search

`InkMap` rasterizes the target page at 50 dpi and builds a summed-area table of
the ink mask, so `count(rect)` is O(1) and `find_blank()` can test thousands of
candidate positions cheaply.

**Order matters:** apply the all-pages watermark *first*, then run the blank
search for the review stamp. The watermark then counts as ink and the review
stamp will never be placed on top of it. This is not incidental — it is the
whole reason the two operations are sequenced the way they are in `main()`.

`find_blank()` takes a `bias`: `top` reproduces the house placement (the issued
example is top-left), `bottom` prefers the footer margin, which is usually
where a framed drawing sheet has room. Neither is right for every sheet — that
is why `--plan` exists.

## 5. Environment

- `pymupdf` (imports as `pymupdf`; `fitz` is the deprecated alias) does all of
  the work: bake, ink bbox, blank search, XObject plumbing, annotations.
- **No numpy.** The original scaffold used it for the summed-area table; that
  made the script unrunnable on a stock PyMuPDF install. `InkMap` is pure
  Python and fast enough at 50 dpi.
- `pypdf` alone is **not sufficient** (no annotation flattening).
- `pdftoppm` (poppler-utils) is handy for eyeballing output, but PyMuPDF's own
  `page.get_pixmap().save()` does the same thing with no extra dependency.
- **Target environment: the Cowork VM — Python 3.10.12 at `/usr/bin/python3`,
  pip 25.3, and system package management that requires
  `pip install pymupdf --break-system-packages`.** The scripts are written to
  3.9 syntax and verified against the 3.9 and 3.10 grammars; nothing newer is
  used.
- PyMuPDF floor is **1.25** — `Page.add_freetext_annot()` gained `richtext`
  there, and the comment box cannot be drawn without it. `Document.bake()`
  needs >= 1.22. `check_environment()` tests for both *capabilities* at
  startup rather than parsing a version string, and prints the pip command to
  fix it. Without that check a stale PyMuPDF fails as a black border or a
  TypeError several frames deep.

## 6. The house response format, measured

From an issued `EPLUS RESPONSE - <submittal> - <reviewer initials> COMMENTS.pdf`,
page 3 — a real issued response. Both marks are **live annotations**, not flattened content.

- Review stamp: `/Stamp` annot, rect `26.9, 606.5 → 313.2, 749.7` in PDF
  coords — **286.3 x 143.2 pt**, 42 pt in from the top and left page edges.
- Comment box: `/FreeText` annot, rect `25.9, 185.2 → 312.6, 601.4` —
  **the same width as the stamp**, same left edge, sitting **5.1 pt below** the
  stamp's bottom edge.
- Box style: `/C [1 1 1]` (white fill), red 1pt border drawn in the appearance
  stream, `/DA (1 0 0 rg /Helv 6 Tf)`, `/DS` declaring
  `font: Helvetica 6pt; margin:3pt; line-height:6.9pt; color:#FF0000`.
- Content opens with `ENGINEERING PLUS COMMENTS:` then a numbered list.
- Interior pages carry yellow-bordered `EPLUS: <comment>` FreeText callouts for
  point comments. **Not implemented** — add those in Bluebeam.

These are the constants at the top of `stamp_pdf.py`.

## 7. PyMuPDF fights you on both annotation types

Three separate traps, all of which produce a plausible-looking wrong result:

1. **`add_stamp_annot()` rewrites your rect.** It fits the built-in stamp's
   aspect ratio (~3.8:1) into the rect you pass, so a 2:1 review stamp comes
   back at half height, vertically centred. Call `annot.set_rect(rect)`
   immediately afterwards to put it back.
2. **`add_freetext_annot()` only accepts `border_color` when `richtext=True`,
   and then ignores it** — it writes `0 0 0 RG` into the appearance stream and
   you get a black border. `add_comment_box()` patches that one operator to
   `1 0 0 RG`. If a future PyMuPDF changes the stream, the code warns instead of
   shipping a black border silently.
3. **Rich text inherits the template's whitespace.** PyMuPDF splices your HTML
   into an indented `<body>`; without a block element wrapping it, that
   indentation renders as literal spaces in front of the first line. Wrapping
   the content in a `<div>` fixes it, at the cost of about one line of top
   offset — which `comment_box_height()` accounts for.

## 8. Page handles go stale when you build the appearance XObject

`_form_xobject_from_stamp()` calls `insert_pdf()` then `delete_page()` to get
the baked stamp's content and resources into the target document. That
reshuffles the page tree and orphans any live `Page` object — the next call on
it dies with `'NoneType' object has no attribute 'is_pdf'`.

**Build every XObject before taking a `Page` handle**, and re-fetch the page
afterwards. `main()` is ordered that way deliberately.

The temporary page is deleted but the resource tree survives because the form
XObject references it, so save with `garbage=3` (which keeps reachable
objects) rather than a full rebuild.

## 9. Sizing the comment box

PyMuPDF's rich-text layout renders at `1.2 x fontsize` leading with a 2pt
inset, not the 6.9pt / 3pt the issued file declares in its `/DS`. Size the box
with the values PyMuPDF will actually use or the last line gets clipped; keep
the house numbers in `/DS` and `/RC`, which is what Bluebeam reads when someone
edits the box.

`verify_comment_fit()` checks the result by **parsing the appearance stream**
(one `TJ` per line, first baseline in the `Tm`), not by probing pixels. A pixel
probe cannot tell the last legitimate line from an overflowing one — the text
sits a couple of points off the border either way, and the first version of
this check fired on every correct run.

## 10. Two stamps shipped with a damaged xref table

`For Record.pdf` (8 orphans) and `For Information Only.pdf` (1–2, depending on
the read path) carried cross-reference slots marked in-use that pointed at
nothing — objects 48–55. Walking all 90 xref entries found **no object in
either file referencing them**; they were orphans in the table itself, so
MuPDF logged `cannot find object in xref (48 0 R)` on every read.

Two things worth remembering:

1. **A Bluebeam re-save does not fix this.** Revu rewrites the objects it knows
   about and builds a fresh table around the same broken slots. The stamp owner re-saved
   `For Record` and the eight orphans came back byte-for-byte identical. The
   same was true of the Draft raster — when a defect lives below the layer the
   authoring tool edits, asking for a re-save just burns a round trip.
2. **The damage never reached the output.** Stamping a submittal with the
   broken `For Record` produced a file that reopened with zero warnings. It was
   console noise on the source file only, which is why it stayed a low-priority
   item rather than a blocker.

Fixed 2026-09-01 with the stamp owner's approval by rewriting both through
`Document.save(garbage=4, deflate=True, clean=True)` — lossless, and verified
as such: rasterised ink is SHA-1 identical before and after, same 13
annotations, same `&[User] &[Date]` cell, same 216 x 108.7 pt ink box. All
eight bundled stamps now read clean.

**If either file is ever re-edited in Bluebeam, expect the orphans back** —
re-run the repair, and check with the loop in section 5 rather than assuming.

## 11. Opacity lives in the stamp file, not the script

For a live annotation, opacity is just `/CA` on the annot — no ExtGState
wrapper needed.

But **`bake()` preserves the stamp file's own transparency**, so anything the
script adds on top *compounds* with it. Measured on the re-authored
`Draft.pdf`: its text is #969696 at 40%, and the darkest pixel of the baked
stamp is grey level 212 — exactly #969696 (150) composited over white at 0.4.
Applying a further `--watermark-opacity 0.25` would have taken the effective
alpha to 0.10 and left the mark nearly invisible.

So `--watermark-opacity` defaults to **1.0**: honour the stamp as authored.
Use the flag only to knock back a stamp that is too heavy as drawn, and change
the stamp file rather than the flag if the correction should be permanent.
Review stamps stay fully opaque.

## Open questions

- Scanned/image-only submittals: `InkMap` works on rasters, but a scan's
  off-white background may read as ink and defeat the blank search. May need a
  higher threshold or a whitepoint step.
- Landscape / non-Letter / rotated source pages are handled only as far as
  PyMuPDF does implicitly — the mediabox flip in
  `_form_xobject_from_stamp()` is correct, but rotated pages are untested.
- Multi-stamp packages: no support for different stamps on different pages in
  one pass.
