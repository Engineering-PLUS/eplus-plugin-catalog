# Assemble and render: Step 7

Covers building the master JSON, rendering the .docx, and the renderer rules that must not
be re-derived. Assumes `data/items.json`, `data/drafted_items.json` and
`build/sheet_clips_jpg/` exist and `build/report.config.json` is filled in.

### Step 7 — Assemble and render

```bash
python3 scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o build/master_report_items.json
node scripts/gen_report.js build
python3 scripts/verify_report.py build/<output>.docx
```

Or `bash scripts/run_pipeline.sh` for all five steps plus verification.

`build_master.py` merges facts with judgment and enforces what the renderer
should not have to care about: no em or en dashes anywhere, the voice rules,
capitalised corrective actions, photo paths as basenames only (an absolute source
path silently renders the unnormalised, EXIF-sideways original), and a loud
failure on any item with no drafted entry.

Report identity — cover title, subtitle, walk date, prepared-by, footer — lives in
`build/report.config.json`, **not** in the renderer. Change it there. The same
file carries `"include_cover"`: set it to `false` when the client issues its own
coversheet and combines PDFs by hand, in which case a generated cover is a page
they delete every time. Dropping it is safe; the Table of Contents simply
becomes page 1.

Read the `docx` skill for mechanics and `eplus-branding-default-fonts` for styling
if you need to modify the renderer. Its defaults are all learned the hard way —
**do not re-derive them**:

**The cover is the issued EPLUS coversheet design.** Two raster pieces are reused
as artwork, because artwork is what they are: `assets/cover/cover_hero.jpg` (stock
brand imagery) and `assets/cover/cover_bands.png` (the EP diagonal band graphic, a
full-page transparent overlay). Both are page-anchored floating images behind the
text; **the hero is emitted first** because docx derives z order from document
order and the bands belong on top. Every piece of cover text is native and comes
from `report.config.json`, so it tracks page size and stays editable.

The **client logo is per project and is not bundled with this skill** — it is the
end client's trademark and changes every job. Drop it at
`build/assets/cover/client_logo.png` to have it render top right; omit it and the
cover renders without it.

The cover is **its own section**, with no letterhead header and no footer, since a
page-number strip across the artwork reads as a mistake. The section break already
starts the following page, so the Table of Contents paragraph must not also carry
`pageBreakBefore` or Word emits a blank page.

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

### The pipeline outputs .docx only, and the TOC uses live Word fields

These are linked. Do not undo either.

**No PDF is generated.** The reviewer produces it from Word once markup is done.
Word recalculates fields on open and on export.

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
`run_pipeline.sh`; run it yourself after a bare `node scripts/gen_report.js`):
the docx library emits every bookmark as `w:id="1"` (Word keys on the id and
discards duplicates — the `Error! Bookmark not defined.` bug that shipped once)
and non-canonical `PAGEREF` instruction text; it fixes both in place.
`verify_report.py` asserts the ids are unique, that exactly one canonical TOC
field opens and closes around the entries, and that the cached entry count
matches the item count.


Next: `reference/verify-and-deliver.md` (verify the OOXML, keep it editable, deliver once).
