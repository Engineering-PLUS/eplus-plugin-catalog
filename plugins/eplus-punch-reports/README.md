# EPLUS Punch Reports

Two halves of the same job. **Produce** a punch report from a PlanGrid pull, and
**search** four years of EPLUS punch walks for the precedent that makes its
wording defensible.

## Producing a report

```
/punch-report [project folder or PlanGrid project]
```

**Build first, ask last (0.9.0).** Users start a report and walk away, so the
run never stops for a question, a confirmation or the folder picker before the
draft exists. `scripts/locate_inputs.py` finds the connected project folder, the
pull, any Task Report PDF and the next version on its own; with no folder
connected the report is built and delivered into the session outputs folder.
Every decision the old intake round asked about has a default (deleted pins
left out, issuance date TBD, one flat list with pin dates, every item drafted
and the inferred ones flagged). Cover facts come only from the project folder's
`client-profile.json` and PlanGrid (`scripts/prefill_config.py`, never from
memory), and whatever no record states renders on the cover as a red
`[MISSING: ...]` marker. After every render `scripts/finish_list.py` lists what
the draft still needs, each gap with the one command that supplies it; the
final message carries that list and asks its questions only then.

**Missing pieces are surgical edits, not rebuilds.** `scripts/update_report.py`
applies an answer (a cover fact, an issuance date, a Task Report PDF that
arrived later, a reworded item, keep or drop a pin, the folder to deliver to),
re-renders in seconds with no worker, verifies, logs the change and delivers
the next version (v0.1 to v0.2). A delivery to a folder that holds a Task
Report PDF picks it up in the same call. In a later session the workspace is
rebuilt from the delivered package in three commands.

**The project folder stays tidy (0.9.2).** It holds the current version (body,
cover, review sheet, package), `client-profile.json` and the user's own inputs,
nothing else. Each delivery writes the earlier versions into the new package
under `previous-versions/` and removes them from the folder only after the
copies are verified; the first time in a folder, Cowork asks the user once to
allow deletes there (`package.py` prints `CLEANUP PENDING` and the follow-up
`--prune` command).

The pipeline itself: `scripts/init_workspace.sh` stamps it into the session
workspace (the one supported way to lay a workspace out; it refuses to finish
with anything missing), then consolidate, draft in field-report voice, check
precedent, extract the annotated sheet clips, render, verify. Output is a
**.docx**, the file of record: one page per item, a real Word table of contents
field, native EPLUS letterhead, the pin's own date on every item, optional
visit section headings, and deleted PlanGrid pins kept and bannered when the
reviewer wants the numbering intact.

On Cowork the plugin is mounted read-only in the VM, and copies inherit that
mode. `init_workspace.sh` makes the stamped workspace writable immediately after
the template copy, before it creates `_pipeline/scripts/` (0.8.4; in 0.8.0 to
0.8.3 a fresh workspace failed with "Permission denied" on that folder).

The Word file is the file of record; the reviewer issues the report by exporting
it from Word, which recalculates the TOC page-number fields. PDFs for the
model's own layout checks are fine and stay out of the package. When the user
asks for a PDF from the pipeline, `scripts/export_pdf.py` produces a clearly
labelled convenience copy (two LibreOffice passes, so its page numbers match
its own pagination) and `package.py --pdf` delivers it beside the zip.

**Testing:** `/eplus-acceptance:test-punch [project] [days back]` (eplus-acceptance
plugin, eplus-verification catalog, testing profiles only) runs a scripted, token-minimal
smoke test of the workspace flow, the build rules, `package.py`, and the
`plangrid` MCP route (`list_projects`, `list_sheets` and `get_tasks`
summaries, then `pull_mcp.sh` fetching the sha256-checked packets,
`fetch_photos.py`, `adapt_mcp_pull.py` and `consolidate.py` on them, which
also shows whether the sandbox can reach the MCP host), for capturing
evidence in a session export. It is not shipped in this plugin.

The MCP's bulk tools return summaries; the full JSON stays on the MCP host as
a packet that `scripts/pull_mcp.sh` fetches. The model never retypes a tool
result into a file (0.7.4; the first field test spent 34k output tokens and
five minutes doing exactly that).

The project folder is read-only until the end; the run finishes with one
delivery (`scripts/package.py`): a zip of the workspace plus the `.docx`, the
`-Cover.docx` and the review `.xlsx` beside it. The zip carries what the next
run needs and prints what it left out (scratch, caches, earlier renders,
duplicate raw photos, a template stamped into the wrong place); a re-delivery
is suffixed by default and overwrites only with `--replace`. Inside the
package:

```
_pipeline/
  CLAUDE.md              this project's operating manual, read first
  scripts/               the pipeline scripts, smoke test, and packager; also the
                         MCP-pull route (fetch_photos.py for the originals,
                         extract_pdf_photos.py as the fallback, adapt_mcp_pull.py)
  data/                  items.json (facts) + drafted_items.json (judgment)
  build/                 what the renderer reads, report.config.json, the .docx
  ISSUES-LIST.md         what is still missing (generated, with commands), then
                         open questions for the reviewer
  PROCESS-LOG.md         inputs, decisions, review rounds, verification
  LESSONS-LEARNED.md     what broke, and what should change in the skill
  handoff/HANDOFF.md     entry point for the next run
```

