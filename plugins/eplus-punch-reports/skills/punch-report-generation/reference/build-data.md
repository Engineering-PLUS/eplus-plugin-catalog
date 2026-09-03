# Build the data: Steps 1, 2 and 6

Covers consolidating the PlanGrid pull, normalising photos and extracting sheet clips.
Assumes intake (SKILL.md Step 0) is done, dependencies are installed, and the pull and
Task Report PDF sit beside `_pipeline/` in the workspace; `data/items.json` may not exist yet.

### Step 1 — Consolidate

```bash
python3 scripts/consolidate.py <pull_dir> -o data/items.json [--only 11-30]
```

Commands here are written `python3 …` because the pipeline runs in the Linux
sandbox; `run_pipeline.sh`, `smoke_test.sh` and `install_deps.sh` resolve the
interpreter themselves, and on a Windows host the same commands are `python …`.

`--only` accepts ranges and comma lists and is **the only place scope lives**.

It emits one record per live item (number, description, sheet ref, pin stamp,
status, photos resolved to files on disk with capture time and photographer)
plus a triage summary. Read the summary first — `photo_only`, `no_photos` and
`with_room` tell you immediately how much of this report must be drafted from
images.

It handles two pull shapes automatically, both of which quietly corrupt a report
if missed:

- **`delta_<from>_to_<to>/` folders**, possibly **more than one**. Each holds
  the tasks touched in its window plus only the **new** photo binaries, and
  usually an empty `sheets.json`. A later delta is **not** a superset of an
  earlier one: one pull carried a 30-task delta and then an 8-task delta, and
  reading only the newest silently dropped items 12-30 and their photos.
  `consolidate.py` layers the base and every delta oldest-first (sorted by the
  window start date in the folder name), merges tasks by uid so a later
  revision replaces an earlier one, and indexes photos across every layer. Its
  `tasks source` line names every layer it used; read it.
- **Filler titles.** Field staff reuse a personal marker as a title (an
  initials-plus-digit marker on one job, `General` on 18 of 20 pins on
  another). Any title appearing on >=50% of pins (min 3) is treated as empty
  rather than as content.

### Step 2 — Normalise photos

```bash
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json
```

Applies EXIF rotation, letterboxes to a uniform box, and downscales. **PIL does
not apply EXIF orientation on save**, and the originals look upright in every
normal image viewer, so a missed transpose only surfaces as sideways photos in
the rendered document. On the last pull, 34 of 34 photos needed it.

### Step 6 — Sheet clips

Per-item annotated clips — the drawing with the pin stamp — come only from the
**PlanGrid Task Report PDF**.

```bash
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" build/sheet_clips_jpg \
    --items-from data/items.json --dims-out build/sheet_clip_dims_jpg.json
```

It handles three traps, all already solved — do not reimplement:

1. **Table of contents.** The first pages repeat every item heading with dot
   leaders and page numbers, so a naive search for `#N` matches the ToC entry.
   Content start is detected, not hardcoded.
2. **The reported image bbox is larger than the visible region.** PlanGrid draws
   the clip through a clip path pymupdf cannot see, so `get_image_info()` reports
   a bbox that can overrun the page edge entirely. **The crop is anchored on the
   clip box's real vector border rectangle** found via `page.get_drawings()`,
   filtered by plausible size and aspect and by sitting below the heading.
   *This replaced tuned pixel offsets from the "Sheet" text label, which were
   geometry-specific and produced silent garbage when a Task Report arrived as A4
   rather than US Letter.* **Anchor on vector geometry the producing tool actually
   drew, never on measured offsets from a text label.**
3. **Overflow.** An item near a page bottom pushes its clip to the next page with
   no repeated heading; detected, with a fallback to the following page.

It reports which items used the fallback and which are missing — read that output
rather than assuming. It also **exits non-zero on byte-identical clips for two
different pins** (every emitted clip is sha1-hashed): that has shipped once, two
items showing the same drawing, one of them therefore wrong, and nobody caught
it by eye.

**A Task Report only covers the export window it was generated for.** A
multi-visit report needs one Task Report export per visit; clips for items from
an earlier visit are simply absent from a later export. Ask for the missing
export rather than salvaging clips from a previously rendered document.


Next: `reference/drafting.md` (read every source and draft `data/drafted_items.json`).
