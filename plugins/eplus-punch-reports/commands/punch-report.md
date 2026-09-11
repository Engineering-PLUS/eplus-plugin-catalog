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

## 1. Intake: one round, after the pull, before any drafting

Field result 2026-09-09: three question rounds on one report cost 47 minutes
of waiting, and the identity fields were asked last, as plain text, at render
time. Field result 2026-09-10: the cover fields were never asked, so the cover
was rebuilt by hand. Intake is therefore **one `AskUserQuestion` call**, sent
after the data is in hand, covering everything below. Nothing on this list is
asked later unless the data forces it (a worker's Open question).

**Gather first, silently:**

1. `<project folder>/client-profile.json`, if present. It holds the
   client-level facts from earlier reports for this client (display name,
   address, EP number, inspector, reviewer, record-only drop phrases, cover
   settings). If absent, stamp `template/client-profile.json` into the
   workspace root and fill what you can.
2. The pull: an exported folder with `tasks.json` (note any `delta_*` folders),
   or the `plangrid` MCP (`list_projects`, then one `get_tasks` and one
   `list_sheets`; their packets are fetched by `scripts/pull_mcp.sh`, never
   retyped; see `reference/build-data.md` Step 0b). The Task Report PDF from the uploads or
   the project folder; it is the only source of pin clips, so if it is missing
   that becomes a question.
3. Run consolidate with the rules you already know (the profile's
   `drop_phrases`, the user's title and date filters) so the triage summary
   is in front of you: item count, deleted or archived strays, and any
   **NEAR-MISS** descriptions it reports.

**Then ask, in one call (four questions at most):**

| # | Question | Options |
|---|---|---|
| 1 | Scope edge cases the rules did not settle: strays, near-miss phrases, a pull spanning two walk dates. Name the items. Skip this question if there are none and use the slot for the Task Report if that is missing. | drop / keep / other |
| 2 | Issuance date. Never inferred, never defaulted to today; it is the reviewer's contractual decision. | today's date / the walk date / other |
| 3 | Identity, shown as one block for confirmation: project name as it reads on the cover, building or area (the subtitle), client display name and street address, EP project number, walk date (from the pin dates), who walked it, who reviews it. Prefill from the profile and the PlanGrid project; mark anything blank as "missing". | correct / change (say what) |
| 4 | Cover: generate one for review (a separate `-Cover.docx`, body page 1 left blank), the reviewer supplies their own (body page 1 left blank; ask for the file), blank page only, or none. Prefill from the profile's `cover_mode`. | template / supplied / blank / none |

Free text arrives through "Other"; read it and apply it. A PDF is not asked
about: it is made only if the user asks for one (step 6).

**Then write the answers down, once:** the per-report facts into
`_pipeline/build/report.config.json`, the client-level facts into the
workspace's `client-profile.json` (delivery copies it into the project folder,
the one file `package.py` updates in place), and the scope rules into the
`SCOPE`, `TITLE`, `CREATED_AFTER` and `DROP_PHRASES` variables recorded in
`_pipeline/CLAUDE.md`. From here on nothing about identity or scope is
re-derived or re-asked.

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
the rendered `.docx`, the `-Cover.docx` when one was generated, and the review
`.xlsx` beside it so the reviewer can start reading without unzipping. It
never overwrites an existing delivery. Run it with `--dry-run` first if you
want to see the manifest.

Two Word files go out, not one: the body, whose page 1 is intentionally blank,
and the cover (generated, or the reviewer's own). Tell the user that, and that
the blank page is where the cover goes. Offer, do not do: once the user has
both as PDFs (Word export, or `scripts/export_pdf.py` on request),
`python3 scripts/staple_pdf.py <cover.pdf> <body.pdf>` replaces the blank
page with the cover. Only after they say yes; the Word files stay the files
of record and they may still be editing.

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

The `.docx` is the working file and the file of record; the reviewer issues
the report from Word, which recalculates the page-number fields on export. A
PDF for your own layout check is fine under `_pipeline/build/_scratch/`
(`render_preview.py` does this and deletes its PDF). Package a PDF only when
the user asks for one: `python3 scripts/export_pdf.py build/<report>.docx`,
then `package.py ... --pdf`, and tell the user it is a convenience copy whose
page numbers come from LibreOffice, not the issued document.
