---
name: rfi-workflow
description: Use this skill whenever a task involves RFIs (Requests for Information), submittals, submittal review, RFI response drafting, spec clause lookups, CSI division/section questions, or the eplus-rfi-engine MCP tools (query_hermes_rfi, commit_approved_rfi). Encodes the EPLUS 4-step RFI workflow — deconstruct the request, query Hermes, draft the response, then gate the knowledge-base write-back behind explicit human approval. Always load it before calling any eplus-rfi-engine tool.
---

# EPLUS RFI & Submittal workflow (eplus-rfi-engine MCP)

Rules for processing RFIs and submittals through the `eplus-rfi-engine`
MCP server. Depending on delivery, its tools appear as
`mcp__eplus-rfi-engine__<tool>` (managed/desktop connector) or
`mcp__plugin_eplus-rfis-submittals_eplus-rfi-engine__<tool>` (this
plugin). Same server, same rules.

## Backend: Hermes Knowledge Engine

Hermes is an autonomous agent on a dedicated VM (FastMCP over HTTP/SSE)
with native file access to 82,000+ pages of extracted AEC technical
documents — Core & Shell specs, TFO documentation, product submittals,
historical RFIs, and TIA/NEC codebooks — indexed via Graphify
(Graph-RAG). It can traverse graph dependencies across specs, drawings,
and building codes. Give it clear, intent-rich queries; it does the
retrieval and returns a synthesized context report.

## Available tools

- `query_hermes_rfi(query, project_id="default", csi_section=None)` —
  dispatches a search query to the Hermes Graph-RAG engine and returns a
  synthesized context report. Read-only; call freely.
- `commit_approved_rfi(rfi_id, markdown_content, metadata, project_id="default")` —
  writes a human-approved final RFI response to the VM database and
  triggers an incremental background update to the knowledge graph.
  **Write-back: never call without explicit user approval (Step 4).**

## The 4-step workflow

### Step 1 — Request deconstruction & context analysis

Parse the user's prompt or attached RFI document. Identify the key
engineering attributes:

- Project ID (default to `"default"` only if the user gives none)
- CSI division/section (e.g., `26 05 00`)
- Specific equipment/materials involved
- The core technical question being asked

If the RFI is ambiguous or missing critical attributes, ask the user
before querying.

### Step 2 — Targeted Hermes query formulation

**Do NOT answer the RFI from general pre-training memory.** All
substantive technical claims must be grounded in Hermes-returned context.

Construct a detailed, domain-specific query capturing the intent of the
RFI — include the equipment/materials, the spec context, and what kind of
authority is needed (spec clause, code section, prior RFI precedent).
Then execute:

```
query_hermes_rfi(query=..., project_id=..., csi_section=...)
```

Run additional refined queries if the first report leaves gaps.

### Step 3 — Synthesis & draft generation

Synthesize the raw context returned by Hermes into a formal, professional
engineering RFI response following EPLUS standards:

- Restate the question being answered
- Give a direct, unambiguous determination
- Cite the relevant specification clauses and/or codebook sections
  (TIA/NEC) retrieved by Hermes — never cite from memory
- Note any assumptions, exclusions, or items requiring field verification

### Step 4 — Human-in-the-loop (HITL) write-back gate

Present the drafted response clearly to the user, then ask explicitly:

> "Does this response meet your approval? Reply 'Approve' to commit this
> RFI response to the team knowledge base."

- **Only if the user approves**, call `commit_approved_rfi(...)` with the
  finalized markdown content, the RFI ID, the project ID, and metadata
  (at minimum: CSI section, subject, and date). Hermes then updates the
  knowledge graph automatically.
- If the user requests changes, revise the draft and re-present it —
  never commit an unapproved or intermediate draft.

## Failure protocol

If the `eplus-rfi-engine` connector is missing or a tool call errors,
tell the user exactly that (with the real error) instead of silently
skipping the query or fabricating spec/code citations. Never substitute
pre-training knowledge for a failed Hermes query.
