# Revising an existing report

Covers every round after the first delivery: the user supplies something the
draft was missing, rewords items, changes a decision, or returns a reviewed
`.docx`. Assumes a delivered package (`.zip`) exists in the project folder or
the session outputs folder.

## Supplying a missing piece or changing a decision: one command

Almost every revision is small: an EP number, a walker's name, an issuance
date, a Task Report PDF that arrived later, a pin to drop or keep, a sentence
reworded. Each is one `update_report.py` call from `_pipeline/`, several in one
call when they arrive together. It edits the config or the drafts, re-renders
(build master, render, verify, run record, review sheet, finish list; seconds
on a normal report), logs the change in `PROCESS-LOG.md`, and with `--deliver`
packages the next version beside the earlier one:

```bash
python3 scripts/update_report.py --set ep_project_no=27625 --set inspector="Leo Manning" \
    --set issuance_date=2026-09-30 --deliver
python3 scripts/update_report.py --task-report "<path>/PlanGrid Task Report.pdf" --deliver
python3 scripts/update_report.py --deleted-pins keep --deliver
python3 scripts/update_report.py --item 12 --description "..." --corrective-action "..." --deliver
python3 scripts/update_report.py --drop 7,19 --deliver
python3 scripts/update_report.py --deliver "<folder the user just connected>"
```

**Never for these:** a worker, a fresh workspace in the same session, the data
steps, re-reading the references, or re-drafting items the change does not
touch. Field result 2026-09-09: a user who supplied the project name, the
walker and the EP number waited 8 minutes while a worker re-rendered; the same
change is now a single command.

Supplied cover facts are recorded as `fact_sources: user` and client-level ones
(client name, address, EP number, inspector, reviewer, cover mode) are written
to `client-profile.json`, which `package.py` delivers into the project folder
so the next report for this client starts with them.

## In a new session: rebuild the workspace from the package, then the same commands

The workspace lives in one session's outputs folder and is gone in the next.
The delivered package carries everything the render needs (data, drafts,
config, photos, clips, paperwork). Three commands bring it back:

```bash
S=/sessions/<session>/mnt/.local-plugins/marketplaces/eplus-claude-plugins/plugins/eplus-punch-reports/skills/punch-report-generation
bash "$S/scripts/init_workspace.sh" <new workspace> --from-package "<project folder>/<package>.zip"
cd <new workspace>/_pipeline && bash scripts/install_deps.sh
python3 scripts/update_report.py <changes> --deliver
```

`locate_inputs.py` names the newest package in the project folder. The package
supplies the data and decisions; the plugin supplies the scripts (the stamper
skips the package's `scripts/` on purpose). No smoke test is needed for an
update; the first run ran it.

## A reviewed .docx comes back

- **The reviewer's Word edits are the senior source.** Rebuilding from scratch
  discards them. To recover approved wording from a reviewed .docx, use
  `scripts/import_reviewed_docx.py`, **a PROTOTYPE that has not yet been run
  end to end as one program**; it was assembled from ad hoc code that recovered
  16 write-ups once. It matches embedded photos to normalised thumbnails by
  **32×32 greyscale pixel signature** (exact, unlike caption timestamps, which
  collide the moment two photos share a minute) and emits drafted entries with
  `"origin": "reviewer_final"`. It also reveals photos the reviewer silently
  deleted. Check every entry it writes against the reviewed document before
  rendering from it. Comments come back with `scripts/read_comments.py`; apply
  each with `update_report.py --item N ...`.
- **`origin: reviewer_final` and `origin: user_reviewed` text is untouchable.**
  `build_master.py` refuses to sanitize-rewrite it and fails loudly if it would
  have to; the voice guard does not apply to it. Fix source text explicitly or
  not at all.
- **Reviewer pin merges live in the judgment layer.** Record them as a `merges`
  block in `drafted_items.json`: `{"items": [...], "merges": [{"into": 22,
  "from": 23, "drop_photos": ["…"]}], "omit": [...]}`. `build_master.py`
  applies merges in memory (photos folded in chronological order, deduped by
  uid, titles matching a `drop_photos` substring dropped, absorbed pin
  auto-omitted) and leaves out every pin in `omit`. Never mutate `items.json`
  to represent a human decision; a re-run of consolidate would erase it.
- **New site visits need their own Task Report export** for sheet clips (see
  Step 6 in `reference/build-data.md`); do not salvage clips from the previous
  render. When it arrives: `update_report.py --task-report <pdf>`.
- **A scope change is a re-run of the data steps, inside the same command:**
  `update_report.py --scope 11-30` (or `--title-filter`, `--created-after`,
  `--drop-phrases`). The run record, the CLAUDE.md figures, the review sheet
  and the finish list follow. Items the new scope brings in have no draft yet;
  the build names them, and those are the only items to draft before running
  the same command again. Hand-edit only `ISSUES-LIST.md` below the generated
  block and the scope paragraph in `PROCESS-LOG.md`. Never start a worker to
  renumber documents.

Next: `reference/drafting.md` only for items that have no draft yet, then `update_report.py`.
