---
name: punch-report-generation
description: Use this skill to DRAFT a punch report, field progress report, or site inspection report from raw field material — a PlanGrid project pull, a folder of site photos, an engineer's walk notes, or any combination. Trigger when asked to write up a punch walk, turn photos and notes into a report, produce a draft punch list document, or generate a deliverable from a site visit. Covers consolidating messy source data, drafting descriptions from photo evidence, checking wording against EPLUS precedent, and rendering a branded one-page-per-item Word document. Distinct from the `punch` skill, which QUERIES the historical corpus; this one PRODUCES a new report.
argument-hint: <folder of field material — e.g. "draft the report from the files in this folder">
---

# Drafting a punch report from field material

Turns a site walk into a reviewable draft. The human finishes and issues it —
the target is ~80% of the way there with every uncertainty surfaced, not a
publishable document.

$ARGUMENTS

## The premise: the input is always messy

This is the problem being solved, not a problem to complain about. Assume all
of the following, every time, and design around it:

- **No location data.** PlanGrid's `room` field is typically empty on 100% of
  pins. The only structured location is the drawing sheet number.
- **Most pins have no description.** Expect roughly a third authored, the rest
  photo-only. The photos *are* the record.
- **Notes aren't linked to pins.** Walk notes arrive as narrative bullets with
  no item numbers, so matching a note to a pin is inference from photo content,
  not a lookup. It is the fuzziest step in the pipeline — treat every match as
  a claim to be checked, not a fact.
- **Some pins are noise.** Camera misfires, photos of colleagues, blank walls.
- **Some pins bundle several unrelated conditions** because that is how they
  were pinned in the field.

**Never ask the field to fix this before you can work.** Infer what is
inferable, label what was inferred, and surface what is not determinable.

## Workflow

### Step 1 — Consolidate

Run the bundled script against the PlanGrid pull:

```bash
python scripts/consolidate.py <rescue_dir> -o items.json
```

It emits one record per live item (number, description, sheet ref, pin stamp,
status, photos resolved to files on disk with capture time and photographer)
plus a triage summary. It auto-detects a title string repeated on nearly every
item (field staff use these as personal markers, e.g. "Jim2") and drops it
rather than treating it as content.

Read the summary before anything else — `photo_only`, `no_photos` and
`with_room` tell you immediately how much of this report has to be drafted
from images.

### Step 2 — Read every source document, and diff the duplicates

Walk notes frequently arrive as two near-identical files (`…notes.docx` and
`…notes(update).docx`). **Diff them and use the newer one**; call out only real
conflicts. Do not assume the older is a safe backup — in practice the update
fixes typos and adds items.

If a PlanGrid Task Report PDF is present, that is where the per-item annotated
sheet clips live (see Step 5). `sheet_packets/*.pdf` contains only the raw
drawings with **no pin stamps** — do not look for per-item clips there.

### Step 3 — Draft a description for every item

**Items with an authored description:** the engineer's wording is
authoritative. Polish to report voice; never change technical meaning.

**Photo-only items:** check the walk notes first — if a note plainly covers
the item, use it and record that the match was inferred. Otherwise describe
what is visibly wrong, in trade vocabulary, and mark it as drafted from photo
evidence.

**Three outcomes are all valid, and the third is not a failure:**

1. A specific, defensible deficiency.
2. A description qualified by what could not be confirmed.
3. *"Photo shows X; deficiency not determinable without field context."*

Expect roughly a third of photo-only pins to land in category 3. That is a
realistic baseline with no location metadata, not a sign anything went wrong.
**Forcing a confident description onto an ambiguous photo is the single worst
failure mode available here** — it produces a report that reads well and is
partly fiction.

**Flag, do not describe, pins with no field content at all.** If the only
photo shows a person, a vehicle, an office interior, or a blank wall, the pin
is almost certainly a camera misfire. Surface it as *"should this item be in
the report?"* rather than writing a hedged entry for it. Do not delete it
silently either — that is the human's call.

### Step 4 — Check wording against EPLUS precedent

Use `query_hermes_punch` (see the `punch` skill) to match this walk's findings
against how EPLUS has written up the same conditions before — bushings,
grounding, J-hooks, labeling, zip ties, cable management all have deep
precedent across sibling projects.

**Verify the tool is reachable before starting the report, and say so loudly
if it is not.** A silently-degraded precedent pass produces a finished-looking
report whose wording was never checked, with the caveat buried where nobody
reads it. If the connector is down, state it at the top of your response and
in the document, and treat a precedent pass as required follow-up.

**When a filtered query returns nothing, drop the `trade` filter first.**
Field-tested: `trade: "Telecom"` plus free text returned zero results where the
same query unfiltered returned good hits. Free text does the work; filters
narrow too aggressively on specific phrasing.

Aim for full coverage. A spot-check of the obvious themes leaves most items
unchecked.

### Step 5 — Sheet clips (optional but expected in a finished report)

Per-item annotated clips — the drawing with the pin stamp — come only from the
**PlanGrid Task Report PDF**. Use the bundled script:

