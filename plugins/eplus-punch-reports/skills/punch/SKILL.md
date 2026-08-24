---
name: punch
description: Use this skill whenever a task involves punch lists, punch walks, punch reports, field progress or site inspection reports, security acceptance walks, pre-punch reports, construction deficiencies or defects, "what do we usually find" / recurring-issue questions, punch counts or closeout statistics, per-trade punch checklists or SOPs for a site walk, pulling field photos or marked-up drawing sheets for an issue, exporting a filtered punch list to a spreadsheet, or the eplus-punch-engine MCP tools (query_hermes_punch, get_punch_item, list_punch, punch_stats, grep_punch, export_punch_report). Encodes the exact filter vocabulary of the EPLUS punch corpus — trades, project codes, statuses, sheet references — so queries hit real values instead of guesses. Always load it before calling any eplus-punch-engine tool.
argument-hint: <what to look up — e.g. "recurring telecom issues at NVA05A" or "open security items on sheet T02-01B">
---

# EPLUS punch report workflow (eplus-punch-engine MCP)

Rules for querying the EPLUS punch corpus through the `eplus-punch-engine`
MCP server. Depending on delivery, its tools appear as
`mcp__eplus-punch-engine__<tool>` (managed/desktop connector) or
`mcp__plugin_eplus-punch-reports_eplus-punch-engine__<tool>` (this plugin).
Same server, same rules.

When invoked as a slash command, handle the following request:

$ARGUMENTS

When triggered automatically, apply the same workflow to the punch-related
request in the conversation.

## User-facing language

Say "the EPLUS punch database" or "past punch walks" — never "Hermes,"
"Graph-RAG," "MCP," "SQLite," or raw tool names. Backend terminology is for
reasoning and tool calls only. On failure, lead with a plain-language
explanation and put the verbatim error in a labeled technical details
section.

## What is in the corpus

724 individual punch items plus 41 narrative report bodies, drawn from 41
published EPLUS reports (2022–2026) across nine data center projects. Each
item carries the field engineer's own description, its live status, the
drawing sheet it was pinned to, and captioned site photos. Item text is the
engineer's wording — quote it rather than paraphrasing when precision
matters.

## Available tools

**Pick the cheapest tool that answers the question.** Four of the six
tools are direct database reads — instant, no summarization model, exact
text. Only reach for the synthesized search when the question genuinely
needs keyword matching or thematic summary.

Direct tools (no models, instant, verbatim):

- `punch_stats(project_id=None, group_by="status")` — aggregate counts.
  `group_by`: `status` | `trade` | `project` | `sheet` | `trade_status`
  (trade-by-status matrix). THE tool for "how many open Telecom items on
  POR03B," closeout percentages, which sheets have the most items. Never
  count by pulling items through a search.
- `list_punch(project_id=None, trade=None, status=None, sheet_ref=None,
  limit=50)` — filtered listing: IDs, titles, trades, sheets, statuses.
  The browse tool for "what's open on NVA02E" before deciding what to
  fetch. Reports total matches alongside the returned page.
- `get_punch_item(item_id, upload_photos=True)` — ONE item verbatim: full
  metadata, the engineer's exact wording, every report occurrence, photo
  links. Use for direct lookups ("what is POR03B-99") and to verify
  wording before quoting an item in anything formal.
- `grep_punch(pattern, project_id=None, status=None, max_hits=30)` —
  exact/regex search over titles, sheet refs, descriptions, and photo
  captions. The right tool for device IDs (`BR02-4204B`), room numbers,
  and part numbers that keyword search tokenizes into noise.

Search + synthesis:

- `query_hermes_punch(query, project_id=None, sheet_ref=None, trade=None,
  item_id=None, status=None, upload_photos=True, limit=10)` — stemmed
  keyword + metadata search with a synthesized summary. Use for
  descriptive-language matching ("missing bushings at tray penetrations")
  and recurring-theme questions. Returns matching items and, when
  `upload_photos=True`, temporary download links for site photos and
  marked-up drawing sheets.
- `export_punch_report(query, project_id=None, trade=None, status=None,
  sheet_ref=None, limit=100)` — builds a spreadsheet of matching items and
  returns a download link. Use when the user wants a list to work from,
  hand off, or file — not for answering a question in chat.

All six are read-only. There is no write-back path in this plugin; nothing
a user says can modify the punch database.

## Filter vocabulary — use these exact values

Guessing filter values returns empty results. These are the only values in
the corpus:

**trade** (one per item, rule-derived from the item text and sheet):
`Telecom` (432 items) · `Security` (263) · `AV` (13) · `General` (11) ·
`Electrical` (4) · `Mechanical` (1)

