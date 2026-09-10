---
description: Draft a punch report from a PlanGrid pull — builds the whole pipeline in the session workspace, consolidates, drafts, checks precedent, renders and verifies, then delivers one package to the project folder.
argument-hint: [project folder, or leave blank to use the current one]
---

Draft a punch report from field material.

Project folder: $ARGUMENTS (if blank, use the current working folder).

Load the `punch-report-generation` skill and follow it. This command is the
intake and scaffolding front end for that workflow; the skill is the authority
on every step. The skill's SKILL.md is the core (intake, premise, stage
router, one-line step overview); its stage router names the one
`reference/<stage>.md` file to read for the stage you are in, so read that
file rather than all of them.

**The project folder is read-only until the very end.** You read the inputs
from it once, do every step in your own workspace, and the only write to the
project folder is the single delivery in step 6. Never create, edit, or copy
individual files there mid-run; that is how a rendered document and the file
that generates it have disagreed before.

## 1. Intake, before anything else

Inspect the project folder and report what you found, then confirm the four
inputs with the user in **one** message rather than discovering them mid-run:

- **The PlanGrid pull** — a directory containing `tasks.json`. Say how many
  items it holds, and whether a `delta_<from>_to_<to>/` folder is present (if
  so, the delta is the authoritative task list and you need both photo
  directories plus the base's `sheets.json`).
- **The PlanGrid Task Report PDF** — **not part of an API pull**, exported
  separately, and the only source of the per-item annotated sheet clips. If it
  is absent, ask for it. The pipeline still runs without it, but every item
  renders `(no pin clip)`, so this is the user's call to make knowingly.
- **Scope** — which item numbers this report covers. If the pull spans more
  than one walk date, say so and propose a split; do not assume. Whatever is
  agreed becomes `SCOPE`, and that is the only place scope lives.
- **Report identity** — project name, building/area, walk date, who walked it,
  and who reviews it. These fill `build/report.config.json`.
- **Issuance date** — ask this one with `AskUserQuestion`. Never infer it, never
  default to today. It is a contractual fact about when the report goes out, it is
  the reviewer's decision, and it routinely differs from both the walk date and
  the compile date.
- **EP project number** — capture it into `report.config.json` as `ep_project_no`
  for our own traceability, and make sure it is **not rendered**. It is internal
  tracking, not client-facing, including on the cover. `verify_report.py` fails the
  build if it reaches the document text.

Ask about anything genuinely ambiguous here. Everything after this point is
expensive to redo.

## 2. Build the workspace

Create a workspace folder in the session's own outputs area (your working
folder, not the project folder), named after the report, for example
`<project>-punch-<walkdate>/`. Then:

1. Copy the skill's `template/` into the workspace, and its `scripts/` into
   `_pipeline/scripts/`. **From bash in the sandbox the plugin lives at**
   `/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-punch-reports/skills/punch-report-generation/`
   (`<session>` is the first path segment under `/sessions/`; `ls /sessions`
   shows it). `${CLAUDE_PLUGIN_ROOT}` is the same folder as seen by host tools
   (Read, Grep) and does not exist inside the sandbox, so do not `find /` for
   it and do not conclude the plugin is unreachable.
2. Copy the inputs **once** from the project folder into the workspace root:
   a pre-exported PlanGrid pull directory (base and any delta) and the Task
   Report PDF. `run_pipeline.sh` finds them there automatically, beside
   `_pipeline/`. If the pull comes from the `plangrid` MCP instead of a folder,
   follow "Pulling from the MCP" in `reference/build-data.md`: raw material
   goes to `plangrid_mcp/`, `scripts/adapt_mcp_pull.py` writes `plangrid_pull/`.
3. Fill in `_pipeline/build/report.config.json` from the identity answers, and
   replace the `<PLACEHOLDER>` fields in `_pipeline/CLAUDE.md` with this
   project's real values as you learn them. That file is what the next run
   reads first.

If the project folder already holds a delivered package from a prior run,
unzip that package into the workspace instead of stamping a fresh template,
**then overwrite `_pipeline/scripts/` from the plugin path above**. The
package carries that run's data and decisions; the plugin carries the current
scripts. A package's scripts are never the source for a new run, even when
they look newer, because a fix made inside one session's workspace is not a
plugin fix. Report what you found and carry on from there; this is a re-run.

The scripts in the plugin are the only scripts. If one is wrong, fix it in the
workspace to finish the run, then say so in `LESSONS-LEARNED.md` and file it
with `report_issue` so the plugin gets the fix; do not rely on memory or on the
next package to carry it.

## 3. Install dependencies and check the tooling

```bash
cd <workspace>/_pipeline && bash scripts/install_deps.sh && bash scripts/smoke_test.sh
```

The sandbox does not ship PyMuPDF or the `docx` Node package, and Node only
finds `docx` in a `node_modules` beside the scripts, so the install step is
needed on every fresh sandbox. It is idempotent and quiet when everything is
already present. Fix or report anything the smoke test still flags before
drafting.

## 4. Stay in the workspace

Everything in steps 4 and 5 happens inside the workspace. Every step reads and
writes there, so sources and outputs can never drift apart, and none of it is
slowed by or visible on the project share until it is finished.

Nothing is deleted, moved, or renamed in the workspace or the project folder
while the run is in progress, by you or by a worker. Scratch goes under
`_pipeline/build/_scratch/`. When you hand a stage to a worker, the prompt
starts with the block in `reference/worker-brief.md`, verbatim; workers come
back with "Open questions" (ask them once, after the worker returns) and
"Files to remove" (handled in step 7, never before).

## 5. Run the workflow

Follow the skill: consolidate, normalise photos, read the sources, draft every
item in field-report voice, check precedent (two-step: search, then
`get_punch_item` before quoting), extract sheet clips, build master, render,
verify.

`bash scripts/run_pipeline.sh` runs steps 1 through 5 plus verification once
`data/drafted_items.json` exists.

## 6. Deliver one package

When verification passes and the issues list and handoff are written, deliver
with a single command:

```bash
python3 scripts/package.py <workspace> "<project folder>"
```

It zips the entire workspace (pipeline, sources, data, build, handoff; not
`node_modules` or caches) into `<report>.zip` in the project folder and places
the rendered `.docx` and the review `.xlsx` beside it so the reviewer can start
reading without unzipping. It refuses to overwrite an existing delivery. Run it
with `--dry-run` first if you want to see the manifest.

That command is the only write to the project folder in the whole run. If a
delivery already exists there, `package.py` suffixes the new files rather than
replacing anything; it never needs the old ones removed. Tell the user what was
delivered and where.

## 7. Cleanup, last, and only if there is something to clean

After delivery and after the summary to the user, look at every "Files to
remove" list the workers returned. Files inside the session outputs folder
stay; the session discards them. Only the project folder is ever cleaned, and
only when a re-delivery left an earlier copy behind. If there is something to
remove there, make one request that names every file and says why, and let the
user decide. That is the only point in the run where a delete is allowed.

Do not generate a PDF. The reviewer produces it from Word, which recalculates
the page-number fields on export.
