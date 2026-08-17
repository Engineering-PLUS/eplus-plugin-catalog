# EPLUS Punch Reports

Search four years of EPLUS punch walks from chat — find recurring
deficiencies by trade, project, or drawing sheet, pull the field photos that
show them, and export filtered punch lists to a spreadsheet.

## What it connects to

The `eplus-punch-engine` MCP server (SSE, port 8653) on the Hermes VM,
backed by a corpus of **724 punch items and 41 narrative report bodies**
extracted from 41 published EPLUS reports (2022–2026) across nine data
center projects: NVA02E, NVA05A, NVA05D, POR03B, POR03C, CHI01A, SVY01D,
SVY01E, SVY01F.

Each item carries the field engineer's own description, the live
open/closed/pending status pulled from PlanGrid, the drawing sheet it was
pinned to, and site photos with generated captions describing what each one
shows.

## Tools

| Tool | Purpose |
|---|---|
| `query_hermes_punch` | Hybrid keyword + metadata search with a synthesized answer, plus temporary download links for the relevant site photos and marked-up drawing sheets. |
| `export_punch_report` | Builds a spreadsheet of matching items and returns a download link. |

Both are read-only — this plugin cannot modify the punch database.

## Skills

- **`punch`** — the query workflow and the exact filter vocabulary (trades,
  project codes, statuses, sheet references), so queries hit real values.
  Also covers building a per-trade punch-walk checklist from what EPLUS has
  actually written up, rather than from generic construction knowledge.
- **`punch-report-generation`** — **produces** a new report from raw field
  material: photos, walk notes, a PlanGrid pull. Assumes the input is messy
  (no room data, untagged notes, misfire pins, unreadable photos) because it
  always is, and surfaces what it cannot determine instead of inventing it.
  Bundles `scripts/consolidate.py` and carries the hard-won rendering
  defaults — one item per page with dynamic photo-grid sizing, EXIF rotation,
  thumbnail downscaling, and the DXA-vs-pixel trap.
- **`plangrid-extraction`** — how PlanGrid PDFs store their data, for when
  someone drops a raw punch report into the chat. Covers the three photo
  traps (full drawing behind a clipped view, markup only in vector
  annotations, camera-native rotation) plus extracting the per-item
  annotated sheet clip from a Task Report PDF.

## Typical asks

- "What telecom issues keep coming up at NVA05A?"
- "Show me the open security items on sheet T02-01B with photos."
- "Build me a punch-walk checklist for the telecom scope."
- "Export all open POR03C items to a spreadsheet."
- "What was punch item POR03B-277?"

## Notes

Photo, drawing, and spreadsheet links are temporary (about 7 days) — save
anything worth keeping. Status values are live from PlanGrid, so an item a
published PDF shows as open may since have been closed.