```bash
pip install pymupdf
python scripts/extract_sheet_clips.py "<Task Report>.pdf" clips/ --items-from items.json
```

It handles the three traps that make this fiddly, all of them already solved —
do not reimplement:

1. **Table of Contents.** The first pages repeat every item heading with dot
   leaders and page numbers, so a naive search for `#N` matches the ToC entry.
   The script detects where content starts rather than hardcoding a page.
2. **The reported image bbox is larger than the visible region** — a clip path
   in the content stream is not exposed via `get_image_info`. The crop is
   anchored off the "Sheet" label's position with a tuned offset.
3. **Overflow.** An item near a page bottom pushes its clip to the next page
   with no repeated heading; detected and handled by falling back to the
   following page.

Verified end to end on the NVA06B Task Report: **52/52 clips**, one via the
overflow fallback. It reports which items used the fallback and which are
missing — check that output rather than assuming.

### Step 6 — Render the document

**Use the bundled generator — it already implements everything below.**

```bash
npm install docx          # ^9.7.1
node scripts/gen_report.js <buildDir> [out.docx]
OMIT_NUMBERS=1,2 node scripts/gen_report.js <buildDir>   # drop confirmed misfires
```

`buildDir` must contain `master_report_items.json` (one record per item with
description, location, sheet fields, `photo_paths`, `origin`, `confidence`,
and optional `reviewer_flag` / `precedent_note` / `cross_ref`), plus
`thumb_dims.json`, `sheet_clip_dims_jpg.json`, `assets/logos/`, and the
thumbnail and clip images. It writes to a new filename rather than
overwriting.

Read the `docx` skill for mechanics and `eplus-branding-default-fonts` for
styling if you need to modify it. The defaults it encodes, all learned the
hard way — **do not re-derive these**:

**One item per page.** Not cosmetic — a walk-down report is read a page at a
time. Page break before each item heading, table rows marked `cantSplit`. To
make a 1-photo item and a 21-photo item both look intentional, the photo grid
is sized *dynamically*: `estimateOverheadDXA()` sums the heading, meta table
(the taller of the text rows vs. the sheet clip in its `rowSpan` cell),
description, flags and labels; `layoutForItem()` then walks column counts 3→8
and picks the first that fits the photos in the remaining vertical space at a
minimum thumbnail width, falling back to 8 columns compressed if nothing fits.
1- and 2-photo items get fixed larger sizes so they do not balloon.

**Rotate photos before embedding.** PIL does **not** apply EXIF orientation on
save. Call `ImageOps.exif_transpose()` before resizing or every portrait photo
renders sideways — and it looks correct in every normal image viewer, so it is
easy to miss until the document is built.

**Downscale.** ~700 px wide at quality 72 takes a 160-photo report from
>150 MB to ~8 MB with no readability loss. Full-resolution embedding produces
an unusable file.

**Image sizes are in PIXELS.** `docx`'s `ImageRun.transformation.{width,height}`
wants pixels while everything else in the document is twips/DXA. Passing DXA
straight through renders a ~23-inch image and blows every item onto three
pages. Convert: `px = Math.floor((dxa / 1440) * 96)`. This bug has been hit
twice — once per image type added.

**`rowSpan` is declared once.** Put it on the first row's cell only; the
library generates the merge continuations. Adding your own placeholder cells in
the spanned rows produces invalid columns.

**Green is for visually distinct callouts** — a box or banner — not for an
inline bolded label inside body text. Body text stays Blue/Dark Grey.

**Write to new filenames, never overwrite.** Scratch workspaces routinely
refuse in-place overwrite ("Operation not permitted"), and some libraries
unlink-then-write internally. Version-stamp output directories.

### Step 7 — Deliver the draft plus the issues list

The issues list is a first-class deliverable, not an appendix. Include:

- **Source conflicts** — e.g. a pin on a 2nd-floor sheet while the notes place
  the same condition on the 1st floor. Report both; never silently pick one.
- **Items referencing documents you were not given** (bulletins, ASIs, RFIs) —
  the description can only restate the reference.
- **Suspected misfire pins**, as questions.
- **Items where the photo contradicts the description.**
- **Multi-condition pins**, listed for a split/keep decision.
- **Anything drafted from photos rather than authored**, so the reviewer knows
  where to look hardest.

## House policy

These are standing decisions. Follow them unless told otherwise for a
particular report:

- **Multi-condition pins stay combined in the draft** and are listed for
  review. Splitting changes item numbering, which breaks the link back to
  PlanGrid — that is the human's call to make deliberately.
- **"Not determinable" items ship in the report**, marked as such. They are
  evidence a shot was missed and are worth seeing.
- **Suspected misfire pins are surfaced as questions**, never deleted and never
  force-described.

## What good looks like

A report where every item is traceable to its PlanGrid number, every
description is either the engineer's own words or clearly marked as drafted
from photos, every uncertainty appears in the issues list rather than being
smoothed over, and the reviewer's job is confirming judgment calls — not
discovering that a confident-sounding paragraph was invented.
