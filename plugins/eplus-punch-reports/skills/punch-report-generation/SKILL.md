---
name: punch-report-generation
description: Use this skill to DRAFT a punch report, field progress report, or site inspection report from raw field material — a PlanGrid project pull, a folder of site photos, an engineer's walk notes, or any combination. Trigger when asked to write up a punch walk, turn photos and notes into a report, produce a draft punch list document, or generate a deliverable from a site visit. Covers intake, consolidating messy source data, drafting descriptions in field-report voice, checking wording against EPLUS precedent, and rendering a branded one-page-per-item Word document with a live table of contents. Distinct from the `punch` skill, which QUERIES the historical corpus; this one PRODUCES a new report.
argument-hint: <folder of field material — e.g. "draft the report from the files in this folder">
---

# Drafting a punch report from field material

Turns a site walk into a reviewable draft. The human finishes and issues it —
the target is ~80% of the way there with every uncertainty surfaced, not a
publishable document.

$ARGUMENTS

**The pipeline is a stampable project template, not a set of loose scripts.**
Build a workspace in the session's own outputs area (your working folder, never
the user's project folder): copy `template/` into it, copy `scripts/` into
`_pipeline/scripts/`, and copy the inputs (the PlanGrid pull and the Task Report
PDF) in beside `_pipeline/` once. Work only there. The template's
`_pipeline/CLAUDE.md` is the operating manual for that project and is the file
a future run reads first — fill it in as you go rather than at the end.

**Re-read `_pipeline/CLAUDE.md` whenever you resume a session, and again after a
context compaction.** Nothing loads it for you: it sits one level below the
working folder, so it is not picked up automatically, and compaction drops what
you had read. It carries this project's scope decision and the rules the
renderer bakes in, so a run that skips it re-derives them the hard way.

## Step 0 — Intake, before you start drafting

Confirm all four before touching the data. Two of these have been discovered
mid-run before, which costs a restart:

| Input | Required? | Notes |
|---|---|---|
| PlanGrid pull | yes | a directory containing `tasks.json` |
| **PlanGrid Task Report PDF** | for pin clips | **not part of an API pull.** Exported separately. The only source of per-item annotated sheet clips. |
| Scope | yes | which item numbers this report covers, and what a prior report already covered |
| Walk notes | optional | often arrive as two near-identical files |

**Ask for the Task Report and the scope up front.** Both were mid-run
discoveries on the last job. If the Task Report is genuinely unavailable the
pipeline still runs and items render `(no pin clip)`, but say so before drafting
rather than after.

**Use `AskUserQuestion` to get the issuance date.** Do not infer it, do not use
today's date, and do not leave it blank. The issuance date is a contractual fact
about when the report goes out, which is a decision the reviewer makes and often
differs from both the walk date and the date the draft was compiled. Ask it
explicitly as part of intake, alongside the walk date and scope.

**The EP project number is internal tracking and is never rendered.** It lives in
`report.config.json` as `ep_project_no` so runs stay traceable on our side, but it
must not appear anywhere a client, GC or subcontractor reads, including the cover.
`verify_report.py` asserts it is absent from the document text, so this fails the
build rather than shipping.

Then install the dependencies and check the tooling actually works:

```bash
bash scripts/install_deps.sh && bash scripts/smoke_test.sh
```

The sandbox ships without PyMuPDF and without the `docx` Node package, and Node
only resolves `docx` from a `node_modules` beside the scripts, so the install
step is required on every fresh sandbox. It is idempotent.

This exists because a previous generation of this pipeline documented four
features its shipped code did not have. Run it; do not assume.

### The project folder is read-only until delivery

The user's project folder is where the inputs come from and where the finished
package goes. Nothing else touches it. Every step runs in the workspace, so the
share's slowness (photo normalisation has taken **over two minutes on a share
versus 2.6 seconds locally**) never enters the run, and sources and outputs
cannot drift apart because there is only one copy of each.

That second point is the real reason. An earlier version of this workflow
worked in the project folder with a local scratch copy and synced back by hand;
a `drafted_items.json` edit once lived only in the scratch copy, the report was
rendered from it, and the project folder's copy was never updated, so the
document and the file that generates it disagreed and a re-run would have
silently reverted the change. One workspace, one delivery, no sync step.

Delivery is `scripts/package.py <workspace> <project folder>` and nothing else
(Step 10, `reference/verify-and-deliver.md`).

## The premise: the input is always messy

This is the problem being solved, not a problem to complain about:

- **No location data.** PlanGrid's `room` field is typically empty on 100% of
  pins. The only structured location is the drawing sheet number.
- **Many pins have no description.** The photos *are* the record.
- **Notes aren't linked to pins.** Matching a note to a pin is inference from
  photo content, not a lookup. It is the fuzziest step here — treat every match
  as a claim to be checked.
- **Some pins are noise.** Camera misfires, photos of colleagues, blank walls.
- **Some pins bundle several unrelated conditions.**

