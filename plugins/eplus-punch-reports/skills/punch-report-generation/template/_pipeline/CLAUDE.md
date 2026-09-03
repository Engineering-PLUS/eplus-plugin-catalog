# <PROJECT> punch report pipeline

Everything needed to rebuild this report from the raw PlanGrid pull. Read this
before touching anything in here.

**Current output:** `<filename>.docx`, <N> items, <N> pages, <N> photos, <N> sheet
clips. Draft for internal review, not issued.

---

## Scope decision, read this first

The PlanGrid pull contains **<N>** items. This report covers **<which>**.
<State what was excluded and by whose direction, and whether the excluded items
are still open. If a prior report covered them, name it.>

Scope lives in exactly one place, the `SCOPE` variable, which becomes
`consolidate.py --only`:

```bash
SCOPE=11-30 bash scripts/run_pipeline.sh
```

Nothing else in the pipeline hardcodes it. Unset `SCOPE` to include every item.

---

## Working rule: this workspace is the only place work happens

This folder tree was built in the session's own workspace and delivered to the
project folder as one package (`scripts/package.py`). The project folder itself
is read-only during a run: inputs are copied in once, every step reads and
writes here, and the only write back is the final delivery.

Two reasons, both learned the hard way. Project shares are slow for the
many-small-file steps (photo normalisation has taken over two minutes on a share
and 2.6 seconds locally), and a run that works in the project folder with a
scratch copy has to sync sources back by hand. That sync was once missed: a
`drafted_items.json` edit lived only in the scratch copy, the report was rendered
from it, and the delivered document disagreed with the file that generates it.
`verify_report.py` checks the rendered document against the master JSON for
exactly this reason, but the workspace rule removes the failure mode instead of
catching it.

**To re-run:** unzip the delivered package into a fresh workspace, refresh
`_pipeline/scripts/` from the plugin, work there, and deliver again with a new
package name. Never edit the delivered copy in place.

---

## The source data, and where it hides

The pull is `<pull folder>/`. Two shapes to check for, every time:

1. **`delta_<from>_to_<to>/` folders, possibly several.** When a pull is taken
   across more than one session, each delta holds the tasks touched in its
   window plus only the **new** photo binaries, and usually an **empty**
   `sheets.json`. A later delta is **not** a superset of an earlier one.
   `consolidate.py` layers the base and every delta oldest-first, merges tasks
   by uid, and indexes photos across every layer; its `tasks source` line
   names the layers it used. Reading any one folder alone quietly loses either
   items or photos.

2. **The Task Report PDF is not in the pull.** It is exported separately from
   PlanGrid and is the ONLY source of the per-item annotated sheet clips (the
   drawing with the pin stamp). A pull's `sheet_packets/*.pdf` holds raw drawings
   with **no pin stamps**. If no Task Report is present, ask for one before
   drafting rather than discovering it mid-run.

Data quality for this pull, from the triage summary:

- <N> items in scope, <N> with an authored description, <N> photo-only
- <N> photos, all resolved to files on disk, shot <date> by <photographer>
- `room` is empty on <N>% of pins. The drawing sheet is the only location data.
  Reports print `Not recorded in PlanGrid, see sheet reference`.
- <N> of <N> items resolve to a valid sheet
- `title` is the literal string `<filler>` on <N> of <N> pins. It is a field
  marker, not content. `consolidate.py` auto-detects and drops any title
  appearing on >=50% of pins (min 3).

---

## Pipeline, in order

Run from `_pipeline/`. Dependencies: `bash scripts/install_deps.sh` (idempotent;
needed on every fresh sandbox), then `bash scripts/smoke_test.sh`.

Check the tooling before the first run:

```bash
bash scripts/smoke_test.sh
```

Then:

```bash
bash scripts/run_pipeline.sh
```

That runs all five steps and verifies. The individual steps, if you need one:

```bash
# 1. consolidate the pull -> the factual layer
python3 scripts/consolidate.py "<pull>" -o data/items.json --only <scope>

# 2. normalise photos (EXIF rotate + letterbox + downscale)
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json

# 3. sheet clips from the PlanGrid Task Report PDF
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" \
    build/sheet_clips_jpg --items-from data/items.json \
    --dims-out build/sheet_clip_dims_jpg.json

# 4. assemble the render-ready JSON (facts + judgment)
python3 scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o build/master_report_items.json

# 5. render, repair bookmark ids, verify
node scripts/gen_report.js build
python3 scripts/fix_bookmark_ids.py build/<filename>.docx
python3 scripts/verify_report.py build/<filename>.docx

# optional layout spot check (needs soffice on PATH; deletes its own PDF)
python3 scripts/render_preview.py build/<filename>.docx --pages 1,4
```

