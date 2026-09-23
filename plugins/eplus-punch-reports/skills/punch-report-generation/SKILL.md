---
name: punch-report-generation
description: Use this skill to DRAFT a punch report, field progress report, or site inspection report from raw field material — a PlanGrid project pull, a folder of site photos, an engineer's walk notes, or any combination. Trigger when asked to write up a punch walk, turn photos and notes into a report, produce a draft punch list document, or generate a deliverable from a site visit. Builds the whole draft without stopping to ask, then lists what is missing and applies each answer as a surgical edit. Covers consolidating messy source data, drafting descriptions in field-report voice, checking wording against EPLUS precedent, and rendering a branded one-page-per-item Word document with a live table of contents. Distinct from the `punch` skill, which QUERIES the historical corpus; this one PRODUCES a new report.
argument-hint: <folder of field material — e.g. "draft the report from the files in this folder">
---

# Drafting a punch report from field material

Turns a site walk into a reviewable draft. The human finishes and issues it —
the target is ~80% of the way there with every uncertainty surfaced, not a
publishable document.

$ARGUMENTS

**The pipeline is a stampable project template, not a set of loose scripts.**
Build a workspace in the session's own outputs area (your working folder, never
the user's project folder) with **one command, and only this command**:

```bash
bash <plugin skill>/scripts/init_workspace.sh <workspace>                       # fresh run
bash <plugin skill>/scripts/init_workspace.sh <workspace> --from-package <zip>  # re-run
```

It lays the template out at the workspace root (so `<workspace>/_pipeline/CLAUDE.md`,
`build/assets/`, `build/report.config.json` and `client-profile.json` exist where
the pipeline reads them), refreshes `_pipeline/scripts/` from the plugin, makes
the tree writable, and exits non-zero naming anything missing. Never hand-roll
`cp` commands for this: on 2026-09-14 a worker copied `template/` to
`_pipeline/template/`, the first render died on a missing logo, a config was
written into the user's project folder by mistake, and the delivered package
had no CLAUDE.md, PROCESS-LOG or ISSUES-LIST at all. Then copy the inputs (the
PlanGrid pull and the Task Report PDF) in beside `_pipeline/` once. Work only
there. The template's `_pipeline/CLAUDE.md` is the operating manual for that
project and is the file a future run reads first — fill it in as you go rather
than at the end.