**Never ask the field to fix this before you can work.** Infer what is
inferable, label what was inferred, and surface what is not determinable.

**Measure this pull rather than assuming it.** Data quality varies widely
between jobs: one recent pull was 80% authored with 100% valid sheet refs, well
above the pessimistic baseline. Read the triage summary from Step 1 (`reference/build-data.md`) and set the
bar from the data in front of you.

## Stage router — read one reference file, not all of them

This file is the core. Everything after intake is stage-specific and lives in
`reference/`. Identify the stage from the user's ask and from what already
exists in the workspace, then **read only the reference for the current stage;
do not read them all.**

| If the user asks for / the workspace shows | Read |
|---|---|
| A fresh start with a raw PlanGrid pull; `data/items.json`, `build/thumbs_uniform/` or `build/sheet_clips_jpg/` missing | `reference/build-data.md` (Steps 1, 2, 6) |
| `data/items.json` exists but `data/drafted_items.json` does not; the user wants items written up | `reference/drafting.md` (Steps 3, 3.5, 4, 5) |
| `data/drafted_items.json` exists and the user asks about wording, voice or precedent | `reference/drafting.md` (Step 5 for precedent) |
| The user asks to render, or `build/` holds no `.docx` yet | `reference/render.md` (Step 7, the docx-only / TOC rules) |
| A `.docx` exists in `build/`; the user asks to check it, work reviewer comments, or deliver | `reference/verify-and-deliver.md` (Steps 8, 9, 10) |
| A delivered package (`.zip`) already sits in the project folder, or the user has a reviewed `.docx` back from the reviewer | `reference/revising.md` |

Each reference ends with a `Next:` line, so a full run chains through them in
order. Steps 3 to 5 are judgment, not commands: **always read
`reference/drafting.md` before writing a single description**, whatever the
stage looks like. The remaining steps can be run from the overview below when
nothing about the run is unusual; open the reference when a step misbehaves or
the user's ask is about that stage.

## Workflow overview — the command each step runs

Commands are written `python3 …` because the pipeline runs in the Linux
sandbox; on a Windows host the same commands are `python …`. Run from
`_pipeline/`. `bash scripts/run_pipeline.sh` runs Steps 1, 2, 6, 7 and the
verification in one go once `data/drafted_items.json` exists; `SCOPE=11-30`
in front of it sets the scope.

```bash
# Step 1  Consolidate                         -> reference/build-data.md
python3 scripts/consolidate.py <pull_dir> -o data/items.json [--only 11-30]

# Step 2  Normalise photos                    -> reference/build-data.md
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json

# Step 3  Read every source, diff duplicate notes   -> reference/drafting.md
# Step 3.5 Ask how the wording is set (AskUserQuestion, preview artifact)
# Step 4  Draft data/drafted_items.json       -> reference/drafting.md
# Step 5  Precedent: query_hermes_punch, then get_punch_item -> reference/drafting.md

# Step 6  Sheet clips from the Task Report PDF -> reference/build-data.md
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" build/sheet_clips_jpg \
    --items-from data/items.json --dims-out build/sheet_clip_dims_jpg.json

# Step 7  Assemble and render                 -> reference/render.md
python3 scripts/build_master.py --items data/items.json \
    --drafted data/drafted_items.json -o build/master_report_items.json
node scripts/gen_report.js build
python3 scripts/verify_report.py build/<output>.docx

# Step 8  Verify (OOXML, then visual)         -> reference/verify-and-deliver.md
python3 scripts/render_preview.py build/<output>.docx --pages 1,4

# Step 9  Keep it editable: comments and review sheet -> reference/verify-and-deliver.md
python3 scripts/read_comments.py <reviewed>.docx            # readable
python3 scripts/read_comments.py <reviewed>.docx --json -o comments.json
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the yellow columns
python3 scripts/review_sheet.py import build Report-Review.xlsx
node scripts/gen_report.js build

# Step 10 Deliver, once, through package.py   -> reference/verify-and-deliver.md
python3 scripts/package.py <workspace> "<project folder>"
```

A revision of an already-delivered report (the common case) starts from
`reference/revising.md`, not from Step 1.

## House policy

Standing decisions. Follow them unless told otherwise for a particular report:

- **Multi-condition pins stay combined in the draft** and are listed for review.
  Splitting changes item numbering, which breaks the link back to PlanGrid.
- **"Not determinable" items ship in the report**, marked as such. They are
  evidence a shot was missed and are worth seeing.
- **Suspected misfire pins are surfaced as questions**, never deleted and never
  force-described.
- **The report is .docx only.** No PDF, no LibreOffice step.

## What good looks like

A report where every item is traceable to its PlanGrid number, every description
is either the engineer's own words or clearly marked as drafted from photos, every
uncertainty appears in the issues list rather than being smoothed over, and the
reviewer's job is confirming judgment calls — not discovering that a
confident-sounding paragraph was invented.