`data/items.json` is **facts**, regenerated from the pull.
`data/drafted_items.json` is **judgment**, written during the drafting step.
Only the second is yours to edit by hand. It is a bare list of entries or
`{"items": [...], "merges": [...]}`; the field list is in the skill's
`reference/drafting.md` (Step 4).
Two fields matter to the renderer beyond the text: `photo_mode` on a photo-less
item (`own_photos` renders a blank paste grid, `none` drops the grid and label,
`followup` renders the grid), and `origin`: entries marked `user_reviewed` or
`reviewer_final` are human-approved and `build_master.py` never rewrites them,
failing the build instead if they are not already clean.

### No PDF is generated here, and the TOC is a real Word TOC field

These two facts are linked. Do not undo either.

**We output .docx only.** The reviewer generates the PDF from Word when markup
is finished. Word recalculates fields on open and on PDF export. LibreOffice
paginates differently and does not update fields, so a PDF made with it carries
wrong page numbers; that shipped once and is why the PDF guard hook exists.

**The contents block is one `TOC \o "1-1" \h \z \u` field.** Its cached
result, written by the renderer, is the styled entry list: one `PAGEREF` field
per item pointing at the bookmark on that item's Heading 1, wrapped in a
hyperlink, so the list is visible the moment the file opens. `features:
{ updateFields: true }` makes Word refresh on open; *Update Table* or Ctrl+A
then F9 regenerates **titles, page numbers and the entry count together**, so
deleting or adding an item in Word repairs the whole contents page. Regenerated
entries take the document's `TOC1` style, which matches the cached look.

Two earlier designs died on field evidence: static page numbers harvested from
a LibreOffice render (wrong renderer, never recalculated), then hand-built
entries with live page-number fields but static titles (numbers self-healed on
F9 while deleted items stayed listed, so the TOC rotted while the body looked
right). Owning the whole block as one field is what fixed it.

**`fix_bookmark_ids.py` must run after every render.** The docx library writes
every bookmark with the same numeric id; Word keys on the id, keeps one and
discards the rest, and every TOC entry after the first shows `Error! Bookmark
not defined.` on F9. `run_pipeline.sh` runs it; `verify_report.py` asserts the
ids are unique and that exactly one canonical TOC field wraps an entry list the
same length as the item list.

---

## Editing the report after it is rendered

A rendered .docx is a compiled artifact. Two supported paths, both must keep
working.

**Small edits: directly in Word.** Item headings use Word's own numbering, so
deleting an item renumbers the rest automatically. Do not write the number into
the heading text. Every item is exactly one page and self-contained, so inserting
an item by hand is copy a page, paste, edit.

The PlanGrid ID is deliberately **not** in the heading. The printed item number
is presentational and will change; the PlanGrid ref is the permanent link back to
source. It is carried in `master_report_items.json` as `plangrid_ref` and shown
in the review spreadsheet.

**Reviewer comments in Word: read them back** rather than reading the document
and guessing what changed.

```bash
python3 scripts/read_comments.py <reviewed>.docx
```

Each comment is reported with the text it is anchored to and the item heading it
sits under. Resolved comments are hidden unless `--include-resolved` is passed.

**Bulk edits: the review spreadsheet.**

```bash
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the YELLOW columns only
python3 scripts/review_sheet.py import build Report-Review.xlsx
node scripts/gen_report.js build
```

Yellow = editable, grey = generated and ignored on import, so photo paths and
sheet clips cannot be corrupted by editing the sheet. `Include? = N` drops an
item, `Order` reorders, a new row with a blank PlanGrid ref inserts an item. A
timestamped `.bak.json` is written before anything changes.

---

## Rules the renderer bakes in, do not re-derive

- **The letterhead is built natively, never pasted in as a bitmap.** A
  full-page-width strip in a header starts at the *body* left margin, so it
  overhangs right and leaves dead space left. The header is a two-column table
  sized to `USABLE_W`, so it tracks the body margins at any page size and stays
  crisp at print resolution. The divider must stay a shaded paragraph, not a
  border, because LibreOffice clamps thick borders to hairlines.
