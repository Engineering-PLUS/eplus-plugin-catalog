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

**Where the template and scripts are.** From bash in the sandbox this skill is
at `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-punch-reports/skills/punch-report-generation/`
(`ls /sessions` gives `<session>`). The host-side path in this file's "Base
directory" line is the same folder seen by Read and Grep; it is not visible to
bash. Stamp from the plugin path every run, including re-runs that unzip a
prior package: the package supplies data and decisions, the plugin supplies
scripts.

**Tooling facts come from this skill, not from memory.** Memory entries and a
prior package's CLAUDE.md, PROCESS-LOG and LESSONS-LEARNED are good sources for
project facts: client conventions, names, addresses, what an earlier report
covered. They are not sources for what is reachable, installed, or broken on
this seat today. Egress, missing packages and script bugs are re-tested on
every run (the live photo fetch in `reference/build-data.md` is the usual
case). When a memory entry contradicts this skill on tooling, the skill wins,
and the main thread corrects that memory entry at the end of the run so the
next one does not inherit it. Workers do not read memory at all.

**Re-read `_pipeline/CLAUDE.md` whenever you resume a session, and again after a
context compaction.** Nothing loads it for you: it sits one level below the
working folder, so it is not picked up automatically, and compaction drops what
you had read. It carries this project's scope decision and the rules the
renderer bakes in, so a run that skips it re-derives them the hard way.

## Step 0 — Intake: one round, after the pull, before you start drafting

The `punch-report` command carries the full intake procedure and the exact
question set; follow it. The shape is fixed: gather first (the client profile
from the project folder, the pull, the Task Report PDF, a consolidate run with
the known rules), then **one `AskUserQuestion` call** covering scope edge
cases, issuance date, the identity block, and the cover mode. Field results
2026-09-09 and 2026-09-10: three rounds on one report cost 47 minutes of
waiting, and the cover fields that were never asked are why the reviewer
rebuilds the cover by hand.

| Input | Required? | Notes |
|---|---|---|
| `client-profile.json` | if present | client-level facts from earlier reports for this client; confirmed, not trusted blind, and written back at delivery |
| PlanGrid pull | yes | a directory containing `tasks.json`, or built from the MCP (`reference/build-data.md` Step 0b) |
| **PlanGrid Task Report PDF** | for pin clips | **not part of an API pull.** Exported separately. The only source of per-item annotated sheet clips. If it is missing, that is one of the intake questions. |
| Scope rules | yes | `SCOPE`, `TITLE`, `CREATED_AFTER`, `DROP_PHRASES`; consolidate reports the strays and near misses those rules leave open, and they go into the intake question |
| Walk notes | optional | often arrive as two near-identical files |

**The issuance date is asked, never inferred**, never today by default. It is a
contractual fact about when the report goes out and the reviewer decides it.

**The EP project number is captured at intake** into `report.config.json` as
`ep_project_no` and into the client profile. It is rendered on the cover only,
as the issued coversheet does; `verify_report.py` asserts it is on the cover
and absent from the body.

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
| Any stage is being handed to a worker (Agent tool) | `reference/worker-brief.md`, pasted verbatim at the top of the prompt |

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
# Step 0b Only when the pull comes from the plangrid MCP  -> reference/build-data.md
#         (get_tasks and list_sheets return summaries plus a packet url; never retype a
#          result into a file: pull_mcp.sh fetches the packets and checks their sha256)
bash scripts/pull_mcp.sh '<tasks packet url>#<sha256>' '<sheets packet url>#<sha256>'
python3 scripts/fetch_photos.py --pull ../plangrid_mcp              # live originals, every run
python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp   # only for photos fetch_photos could not get
python3 scripts/adapt_mcp_pull.py                                   # ../plangrid_mcp -> ../plangrid_pull

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
#         (build master, gen_report.js, fix_bookmark_ids.py, verify_report.py, in one go)
RENDER_ONLY=1 bash scripts/run_pipeline.sh

# Step 8  Verify (OOXML, then visual)         -> reference/verify-and-deliver.md
python3 scripts/render_preview.py build/<output>.docx --pages 1,4

# Step 9  Keep it editable: comments and review sheet -> reference/verify-and-deliver.md
python3 scripts/read_comments.py <reviewed>.docx            # readable
python3 scripts/read_comments.py <reviewed>.docx --json -o comments.json
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the yellow columns
python3 scripts/review_sheet.py import build Report-Review.xlsx
RENDER_ONLY=1 bash scripts/run_pipeline.sh

# Step 10 Deliver, once, through package.py   -> reference/verify-and-deliver.md
python3 scripts/package.py <workspace> "<project folder>"
```

A revision of an already-delivered report (the common case) starts from
`reference/revising.md`, not from Step 1.

## Delegating a stage to a worker

Every Agent prompt sent during a run starts with the block in
`reference/worker-brief.md`, pasted verbatim, followed only by the workspace
and project paths, the stage and its one reference file, the decisions already
made, and where to stop. Do not write worker instructions from scratch; the
brief is the instruction set, and it already forbids the things that stalled
field runs (deleting files, reading memory, studying scripts instead of running
them, talking to the user).

Workers make no decisions. A worker that reaches a decision the brief does not
cover finishes what does not depend on it, stops, and returns the question
under **Open questions** with the evidence both ways. It cannot be resumed.
The main thread settles every open question before the next worker starts:
ask the user (all questions at once, one `AskUserQuestion`) or, when the
user's intent is not in doubt, decide from house policy and the decisions
already on record. The answer goes into the next worker's brief as a settled
decision so it cannot come back. When the main thread would have to guess, it
asks. Never block inside an Agent call on something only the user can answer;
the worker cannot ask, and the user cannot reach a worker. **Files to remove**
waits for the end of the run.

## Nothing is deleted during a run

Deleting in a mounted folder needs a permission the user has to grant by hand,
with no context for what is being removed. So: no deletes, moves, or renames in
the workspace or the project folder while the run is in progress, by anyone.
Scratch goes under `_pipeline/build/_scratch/` (never packaged) or `/tmp`.
Re-deliveries get a new name from `package.py` rather than replacing the old
files. If files genuinely need removing, do it once at the very end, after
delivery and after the summary to the user: one request naming every file and
why. The session outputs folder is never cleaned; only the project folder, and
only when a re-delivery left an earlier copy behind.

## House policy

Standing decisions. Follow them unless told otherwise for a particular report:

- **Multi-condition pins stay combined in the draft** and are listed for review.
  Splitting changes item numbering, which breaks the link back to PlanGrid.
- **"Not determinable" items ship in the report**, marked as such. They are
  evidence a shot was missed and are worth seeing.
- **Suspected misfire pins are surfaced as questions**, never deleted and never
  force-described.
- **The `.docx` is the working file and the file of record.** The reviewer
  issues the report from Word. PDFs for your own layout checks are fine under
  `build/_scratch/`; a PDF is packaged only when the user asks, via
  `scripts/export_pdf.py` and `package.py --pdf`, and is described as a
  convenience copy (LibreOffice pagination), never as the issued document.

## What good looks like

A report where every item is traceable to its PlanGrid number, every description
is either the engineer's own words or clearly marked as drafted from photos, every
uncertainty appears in the issues list rather than being smoothed over, and the
reviewer's job is confirming judgment calls — not discovering that a
confident-sounding paragraph was invented.
