# rfi-knowledge-hub tool reference

Exact signatures of the `rfi-knowledge-hub` server tools. The server is
delivered as a managed connector; tools appear as
`mcp__rfi-knowledge-hub__<tool>` (or
`mcp__plugin_eplus-rfis-submittals_rfi-knowledge-hub__<tool>` if the plugin
is ever bundled again). The four read tools are called only by the
`rfi-researcher` agent; `commit_approved_rfi` is called only from the main
thread after the Step 4 gate.

## Read tools (researcher only)

- `query_hermes_rfi(query, project_id="default", csi_section=None)` —
  dispatches a search query to the graph engine and returns a synthesized
  context report. Read-only.
  - `query`: **topic keywords only** — equipment, materials, systems, and
    the technical subject (e.g. `"telecom ductbank fiber routing separation
    outside plant"`). Never put project names, CSI/section numbers, or
    meta-words like "spec requirements" / "RFI precedent" in it.
  - `project_id`: the project name goes HERE (e.g. `"PROJECT_A"`,
    `"PROJECT_B"`) — it biases which documents are read. When set, the
    engine runs a second project-scoped retrieval pass; each entry in the
    response's `sources` is labeled `"pass": "general"` or
    `"pass": "project"` so you can see where coverage came from.
  - `csi_section`: the CSI section goes HERE (e.g. `"27 05 26"`).
  - The response's `additional_candidates` lists relevant documents that
    were found but NOT read this time. If the answer looks incomplete, draw
    the next query's keywords from those titles — or read them directly
    with `read_source` — instead of guessing.

**Direct corpus tools — no synthesis models involved, instant, zero token
cost on the backend.** Prefer these over `query_hermes_rfi` whenever you
already know WHAT document you need; use the graph query when you need to
DISCOVER what exists on a topic.

- `list_sources(category=None, project=None, pattern=None,
  spec_version=None, max_results=100)` — browse the corpus file listing.
  `category`: codebooks | specifications | rfis_historical | submittals |
  rfis_approved. `pattern`: case-insensitive substring on the path
  ("270526", "RFI_254", "ductbank"). Returns paths usable with
  `read_source`.
- `read_source(src, offset=0, max_chars=20000)` — the exact text of one
  document, verbatim ground truth. Use it to pull a specific spec part or
  clause, to page through a long document (`total_chars` in the response
  tells you when to page), and to VERIFY any excerpt from a query report
  before citing it in a draft.
- `grep_corpus(pattern, category=None, project=None, spec_version=None,
  max_hits=20)` — exact keyword/phrase/regex search across the raw corpus
  with context lines. The fastest way to find every mention of a part
  number, spec clause ("27 05 26-2.4"), RFI number, or device model across
  all projects.

**Spec versions:** specification files exist as the baseline issue and an
authoritative 2025-08 update. All three direct tools accept `spec_version`:
`"latest"` (the 2025-08 update where one exists — default choice for
determinations), `"baseline"` (the current issue), `"all"` (both — use
when the user asks what changed between versions). `read_source` reports
the file's `version` so citations can name it.

## Write tool (main thread only, gated)

- `commit_approved_rfi(rfi_id, markdown_content, metadata, project_id="default")` —
  writes a human-approved final RFI response to the knowledge base and
  triggers an incremental background update to the knowledge graph.
  **Write-back: never call without explicit user approval through the
  Step 4 AskUserQuestion gate (or the return-path confirmation gate).**
  Required metadata minimum: CSI section, subject, and date. Never commit
  with empty metadata. The plugin's PreToolUse hook additionally makes the
  harness prompt before every call.