Four deliverables come out, not one: the draft body (page 1 left blank for the
coversheet), the cover as its own Word file when one is generated, the issues
list, and the handoff. The issues list is where the reviewer's attention gets
directed. The cover layout is measured from the issued EPLUS coversheet and
driven entirely by `report.config.json`; the reviewer can use it, edit it, or
swap in their own, and `scripts/staple_pdf.py` puts a cover PDF in front of the
body PDF on request.

## Searching the corpus

The `punch-knowledge-hub` MCP server is delivered as a **managed connector from
the desktop bootstrap configuration**, not bundled with this plugin: the plugin
no longer ships a `.mcp.json`. The managed server **must be named
`punch-knowledge-hub`**, because the `punch` skill addresses its tools as
`mcp__punch-knowledge-hub__<tool>` and those names only hold under that server
name. It is backed by **724 punch items and 41 narrative report bodies** from
41 published EPLUS reports (2022–2026) across nine data center projects:
NVA02E, NVA05A, NVA05D, POR03B, POR03C, CHI01A, SVY01D, SVY01E, SVY01F.

Each item carries the field engineer's own description, the live
open/closed/pending status from PlanGrid, the drawing sheet it was pinned to, and
site photos with generated captions.

| Tool | Purpose |
|---|---|
| `punch_stats` | Aggregate counts by status, trade, project, sheet, or a trade-by-status matrix. The tool for counts and closeout percentages. |
| `list_punch` | Filtered listing of IDs, titles, trades, sheets, statuses. The browse tool. |
| `get_punch_item` | One item verbatim. **The only tool to quote wording from.** |
| `grep_punch` | Exact/regex search over titles, sheet refs, descriptions, captions. For device IDs and part numbers. |
| `query_hermes_punch` | Keyword + metadata search with a synthesized summary, plus temporary photo and sheet links. For descriptive and recurring-theme questions. |
| `export_punch_report` | Builds a spreadsheet of matching items and returns a download link. |

All six are read-only — this plugin cannot modify the punch database.

Response sizes vary by more than 50x across these tools, so routing matters:
`punch_stats` answers a count in ~120 tokens where a search costs ~6,400. The
`punch` skill carries the routing table and the measured figures.

## Skills

- **`punch`** — the query workflow, the exact filter vocabulary (trades, project
  codes, statuses, sheet references), response-size budgets, and the real
  behaviour of the `trade` filter. Load before calling any engine tool.
- **`punch-report-generation`** — produces a new report from raw field material.
  Assumes the input is messy because it always is, and surfaces what it cannot
  determine instead of inventing it. Carries the pipeline, the project template,
  and the rendering defaults that were learned the hard way. `SKILL.md` is a
  short core (build first, premise, a stage router, the command per step); the
  step detail lives in `reference/` as one file per stage (`build-data`,
  `drafting`, `render`, `verify-and-deliver`, `revising`), loaded one at a
  time for the stage the run is in.
- **`plangrid-extraction`** — how PlanGrid PDFs store their data, for when someone
  drops a raw punch report into the chat.

## Hooks

None, as of 0.6.5. The three that used to ship were removed after two field
sessions showed about 600 PowerShell spawns for one useful nudge:

- the PreToolUse PDF guard (0.6.4): the PDF policy changed, nothing left to deny;
- the Write/Edit voice check: it received the sandbox path of
  `drafted_items.json`, which the Windows host cannot open, so it never fired;
  `build_master.py` enforces the same rules inside `run_pipeline.sh`;
- the post-render verify reminder: `RENDER_ONLY=1 bash scripts/run_pipeline.sh`
  is now the only supported render command and runs the verifier itself.

`PostToolUseFailure` belongs to the `error-reporting` plugin.

## Typical asks

- "Draft the punch report from the files in this folder."
- "What telecom issues keep coming up at NVA05A?"
- "Show me the open security items on sheet T02-01B with photos."
- "Export all open POR03C items to a spreadsheet."
- "What was punch item POR03B-277?"

## Notes

Photo, drawing, and spreadsheet links are temporary (about 7 days) — save
anything worth keeping. Status values are live from PlanGrid, so an item a
published PDF shows as open may since have been closed.

Pipeline dependencies are installed by `scripts/install_deps.sh` (PyMuPDF,
Pillow, openpyxl from `requirements.txt`; the `docx` Node package from
`package.json`) and checked by `scripts/smoke_test.sh`, which also exercises
the workspace stamper, the deleted-pin and pin-date paths, the visit-section
render, the packager's manifest rules, the review-sheet naming, and the
build-first flow end to end (input discovery, prefill from records, the
`[MISSING]` cover, the finish list, surgical updates and versioned
re-delivery).

Workers never edit the scripts during a run. A needed code change comes back
to the main thread as an open question, is recorded in the workspace's
`LESSONS-LEARNED.md`, and is filed with `report_issue` so it lands here, not
in a `_v2` copy inside one session's workspace.
