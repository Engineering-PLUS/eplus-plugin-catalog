# Assemble and render: Step 7

Covers building the master JSON, rendering the .docx, and the renderer rules that must not
be re-derived. Assumes `data/items.json`, `data/drafted_items.json` and
`build/sheet_clips_jpg/` exist and `build/report.config.json` is filled in.

### Step 7 — Assemble and render

```bash
RENDER_ONLY=1 bash scripts/run_pipeline.sh
```

That runs `build_master.py`, `gen_report.js`, `fix_bookmark_ids.py`,
`verify_report.py` and the review-sheet export (`build/<report>-Review.xlsx`)
in order, and is the only supported way to render: a bare
`node scripts/gen_report.js build` leaves duplicate bookmark ids in the file
and skips the verifier. `bash scripts/run_pipeline.sh` without the variable
runs the data steps first.

**Three things the renderer takes from the data or the config, never from a
worker's patch:**

- **Date Recorded** is the pin's `created_at` (`date_recorded` in the master,
  written by `build_master.py`), so every item has one. The photo timestamp is
  only a fallback for a master built before this field existed. Field result
  2026-09-14: 27 photo-less items printed N/A and cost a second delivery.
- **Deleted pins** kept by `deleted_pins: "keep"` in `report.config.json`
  (`update_report.py --deleted-pins keep`; `KEEP_DELETED=1` still works) carry
  `deleted_in_plangrid`; the renderer prints a red DELETED IN PLANGRID banner
  under the heading and appends "(deleted in PlanGrid)" to the TOC entry.
  `verify_report.py` asserts one banner per such pin and none elsewhere.
- **Visit sections** come from `report.config.json`: `"visit_sections":
  "by_date"` puts a Heading 1 titled "Site Visit N, MM/DD/YYYY" at the top of
  the first item of each pin date, or `"visit_breaks": [{"before": <PlanGrid
  number>, "title": "..."}, ...]` names them explicitly. The heading is
  Heading 1 without item numbering, so the TOC lists it and Word's Update
  Table keeps it; it carries that item's page break. A `before` that names no
  item fails the render. Without either key the report is a flat list and
  the dates carry the split.

`build_master.py` merges facts with judgment and enforces what the renderer
should not have to care about: no em or en dashes anywhere, the voice rules,
capitalised corrective actions, photo paths as basenames only (an absolute source
path silently renders the unnormalised, EXIF-sideways original), and a loud
failure on any item with no drafted entry.

Report identity — building, client display name and address, EP project
number, inspection and issuance dates, inspector — lives in
`build/report.config.json`, **not** in the renderer. Change it there. The footer
is derived from it (`Engineering PLUS  •  <client> <building> Technology System
Punch List  •  Page N of M`); the letterhead reads Technology System / Punch
List whatever the file is called.

**Two files, and the body's page 1 is blank.** `cover_mode` in the config:

| `cover_mode` | Body page 1 | Cover file written | Use when |
|---|---|---|---|
| `template` | blank | `<output>-Cover.docx` | default: the reviewer gets a cover to review and can still swap it |
| `supplied` | blank | no | the reviewer handed over their own coversheet |
| `blank` | blank | no | the reviewer will make a cover later |
| `none` | no blank page, TOC is page 1 | no | a client that issues the report without a cover |

The blank page is the reviewer's workflow made explicit: page 1 of the
exported body PDF gets replaced by the coversheet (in Bluebeam, or with
`scripts/staple_pdf.py` once both PDFs exist), and because the body already
counted that page, "Page 2 of 10" stays right with no field tricks. Never put
a header or footer on that section.

Read the `docx` skill for mechanics and `eplus-branding-default-fonts` for styling
if you need to modify the renderer. Its defaults are all learned the hard way —
**do not re-derive them**:

**The cover is the issued EPLUS coversheet, measured, not approximated.** The
layout constants in `gen_report.js` (positions, sizes, alignment of every text
block) were read off an issued coversheet PDF on 2026-09-10: EP logo and
address line at the top, eyebrow and building on the dark band, client name and
address right-aligned at the bottom, EP project number and the two dates and
the inspector as four lines bottom left, MM/DD/YYYY. Two raster pieces are the
artwork: `assets/cover/cover_hero.jpg` and `assets/cover/cover_bands.png`, both
page-anchored floating images behind the text; **the hero is emitted first**
because docx derives z order from document order and the bands belong on top.
Every piece of cover text is native and page-anchored, so it stays editable in
Word and lines up at print size. No draft warning on the cover; the first
Editor's Note in the body carries it.

**A cover fact nobody has supplied renders as a red `[MISSING: ...]` marker**
(client name, site address, EP project number, building, inspector, walk date;
an empty issuance date renders TBD). The draft is built before those facts are
known, so the marker is the honest state, never a `<template hint>` and never a
guess. `prefill_config.py` fills what the client profile and PlanGrid state
and records each value's source in `fact_sources`; `finish_list.py` lists every
marker with its `update_report.py --set` command; `verify_report.py` fails a
cover that still carries template hint text. The old fallback of printing the
PlanGrid project name where the client name belongs applies only to configs
without `fact_sources`.

The original is set in Montserrat, which
the seats do not have, so the cover uses the document font (Arial) at the same
sizes; when the fleet standardises a brand font, `FONT` is the one constant.

The **client logo is per project and is not bundled with this skill** — it is
the end client's trademark. Drop it at `build/assets/cover/client_logo.png` and
it renders bottom right inside a 3.19 x 0.73 in box; omit it and the cover
renders without it. How a project's logo file gets there is still an open
question (it usually lives inside a document); leave the slot empty rather than
guess.

