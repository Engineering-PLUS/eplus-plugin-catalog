# Build the data: Steps 1, 2 and 6

Covers consolidating the PlanGrid pull, normalising photos and extracting sheet clips.
Assumes the inputs were located (SKILL.md Step 0, `locate_inputs.py`), dependencies are
installed, and the pull and any Task Report PDF sit beside `_pipeline/` in the workspace; `data/items.json` may not exist yet.

### Step 0b — Pulling from the MCP (when there is no pre-exported pull folder)

The `plangrid` MCP's bulk tools return a **summary** (counts, a short index,
a `packet`) and keep the full JSON on the MCP host as a packet file. The
model reads the summary and decides; the sandbox fetches the packet. Raw
material goes in `<workspace>/plangrid_mcp/` (beside `_pipeline/`), the
adapted pull in `<workspace>/plangrid_pull/`, which `run_pipeline.sh` finds on
its own.

**Never copy a tool result into a file with Write or Edit.** Bulk results
arrive with a packet `{url, bytes, sha256, fetch}`; `pull_mcp.sh` fetches it
and proves the bytes by sha256. On the first field test the model retyped
60 KB of inline results (34k output tokens, five minutes, one corrupted uid).
Do not ask for `detail="full"` in a report run.

1. **Three MCP calls, summaries only.** `list_projects(query="<fragment>")`
   for the uid (newest first, active projects). Then
   `get_tasks(project_uid, since="<walk date>")` (or `numbers=[...]`): read
   `coverage` (selected_count, not_found, failed, photo counts) and the
   `index` (one line per task: number, sheet, photos, status, title) to settle
   scope; note `packet.url` and `packet.sha256`. Then `list_sheets(project_uid)`:
   note `untitled` and its packet. Do not call `get_task` per item: the client
   sends tool calls one at a time, so N calls cost N round trips (thirty-three
   took 52 seconds on 2026-09-09). `get_task` remains for one item;
   `pull_tasks` for a change manifest against the previous pull.
2. **Fetch the packets** (one command, both files):
   ```bash
   bash scripts/pull_mcp.sh '<tasks packet url>#<sha256>' '<sheets packet url>#<sha256>'
   ```
   It writes `../plangrid_mcp/tasks.json` and `sheets.json`, checks the sha,
   validates the JSON and prints one line per file. A 404 means the packet
   expired (7 days): call the tool again. No `mcp_photo_urls.json` is needed;
   `fetch_photos.py` builds it from the photos inline in `tasks.json`.
3. **Fetch the originals, every run:**
   ```bash
   python3 scripts/fetch_photos.py --pull ../plangrid_mcp
   ```
   This is not optional and is not skipped because a memory note, a prior
   package, or last week's run said the photo host was blocked. Reachability is
   a property of the seat on the day. The originals are full resolution; the
   fallback below yields about 350 x 620 px, which is visibly soft in the
   rendered grid.
4. **Only if the fetch reported failures**, recover the missing photos and the
   sheet names from the Task Report PDF:
   ```bash
   python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp
   ```
   It skips photos the live fetch already got. If the failure was an egress
   block, file the host with `request_egress_allow` (error-reporting skill) and
   carry on; do not stop the run for it.
5. **Adapt:**
   ```bash
   python3 scripts/adapt_mcp_pull.py        # ../plangrid_mcp -> ../plangrid_pull
   ```
   It coerces the string fields, nests the annotation and photo counts the way
   `consolidate.py` expects, builds `sheets.json` from the MCP names or the PDF
   names, and copies each photo from `photos/` first and `pdf_photos/` second.
   **Sheet titles** ("T01-01, TECHNOLOGY SITE PLAN") come from the `sheet`
   object on each `get_tasks` row and from the saved `list_sheets` result;
   the adapter takes them in that order, then the Task Report's numbers
   (no titles), then the client profile's `sheet_titles` map as an override
   for a drawing PlanGrid itself has no title for. Before MCP 0.7 the server
   returned no sheet list at all and MCP-built reports showed the number
   alone (field result 2026-09-10); the adapter and the run record still say
   when a title is missing, and the delivery summary must repeat it.
   Its last line, `photo route : live | pdf | mixed`, goes into
   `PROCESS-LOG.md` and the workspace `CLAUDE.md` verbatim, with the failed host
   when it is not `live`.

### Step 1 — Consolidate

```bash
python3 scripts/consolidate.py <pull_dir> -o data/items.json [--only 11-30]
```

Commands here are written `python3 …` because the pipeline runs in the Linux
sandbox; `run_pipeline.sh`, `smoke_test.sh` and `install_deps.sh` resolve the
interpreter themselves, and on a Windows host the same commands are `python …`.

`--only` accepts ranges and comma lists and is **the only place scope lives**.
Three more rules, from the user's own words or the client profile, all passed through by
`run_pipeline.sh` (`SCOPE`, `TITLE`, `CREATED_AFTER`, `DROP_PHRASES`):

- `--title "Visit 2"` keeps only items with that title (the walk marker).
- `--created-after 2026-08-31` keeps only items created after that date.
- `--drop-phrase "Observation only for record"` (repeatable; the client
  profile's `drop_phrases` list) drops items whose whole description is that
  phrase. A description that shares the phrase's first two words but is not
  the phrase ("Observation only, ignore.") is reported as **NEAR-MISS** and
  kept; it goes into the finish list (`update_report.py --drop N`), and if the
  user drops it the phrase can join the profile's `drop_phrases` for next time.

Deleted and archived items: `run_pipeline.sh` always passes `--keep-deleted`
(0.9.0), so they stay in `items.json` with `deleted_in_plangrid: true` and the
drafter writes them up like any other item (a one-line "Pin note reads only Up,
with no accompanying photograph." is a valid write-up). Whether they reach the
report is decided at build master by `report.config.json` `deleted_pins`:
`drop` (the default; they are listed in the finish list) or `keep` (the
renderer banners them), switched later with `update_report.py --deleted-pins`.
Never type a deleted pin back into `items.json` by hand; that is the retyping
this pipeline exists to prevent. Every item also carries the pin's
`created_at`, which is what the report's Date Recorded row prints. The strays,
deleted pins and near misses consolidate reports become finish-list entries;
none of them is a question before the build.

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

It also writes `build/sheet_clip_similarity.json`: pairs of clips whose
difference hashes are within a small Hamming distance are `near_identical`,
which means two pins at nearly the same spot on the same sheet (the MCP rows
carry no pin coordinates; the clip, centred on its pin, is the position
signal). With `consolidate.py`'s shared-photo check this is the only evidence
a draft may use to call two items a possible duplicate; see
`reference/drafting.md`.

**A Task Report only covers the export window it was generated for.** A
multi-visit report needs one Task Report export per visit; clips for items from
an earlier visit are simply absent from a later export. Ask for the missing
export (a finish-list entry, `update_report.py --task-report`) rather than
salvaging clips from a previously rendered document.


**Handing this stage to a worker:** the main thread runs
`init_workspace.sh` itself first (one command, see SKILL.md); a worker never
lays out a workspace. Then paste `reference/worker-brief.md`, name this file,
the workspace and project paths, the scope, and "stop after Step 6; report the
triage summary, the photo route, and the sheet-clip result". Give it the drop
rules in force (record-only phrases, title and date filters) as settled
decisions; deleted pins need no rule at this stage, they are always kept and
flagged. Anything those rules do not cover, a stray pin or a near-miss phrase,
the worker reports; the main thread leaves it in at its default and lists it
in the finish list.

Next: `reference/drafting.md` (read every source and draft `data/drafted_items.json`).
