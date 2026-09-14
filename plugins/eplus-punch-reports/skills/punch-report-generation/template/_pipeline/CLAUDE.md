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

Scope lives in exactly one place, the variables in front of `run_pipeline.sh`,
which become `consolidate.py` arguments:

```bash
SCOPE=11-30 TITLE="<walk marker>" CREATED_AFTER=<YYYY-MM-DD> \
DROP_PHRASES="<record-only phrase>; <another>" KEEP_DELETED=<1 or unset> \
bash scripts/run_pipeline.sh
```

**This report's values:** `SCOPE=<…>` `TITLE=<…>` `CREATED_AFTER=<…>`
`DROP_PHRASES=<…>` `KEEP_DELETED=<…>` (record them here at intake; they are
the run's scope of record). Nothing else in the pipeline hardcodes scope.
Unset a variable to apply no rule of that kind. Deleted and archived items
are dropped unless `KEEP_DELETED=1`, in which case they stay, flagged
`deleted_in_plangrid`, and render with a red DELETED IN PLANGRID banner.
Visit sections, when the report has them, are `visit_sections` or
`visit_breaks` in `build/report.config.json`. Client-level facts (display
name, address, EP number, inspector, reviewer, drop phrases, cover settings)
live in `../client-profile.json`, which delivery copies into the project
folder for the next report.

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

**To re-run:** `bash <plugin skill>/scripts/init_workspace.sh <fresh workspace>
--from-package <this package .zip>` unpacks the package and refreshes
`_pipeline/scripts/` from the plugin in one step; work there, and deliver
again under a new `output_filename`. Never edit the delivered copy in place,
and never lay a workspace out by hand.

**Nothing is deleted, moved, or renamed here while a run is in progress**, by
the main thread or by a worker. Deletes in a mounted folder need a permission
the user grants blind, and a worker cannot explain what it is removing. Write
to new filenames; put scratch, test renders and preview PDFs under
`build/_scratch/` (the packager skips it) or `/tmp`. Anything that should go is
listed in the worker's "Files to remove" section and handled by the main
thread once, after delivery. Workers do not read memory; this file and the one
reference named in their brief are their only sources.

---

## The source data, and where it hides

The pull is `<pull folder>/`. **Photo route this run: `<live | pdf | mixed>`**
(from `adapt_mcp_pull.py`'s last line; if not `live`, name the host that failed
and the request id filed for it). This line describes what happened on this
run only. It is not a statement about what the next run can reach: the next
run fetches the originals again regardless, per the skill.

If the pull came from the `plangrid` MCP rather than an exported folder, the raw
material (task rows, photo URLs, downloaded originals, PDF fallback crops) is in
`../plangrid_mcp/` and the adapted pull the pipeline reads is `../plangrid_pull/`.
The MCP's bulk tools return summaries plus a packet url; `scripts/pull_mcp.sh`
fetches the packets. Never write a tool result to a file with Write or Edit.

Two shapes to check for, every time:

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

Data quality for this pull, from the triage summary (generated by
`scripts/run_record.py` on every pipeline run; do not edit inside the markers):

<!-- data-quality:start -->
(written on the first pipeline run)
<!-- data-quality:end -->

`room` is empty on almost every pin, so the drawing sheet is the only location
data and reports print `Not recorded in PlanGrid, see sheet reference`. A title
that appears on >=50% of pins (min 3) is a field marker, not content;
`consolidate.py` detects and drops it, and the record names it.

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

# 4+5. assemble, render, repair bookmark ids, verify, export the review sheet
#      (the only supported render command)
RENDER_ONLY=1 bash scripts/run_pipeline.sh

# layout spot check, three pages and no more (needs soffice on PATH; deletes its own PDF)
python3 scripts/render_preview.py build/<filename>-Cover.docx --pages 1
python3 scripts/render_preview.py build/<filename>.docx --pages <photo item>,<no-photo item>
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

### The .docx is the file of record, and the TOC is a real Word TOC field

These two facts are linked. Do not undo either.

**The reviewer issues the report from Word**, which recalculates fields on open
and on PDF export. LibreOffice paginates differently and does not update
fields, so a plain LibreOffice conversion carries blank or wrong page numbers;
that shipped once. PDFs for your own layout checks are fine and go under
`build/_scratch/`. If the user asks for a PDF, `scripts/export_pdf.py` makes a
convenience copy whose numbers match its own pagination (two passes), and
`package.py --pdf` delivers it, labelled as a convenience copy.

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

**Bulk edits: the review spreadsheet.** Every verified render writes it as
`build/<report>-Review.xlsx`; that is the copy delivered beside the .docx.

```bash
#   reviewer edits the YELLOW columns only, in build/<report>-Review.xlsx
python3 scripts/review_sheet.py import build build/<report>-Review.xlsx
RENDER_ONLY=1 bash scripts/run_pipeline.sh
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
- **Two files: the body, whose page 1 is blank, and the cover.** `cover_mode` in
  `report.config.json` is `template` (write `<output>-Cover.docx`, body page 1
  blank), `supplied` or `blank` (body page 1 blank, no cover written) or `none`
  (no blank page, the TOC is page 1). The blank page is the reviewer's swap
  slot: page 1 of the exported body PDF is replaced by the coversheet, so the
  page numbers and the "of N" count are already right. That section carries no
  header and no footer.
- **The cover is the issued EPLUS coversheet, measured.** Positions and sizes of
  every text block were read off an issued coversheet PDF; the two rasters
  (`assets/cover/cover_hero.jpg`, `assets/cover/cover_bands.png`) are the
  artwork, page-anchored behind the text, hero first so the bands sit on top.
  Content, all from `report.config.json`: eyebrow and building on the band,
  client display name and address bottom right, EP project number, inspection
  date, issuance date and inspector bottom left, dates MM/DD/YYYY. No draft
  warning on the cover. Arial at the reference sizes (the original is
  Montserrat, which the seats do not carry).
- **The client logo is per project and is not bundled.** Drop it at
  `build/assets/cover/client_logo.png` and it renders bottom right; leave it out
  and the cover renders without it.
- **The footer is derived**: `Engineering PLUS  •  <client> <building> Technology
  System Punch List  •  Page N of M`. The letterhead says Technology System /
  Punch List regardless of what the file is called.
- **The meta table is two rows: Drawing Sheet and Date Recorded.** Location was
  removed because PlanGrid's `room` is empty on every pin, so the row only ever
  printed a placeholder, which reads as noise. The Photos count went with it: the
  photos are directly below. If real location data becomes available (photo EXIF
  geotags), add the row back rather than reviving the placeholder.
- **Date Recorded is the pin's `created_at`**, carried as `date_recorded` by
  `build_master.py`, so every item has one whether or not it has a photo. The
  photo timestamp is only a fallback for an old master. `verify_report.py`
  fails a render that prints N/A on an item whose pin has a date.
- **Deleted pins kept by intake are bannered, not hidden.** With
  `KEEP_DELETED=1` they stay in `items.json` flagged `deleted_in_plangrid`,
  render with a red DELETED IN PLANGRID banner under the heading, and their
  TOC entry says "(deleted in PlanGrid)". Nobody retypes them into the data.
- **Visit sections are a config key, not a renderer edit.** `visit_sections:
  "by_date"` in `report.config.json` (or an explicit `visit_breaks` list)
  puts a Heading 1 "Site Visit N, MM/DD/YYYY" on the first item of each pin
  date; the TOC lists it and Word regenerates it with the items. Without the
  key the report is a flat list and Date Recorded carries the split.
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
- **`cover_mode: none`** drops the blank first page for a client that issues the
  report without a cover; the contents page then becomes page 1. Every other
  mode keeps the blank page (see the two-files rule above).
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

`cover_mode` (default `template`) also lives there; see the renderer rules above.

Two rules about that file:

- **`ep_project_no` is rendered on the cover only**, as the issued coversheet
  does (EP Project No is its first meta line). It never appears in the body.
  `verify_report.py` asserts both: present on the cover file, absent from the
  body text.
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