**The letterhead is built natively, never pasted in as a bitmap.** This was
raised on two consecutive reports. The root cause is not image size: a
full-page-width strip in a header starts at the **body** left margin, so it
overhangs the right edge and leaves dead space on the left. Rescaling it is
another patch on the same mistake. The header is a two-column table sized to
`USABLE_W`, so it tracks the body margins at any page size and stays crisp at
print resolution. The divider must stay a shaded paragraph, not a border, because
LibreOffice clamps thick borders to hairlines.

**One item per page.** Page break before each item heading, table rows
`cantSplit`. The photo grid is a **fixed two-column grid** at 1.90 in per photo
(3:4 canvas); nothing searches column counts. `estimateOverheadDXA()` sums the
heading, meta table, description, corrective action and Editor's Note, and the
renderer puts as many *complete* rows as fit in the remaining height on the item
page (1- and 2-photo items always try the item page), then spills the rest onto
headed "(continued)" pages. The "Photos" label carries no count: it goes stale
the moment anyone adds a photo in Word. An item with no photos still gets one
empty row sized like a real cell, as a paste target, unless its `photo_mode` is
`none`.

**Downscale.** ~700 px wide at quality 72 takes a 160-photo report from >150 MB to
~8 MB with no readability loss.

**Image sizes are in PIXELS.** `ImageRun.transformation.{width,height}` wants
pixels while everything else is twips. Passing DXA straight through renders a
~23-inch image and blows every item onto three pages. Convert:
`px = Math.floor((dxa / 1440) * 96)`. Hit twice, once per image type added.

**`rowSpan` is declared once**, on the first row's cell only.

**Green is for visually distinct callouts** — a box or banner — not an inline
bolded label inside body text.

**Write to new filenames, never overwrite.**

### The .docx is the file of record, and the TOC uses live Word fields

These are linked. Do not undo either.

**The reviewer issues the report from Word**, which recalculates fields on
open and on export. The pipeline's own output is the `.docx`. A PDF for a
layout check is fine (`render_preview.py`, scratch only). When the user asks
for a PDF, `scripts/export_pdf.py` makes a convenience copy in two LibreOffice
passes (the first learns where LibreOffice put each item, the second renders a
scratch copy with those numbers cached into the TOC), so its numbers match its
own pagination; it is labelled as such and `package.py --pdf` delivers it. It
is never the issued document, because LibreOffice and Word paginate
differently.

**The contents block is a real Word `TOC` field** (` TOC \o "1-1" \h \z \u `)
whose **cached result** is the styled entry list — the exact structure Word
itself saves. On open the cached entries show immediately, so nothing looks
broken; *Update Table* (or Ctrl+A, F9) regenerates titles, page numbers **and
entry count** together. Each cached entry still carries a real `PAGEREF` field
pointing at the item heading's `Bookmark`, wrapped in an `InternalHyperlink`,
with `features: { updateFields: true }` so Word refreshes on open. Regenerated
entries take the `TOC1` paragraph style defined on the document, so the look
survives regeneration.

This replaced two earlier designs, each killed by field evidence:

- a two-pass render that baked **static page numbers** harvested from a
  LibreOffice dry render — **LibreOffice and Word do not paginate
  identically**, so the numbers were wrong and permanently so;
- hand-built entry paragraphs with live `PAGEREF` fields but **static
  titles** — page numbers self-healed on F9 while deleted items stayed in the
  list, so the TOC silently rotted (two reports failed this way on the same
  day: one stale after item deletions, one showing 16 entries against 9 items
  with seven `Error! Bookmark not defined.`). The asymmetry — the body
  renumbering correctly while the TOC rots — is what misled reviewers.

Transferable rules: **never display a measurement taken from a different
renderer than the reader will use**; **when a constraint is removed, delete the
workaround it forced**; and **make the whole structure one field so Word owns
all of it**, not just the numbers.

`scripts/fix_bookmark_ids.py` runs after every render (wired into
`run_pipeline.sh`, which is why `RENDER_ONLY=1 bash scripts/run_pipeline.sh`
is the only supported render command):
the docx library emits every bookmark as `w:id="1"` (Word keys on the id and
discards duplicates — the `Error! Bookmark not defined.` bug that shipped once)
and non-canonical `PAGEREF` instruction text; it fixes both in place.
`verify_report.py` asserts the ids are unique, that exactly one canonical TOC
field opens and closes around the entries, and that the cached entry count
matches the item count.


**Handing this stage to a worker:** paste `reference/worker-brief.md`, then name
this file, the paths, and "run `RENDER_ONLY=1 bash scripts/run_pipeline.sh`,
then look at three preview pages (the cover, one item with photos, one
without) with `render_preview.py`, report one line each, and stop; do not
deliver". That is the whole verification: the verifier inside the pipeline
already covers the TOC, fields, dates, banners, sections, cover and letterhead.
Do not ask for eight pages, the OOXML, or "check what the renderer keys off"
(the 2026-09-14 render brief did, and the worker spent 12 minutes reading
scripts and patching data). Every decision the render needs is a config key or
a data field named above; if one is missing, that is an Open question for the
main thread, not a renderer edit. Any test render or negative-control file
goes under `build/_scratch/`, never beside the real output, and is never
removed by the worker.

Next: `reference/verify-and-deliver.md` (verify the OOXML, keep it editable, deliver once).
