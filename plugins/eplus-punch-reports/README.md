# EPLUS Punch Reports

Two halves of the same job. **Produce** a punch report from a PlanGrid pull, and
**search** four years of EPLUS punch walks for the precedent that makes its
wording defensible.

## Producing a report

```
/punch-report [project folder]
```

Builds a complete pipeline in the session workspace, then walks the run: intake,
consolidate, draft in field-report voice, check precedent, extract the annotated
sheet clips, render, verify. Output is a **.docx only** — one page per item, live
Word table of contents, native EPLUS letterhead.

The reviewer generates the PDF from Word. That is deliberate: Word recalculates
the TOC page-number fields on open and on export, and LibreOffice does not.

**Temporary:** `/test-punch` runs a scripted, token-minimal smoke test of the
hooks, the workspace flow, and `package.py` with no real data, for capturing
evidence in a session export. Remove `commands/test-punch.md` before wide
rollout.

The project folder is read-only until the end; the run finishes with one
delivery (`scripts/package.py`): a zip of the whole workspace plus the `.docx`
and review `.xlsx` beside it. Inside the package:

```
_pipeline/
  CLAUDE.md              this project's operating manual, read first
  scripts/               the pipeline scripts, smoke test, and packager
  data/                  items.json (facts) + drafted_items.json (judgment)
  build/                 what the renderer reads, report.config.json, the .docx
  ISSUES-LIST.md         open questions for the reviewer
  PROCESS-LOG.md         inputs, decisions, review rounds, verification
  LESSONS-LEARNED.md     what broke, and what should change in the skill
  handoff/HANDOFF.md     entry point for the next run
```

Three deliverables come out, not one: the draft, the issues list, and the
handoff. The issues list is where the reviewer's attention gets directed.

## Searching the corpus

The `eplus-punch-engine` MCP server (SSE, port 8653) on the Hermes VM, backed by
**724 punch items and 41 narrative report bodies** from 41 published EPLUS
reports (2022–2026) across nine data center projects: NVA02E, NVA05A, NVA05D,
POR03B, POR03C, CHI01A, SVY01D, SVY01E, SVY01F.

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
  and the rendering defaults that were learned the hard way.
- **`plangrid-extraction`** — how PlanGrid PDFs store their data, for when someone
  drops a raw punch report into the chat.

## Hooks

Three, all with an `EPLUS_NO_*` escape hatch. Two are context-only and can never
block a tool call:

| Event | What it does |
|---|---|
| `PostToolUse` (Write/Edit) | Sweeps `drafted_items.json` for photo-narration voice, third-person self-reference, and em/en dashes — at authoring time rather than at build time. |
| `PostToolUse` (Bash) | After `gen_report.js`, reminds you to run `verify_report.py` and to deliver only through `package.py`. |
| `PreToolUse` (Bash) | **Denies** converting a punch report to PDF with LibreOffice. Deliberately narrow: it requires both a PDF conversion and a path naming `_pipeline` or a `-DRAFT-v` report, so the `docx` skill's own soffice validation is untouched even in a folder named after punch work. |

`PostToolUseFailure` is deliberately **not** wired here — the `error-reporting`
plugin owns that event, and a second wiring produces a duplicate nudge for the
same failure.

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
`package.json`) and checked by `scripts/smoke_test.sh`.