**Where the plugin is.** From bash in the sandbox this skill is
at `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-punch-reports/skills/punch-report-generation/`
(`ls /sessions` gives `<session>`). The host-side path in this file's "Base
directory" line is the same folder seen by Read and Grep; it is not visible to
bash. Run `init_workspace.sh` from that plugin path every run, including
re-runs from a prior package: the package supplies data and decisions, the
plugin supplies scripts (the script skips the package's `scripts/` on purpose).

**Nothing in a report comes from memory.** Project facts (client, address, EP
number, inspector, reviewer, what an earlier report covered, which version is
next, scope decisions) come from records the next engineer can also see: the
project folder's `client-profile.json`, a delivered package's CLAUDE.md,
PROCESS-LOG and LESSONS-LEARNED, PlanGrid, and the user. Tooling facts (what is
reachable, installed or broken today) come from this skill and are re-tested on
every run. Do not open memory files during a run, main thread or worker. Field
result 2026-09-23: a run read a memory note first, filled the cover, the
deleted-pin decision and the cover mode from it, and labelled them "the earlier
report record", so neither the reviewer nor the tester could tell where they
came from. `prefill_config.py` records each cover fact's source in
`report.config.json` `fact_sources`; a fact no record states stays
`[MISSING]`.

**Re-read `_pipeline/CLAUDE.md` whenever you resume a session, and again after a
context compaction.** Nothing loads it for you: it sits one level below the
working folder, so it is not picked up automatically, and compaction drops what
you had read. It carries this project's scope decision and the rules the
renderer bakes in, so a run that skips it re-derives them the hard way.

## Step 0 — Build first, ask last

The `punch-report` command carries the run order; follow it. The shape is
fixed: **no question, folder picker or confirmation before the draft exists.**
Users start a report and walk away; field results 2026-09-09 to 2026-09-14 lost
12 to 47 minutes per report to unanswered question rounds, and on 2026-09-23 a
folder picker opened with no explanation and was cancelled. So every decision
the old intake asked about has a default (the table in the command, section
4), anything unknown shows on the draft as `[MISSING: ...]` or in the finish
list, and the questions come once, at the end, with the draft already
delivered. A user who never answers still has a complete draft; one who does
gets each answer applied by `update_report.py` in seconds.

**Every default maps to a switch that exists, and so does every change.**
Deleted pins: dropped (default) or kept and bannered (`deleted_pins` in
`report.config.json`, applied at build master, so switching is a re-render).
A two-date pull: one list with the pin date on every item (default), visit
section headings (`visit_sections: "by_date"` or `visit_breaks`), or one date
only (`CREATED_AFTER` / `SCOPE`). On 2026-09-14 options were offered that the
pipeline did not have, and two workers hand-patched the data.

| Input | Found by | If absent |
|---|---|---|
| Project folder | `scripts/locate_inputs.py "<what the user typed>"` | build and deliver into the session outputs folder; ask for the folder at the end |
| `client-profile.json` | the project folder | cover facts stay `[MISSING]`; the user's answers create it at delivery |
| PlanGrid pull | a folder with `tasks.json`, or the `plangrid` MCP (`reference/build-data.md` Step 0b) | the only hard requirement |
| **PlanGrid Task Report PDF** | the project folder or uploads | **not part of an API pull**; the only source of pin clips. Build without clips; finish list |
| Scope rules | `SCOPE`, `TITLE`, `CREATED_AFTER`, `DROP_PHRASES` from the user's words or the profile | every item in the pull; near misses listed |
| Walk notes | uploads or the project folder | optional; often two near-identical files |

**The issuance date is never inferred**, never today by default: the draft
carries TBD and the finish list asks for it. It is a contractual fact the
reviewer decides.

**The EP project number comes from the profile or the user**, into
`report.config.json` as `ep_project_no` and the client profile. It renders on
the cover only; `verify_report.py` asserts it is absent from the body.

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

This file is the core. Everything after Step 0 is stage-specific and lives in
`reference/`. Identify the stage from the user's ask and from what already
exists in the workspace, then **read only the reference for the current stage;
do not read them all.**

| If the user asks for / the workspace shows | Read |
|---|---|
| **A draft exists and the user supplies a missing piece or answers the finish list** (a cover fact, an issuance date, a Task Report PDF, a folder to deliver to, a reworded item, keep or drop a pin) | **nothing: run `python3 scripts/update_report.py ...` from `_pipeline/`** (examples in the command, section 8). No worker, no rebuild |
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
# Step 0  Find the inputs and the project folder, no questions (run from the plugin path S)
python3 "$S/scripts/locate_inputs.py" "<what the user typed>"
bash "$S/scripts/init_workspace.sh" <workspace> && cd <workspace>/_pipeline \
    && bash scripts/install_deps.sh && bash scripts/smoke_test.sh

# Step 0b Only when the pull comes from the plangrid MCP  -> reference/build-data.md
#         (get_tasks and list_sheets return summaries plus a packet url; never retype a
#          result into a file: pull_mcp.sh fetches the packets and checks their sha256)
bash scripts/pull_mcp.sh '<tasks packet url>#<sha256>' '<sheets packet url>#<sha256>'
python3 scripts/fetch_photos.py --pull ../plangrid_mcp              # live originals, every run
python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp   # only for photos fetch_photos could not get
python3 scripts/adapt_mcp_pull.py                                   # ../plangrid_mcp -> ../plangrid_pull

# Steps 1, 2, 6 in one go (consolidate, photos, clips); stops cleanly before drafting
bash scripts/run_pipeline.sh
# Step 1  Consolidate                         -> reference/build-data.md
#         (run_pipeline.sh always passes --keep-deleted; build master applies deleted_pins)
python3 scripts/consolidate.py <pull_dir> -o data/items.json [--only 11-30] --keep-deleted

# Step 1b The cover from records only: profile, PlanGrid, defaults; the rest [MISSING]
python3 scripts/prefill_config.py --project-name "<PlanGrid project>" --version <next> [--project-folder <dir>]

# Step 2  Normalise photos                    -> reference/build-data.md
python3 scripts/normalize_photos.py --items data/items.json \
    --dest build/thumbs_uniform --dims-out data/thumb_dims.json

# Step 3  Read every source, diff duplicate notes   -> reference/drafting.md
#         (default: draft every item, flag the inferred ones; the per-item review loop, Step 3.5, only when the user asks)
# Step 4  Draft data/drafted_items.json       -> reference/drafting.md
# Step 5  Precedent: query_hermes_punch, then get_punch_item -> reference/drafting.md

# Step 6  Sheet clips from the Task Report PDF -> reference/build-data.md
python3 scripts/extract_sheet_clips.py "<Task Report>.pdf" build/sheet_clips_jpg \
    --items-from data/items.json --dims-out build/sheet_clip_dims_jpg.json

# Step 7  Assemble and render                 -> reference/render.md
#         (build master, gen_report.js, fix_bookmark_ids.py, verify_report.py,
#          review_sheet.py export -> build/<report>-Review.xlsx, and the finish
#          list -> build/finish.json + the top of ISSUES-LIST.md, in one go)
RENDER_ONLY=1 bash scripts/run_pipeline.sh

# Step 8  Verify: the verifier already ran; look at THREE preview pages and stop
#         (cover, one item with photos, one without)  -> reference/verify-and-deliver.md
python3 scripts/render_preview.py build/<output>.docx --pages 1,<photo item>,<no-photo item>

# Step 9  Keep it editable: comments and review sheet -> reference/verify-and-deliver.md
python3 scripts/read_comments.py <reviewed>.docx            # readable
python3 scripts/read_comments.py <reviewed>.docx --json -o comments.json
#   reviewer edits the yellow columns of build/<report>-Review.xlsx
python3 scripts/review_sheet.py import build build/<report>-Review.xlsx
RENDER_ONLY=1 bash scripts/run_pipeline.sh

# Step 10 Deliver, once, through package.py   -> reference/verify-and-deliver.md
python3 scripts/package.py <workspace> "<deliver to>"              # --replace only when the user said so
#         then the final message: what was built and where, the finish list, one AskUserQuestion

# Step 11 Every answer or missing piece afterwards: one surgical command, seconds, no worker
python3 scripts/update_report.py --set issuance_date=2026-09-30 --set ep_project_no=27625 --deliver
python3 scripts/update_report.py --task-report "<Task Report>.pdf" --deliver
python3 scripts/update_report.py --item 12 --description "..." --deleted-pins keep --deliver
```

A revision of an already-delivered report (the common case) starts from
`reference/revising.md`, not from Step 1.

## Delegating a stage to a worker

Every Agent prompt sent during a run starts with the block in
`reference/worker-brief.md`, pasted verbatim, followed only by the workspace
and project paths, the stage and its one reference file, the decisions already
made, and where to stop. Do not write worker instructions from scratch; the
brief is the instruction set, and it already forbids the things that stalled
field runs (deleting files, reading memory, studying or editing scripts instead
of running them, talking to the user). Never ask a worker to "check what a
script keys off" or to make a renderer do something the config has no switch
for: that is a plugin change, it comes back as an Open question, and the main
thread files it with `report_issue`. A `_v2` copy of a script inside a
workspace is not a fix; it is a divergence the next run cannot see.

Workers make no decisions. A worker that reaches a decision the brief does not
cover finishes what does not depend on it, stops, and returns the question
under **Open questions** with the evidence both ways. It cannot be resumed.
The main thread settles every open question before the next worker starts,
**without asking the user mid-run**: it decides from house policy and the
defaults in the command, writes the question and the choice into
`ISSUES-LIST.md` so the reviewer sees both, and puts the choice in the next
worker's brief as a settled decision. Where no default is safe (a photo that
contradicts the note, a suspected misfire), the item ships `undetermined` with
an Editor's Note and the question joins the finish list; the run does not
stop. Never block inside an Agent call on something only the user can answer.
**Files to remove** waits for the end of the run.

## Nothing is deleted during a run

Deleting in a mounted folder needs a permission the user has to grant by hand,
with no context for what is being removed. So: no deletes, moves, or renames in
the workspace or the project folder while the run is in progress, by anyone.
Scratch goes under `_pipeline/build/_scratch/` (never packaged) or `/tmp`.
Re-deliveries get a new version name, never an overwrite. The one exception is
the project folder's own tidy-up at delivery: `package.py` writes the earlier
versions of the report into the new package (`previous-versions/`) and removes
them from the folder only after verifying the copies, so the folder holds the
current version and the inputs. When Cowork has not yet allowed deletes there,
it prints `CLEANUP PENDING` with a message for the user that names every file
to be deleted and why: post that message as written, **before** the one
`allow_cowork_file_delete` call (the approval covers the folder; the prompt
itself names one file and gives no reason), then `package.py --prune
"<folder>"`. Nothing else is ever deleted
by the run, and the session outputs folder is never cleaned.

## House policy

Standing decisions. Follow them unless told otherwise for a particular report:

- **Multi-condition pins stay combined in the draft** and are listed for review.
  Splitting changes item numbering, which breaks the link back to PlanGrid.
- **"Not determinable" items ship in the report**, marked as such. They are
  evidence a shot was missed and are worth seeing.
- **Suspected misfire pins are surfaced as questions**, never deleted and never
  force-described.
- **Pins PlanGrid has deleted or archived are dropped**, and listed in the
  finish list. `items.json` keeps them flagged `deleted_in_plangrid`; build
  master applies `deleted_pins` from `report.config.json`, so "keep them,
  marked" is `update_report.py --deleted-pins keep`, a re-render: the renderer
  prints a red DELETED IN PLANGRID banner and marks the TOC entry. Draft the
  deleted pins along with the rest so that switch needs nothing else. Nobody
  types a deleted pin into `items.json`.
- **Date Recorded is the pin's own creation date**, on every item, from
  `created_at`. Photo timestamps are never the source. A pull spanning two walk
  dates therefore reads correctly as a flat list; visit section headings are an
  option on top of that (`--set visit_sections=by_date`), never a substitute for the dates.
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