**project_id**: `NVA02E` (207) · `NVA05A` (159) · `POR03B` (147) ·
`POR03C` (71) · `CHI01A` (45) · `NVA05D` (42) · `SVY01D` (27) ·
`SVY01F` (21) · `SVY01E` (5)

**status**: `open` (520) · `closed` (178) · `pending` (26). These are live
values pulled from PlanGrid, not the published PDF snapshots — a report may
print an item as open that has since been closed. Closed items carry a
closed date.

**sheet_ref**: drawing numbers like `T02-01A`, `T03-01B`, `T05-07`, and
phase-prefixed forms like `01E-T02-03B` / `01F-T02-02B` (85 distinct
sheets, all `T`-series). Present on ~92% of items and the most natural way
field staff describe a location. `sheet_ref` filtering is substring-based,
so `T02-03` matches both `T02-03A` and `01E-T02-03B`.

**item_id**: `<PROJECT>-<issue number>`, e.g. `POR03B-277`. A bare number
also works when a project is given.

Map the user's words onto these before querying: "cameras," "card readers,"
"badge readers," "door hardware" → `Security`. "Cable tray," "basket tray,"
"conduit," "IDF," "fiber," "patch panel," "J-hook," "bushings" → `Telecom`.
"Displays," "speakers," "room schedulers" → `AV`. When a request spans
trades, run separate queries rather than dropping the filter.

## How to answer

0. **Route by question type first:**
   - Counts, percentages, closeout status → `punch_stats`. One call, done.
   - "Show/list what's open on X" → `list_punch`.
   - A specific item ID → `get_punch_item`.
   - A device ID, room number, or exact string → `grep_punch`.
   - Descriptive defect language or theme questions → `query_hermes_punch`.
   Chaining is normal: `punch_stats` for the shape, `list_punch` to browse,
   `get_punch_item` for the ones you'll quote.
1. **Parse the request** into filters (project, trade, status, sheet) plus
   a free-text query for the semantic part. Prefer filters over stuffing
   everything into the query string — the filters are exact, the text
   search is fuzzy.
2. **Query.** Keep queries intent-rich but let filters do the narrowing.
   **When a filtered query returns nothing, drop `trade` FIRST.** Field-tested
   2026-08-17: `trade: "Telecom"` with the text "conduit missing bushings
   connector" returned zero results, while the identical query with no trade
   filter returned good hits. The free-text search does the real work; `trade`
   narrows too aggressively on specific phrasing. After `trade`, widen
   `status`, then `sheet_ref`. Say what you widened.
3. **Ground every claim in returned items.** Never answer a "what do we
   usually find" question from general construction knowledge — the value
   here is that it reflects what EPLUS engineers actually wrote up. Cite
   items by `item_id` and quote the engineer's description.
4. **Photos.** Each site photo has a caption describing what is visible, so
   you can tell which photos are worth surfacing without opening them.
   Include the links for the ones that show the deficiency, with a line
   saying what each shows. For counting or listing questions, don't use
   the search tool at all — `punch_stats` and `list_punch` never touch
   photos and answer instantly.
5. **Links expire.** Photo, drawing, and spreadsheet links are temporary
   (about 7 days). Say so when handing one over, so nobody bookmarks it.

## Building a punch-walk checklist or SOP

A recurring ask: "what should we be looking for on a walk." Do this by
querying the corpus per trade, not from memory — the point is that the
checklist reflects EPLUS's actual findings across four years.

Start with `punch_stats(group_by="trade_status")` to see the corpus shape,
then query the trade (optionally scoped to a project or phase), read the
descriptions of what came back, and group them into recurring themes.
Present the checklist grouped by theme with a representative real item
cited for each line, so the reader can see it came from a real walk. Note
how often a theme recurs — `grep_punch` with a theme keyword gives a fast
recurrence count across all projects — a deficiency written up on many
projects belongs at the top of a walk list. Do not pad the list with
generic construction items the corpus does not support.

## Reporting results

- Lead with the direct answer, then the supporting items.
- Identify items as `PROJECT-number` with the sheet reference — that's how
  field staff locate them.
- Quote the engineer's description for anything technical.
- Mention status when it matters (an item closed two years ago is history;
  an open one is live work).
- For an export, say what the spreadsheet contains and how many rows.

## Failure protocol

If the `eplus-punch-engine` connector is missing or a tool call errors,
say in plain language that the punch database could not be reached and that
no lookup happened. Include the verbatim error in a labeled technical
details section. **Never answer punch questions from general construction
knowledge when the lookup failed** — a fabricated "recurring issues" list
looks authoritative and is entirely invented. Offer to retry instead.

If a query succeeds but returns no items, that is a real answer: say the
corpus has nothing matching those filters, state the filters used, and
suggest which one to widen.