- **Item descriptions are in field-report voice.** The report is written *by* the
  field engineer, describing the site. Banned from descriptions and asserted
  against in `build_master.py`: narrating the evidence ("the photograph shows",
  "not visible in the frame") and third-person self-reference ("the field
  engineer recorded"). Editor's Notes are internal and exempt.
- **The verbatim pin note is not rendered.** Quoting the engineer's own shorthand
  back at them reads as third person. It is carried as `field_note` for
  traceability and appears in the review spreadsheet. If you re-add it, also
  restore its allowance in `estimateOverheadDXA()` or the photo grid under-packs.
- **The cover is the issued EPLUS coversheet design, rebuilt natively.** Two raster
  pieces are reused as artwork because that is what they are:
  `assets/cover/cover_hero.jpg` (stock brand imagery) and
  `assets/cover/cover_bands.png` (the EP diagonal band graphic, a full-page
  transparent overlay). Both are placed as page-anchored floating images behind the
  text, at the geometry taken from the reference document: bands 8.49 x 10.98in at
  (0.00, 0.01), hero 8.53 x 6.37in at (0.00, 1.01). **The hero must be emitted
  first**, because docx derives z order from document order and the bands sit on
  top. All cover text is native and comes from `report.config.json`.
- **The client logo is per project and is not bundled.** It is the end client's
  trademark and changes every job. Drop it at
  `build/assets/cover/client_logo.png` and it renders top right; leave it out and
  the cover renders without it.
- **The cover is its own section**, with no letterhead header and no page footer.
  A "Page 1 of N" strip across the artwork reads as a mistake. Because the section
  break already starts the next page, the Table of Contents paragraph must NOT also
  carry `pageBreakBefore`, or Word emits a blank page between them.
- **The meta table is two rows: Drawing Sheet and Date Recorded.** Location was
  removed because PlanGrid's `room` is empty on every pin, so the row only ever
  printed a placeholder, which reads as noise. The Photos count went with it: the
  photos are directly below. If real location data becomes available (photo EXIF
  geotags), add the row back rather than reviving the placeholder.
- **The pin clip is rendered at double width** (about 3.17in). With no location
  data it is the only thing on the page that says where the item is. Display width
  and extraction `--zoom` must move together, or the clip just gets bigger and
  blurrier; the extractor defaults to 6x for this reason.
- **The photo grid is visibly gridded and photos are numbered.** This document
  gets edited in Word and the commonest edit is adding or swapping a photo;
  borderless cells give the reviewer nothing to aim at. Empty slots are drawn but
  carry no placeholder text, because the file is exported to PDF as-is and hint
  text would print. Empty cells are given the height of a filled cell, because an
  empty paragraph collapses to an invisible hairline. An item with no photos
  still gets one empty row as a paste target unless its `photo_mode` is `none`,
  and the "Photos" label carries no count, which would go stale on the first
  edit.
- **The cover is optional.** `"include_cover": false` in `report.config.json`
  drops the cover section for clients who issue their own coversheet; the
  contents page then becomes page 1.
- **Sheet designators are normalised `TO` to `T0`.** PlanGrid's sheet-name OCR
  reads the character after a leading T as a letter O rather than a zero at upload
  time. The upstream fix is to correct each sheet name by hand when uploading
  drawings; the report cannot rely on that having happened.
- **On-page editor instructions are red and marked DELETE PRIOR TO PRINTING.**
  Anything addressed to the person editing the file, rather than to the reader,
  must be unmistakable, because otherwise it prints in the issued PDF.
- **One item per page.** `pageBreakBefore` on each heading, rows `cantSplit`.
- **No em or en dashes, anywhere, ever.** Swept in `build_master.py`, asserted in
  `verify_report.py`. Standing EPLUS rule.
- **Image sizes are in PIXELS.** `ImageRun.transformation` wants px while
  everything else is twips. `px = Math.floor((dxa / 1440) * 96)`. Getting this
  wrong renders a 23-inch image. Hit twice historically.
- **`rowSpan` is declared once**, on the first row's cell only.
- **EXIF orientation must be applied before resize.**
- **Photos are 1.90 inch in a fixed two-column grid, fill-and-continue
  pagination.** As many complete rows as fit on the item page, the rest on
  headed continuation pages. Tuned to cut blank space. Do not change without
  asking.
- **Green is for visually distinct callouts only**, not inline bold labels.
- **Write to new filenames, never overwrite.**

## Report identity

Cover and footer strings are **not** hardcoded. They live in
`build/report.config.json`. Change them there, not in the renderer.

`include_cover` (default `true`) also lives there; see the renderer rules above.

Two rules about that file:

- **`ep_project_no` is internal tracking and is never rendered.** It is there so
  runs stay traceable on our side. It must not appear anywhere a client, GC or
  subcontractor reads, the cover included. `verify_report.py` asserts it is absent
  from the document text and fails the build if it is not.
- **The issuance date is asked for, never inferred.** It is a contractual fact
  about when the report goes out, decided by the reviewer, and it routinely
  differs from both the walk date and the compile date. A draft that is not yet
  being issued does not get a guessed date.

## Precedent

Item wording is checked against the EPLUS punch corpus via the
`punch-knowledge-hub` tools, using the `punch` skill. Search to find candidates,
then `get_punch_item` to read the exact wording before citing it.

<Record this project's precedent coverage here: how many items carry a citation,
and any theme the corpus could not cover.>
