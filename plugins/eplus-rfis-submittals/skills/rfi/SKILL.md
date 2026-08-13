---
name: rfi
description: Use this skill whenever a task involves RFIs (Requests for Information), submittals, submittal review, RFI response drafting, spec clause lookups, CSI division/section questions, logging or committing a finalized/issued RFI response to the knowledge base, or the eplus-rfi-engine MCP tools (query_hermes_rfi, commit_approved_rfi). Encodes the EPLUS 4-step RFI workflow — deconstruct the request, query Hermes, draft the response, then gate the knowledge-base write-back behind an explicit AskUserQuestion approval — plus the return path for logging a final RFI that was edited and issued outside the chat. Always load it before calling any eplus-rfi-engine tool.
argument-hint: <RFI text, attached document reference, or instructions — e.g. "review this request and draft a response">
---

# EPLUS RFI & Submittal workflow (eplus-rfi-engine MCP)

Rules for processing RFIs and submittals through the `eplus-rfi-engine`
MCP server. Depending on delivery, its tools appear as
`mcp__eplus-rfi-engine__<tool>` (managed/desktop connector) or
`mcp__plugin_eplus-rfis-submittals_eplus-rfi-engine__<tool>` (this
plugin). Same server, same rules.

When invoked as a slash command, process the following request through
the 4-step workflow below:

$ARGUMENTS

When triggered automatically (no slash command), apply the same
workflow to the RFI/submittal request in the conversation.

## User-facing language

In anything the user sees — AskUserQuestion text, draft documents,
status messages, reminders — say "the EPLUS knowledge base" or "the
spec database," never "Hermes," "Graph-RAG," "MCP," "stub," or raw
tool names. Backend terminology is for reasoning and tool calls only.
When reporting failures, lead with a plain-language explanation;
include the verbatim error in a clearly-labeled technical details
section rather than as the message itself.

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
  **Write-back: never call without explicit user approval through the
  Step 4 AskUserQuestion gate (or the return-path confirmation gate).**
  Required metadata minimum: CSI section, subject, and date. Never
  commit with empty metadata.

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

query_hermes_rfi(query=..., project_id=..., csi_section=...)

Run additional refined queries if the first report leaves gaps.

**Inspect the payload, not the status field.** A stubbed or empty Hermes
backend still returns `status: "success"` — the scaffold/stub marker is
buried inside the nested `result` string. Before synthesizing anything,
verify the response contains real retrieved content: actual spec clause
text, code section excerpts, or document citations. If the result is a
scaffold marker, placeholder, or empty context, treat the query as
**failed** and enter degraded mode (below). Synthesizing from an empty
context produces a fully fabricated RFI response — the most dangerous
failure mode in this workflow.

### Step 3 — Synthesis & draft generation

Synthesize the raw context returned by Hermes into a formal, professional
engineering RFI response following EPLUS standards:

- Restate the question being answered
- Give a direct, unambiguous determination
- Cite the relevant specification clauses and/or codebook sections
  (TIA/NEC) retrieved by Hermes — never cite from memory
- Note any assumptions, exclusions, or items requiring field verification

**The markdown draft is always the source of truth.** Compose the full
response in markdown first, regardless of output format. If a docx is
produced, it is built FROM this markdown. On approval, the commit
payload is this markdown — never a re-extraction or reconstruction from
a generated document.

**Output format — decide before drafting:**

a. **User explicitly requested a file** (said "Word doc", "docx",
   "send me a file", "something I can attach/issue", or attached a
   docx template to match): FIRST read the docx skill at
   `/mnt/skills/public/docx/SKILL.md` and follow it to produce the
   response as a .docx file built from the markdown draft. Apply EPLUS
   branding per the `eplus-branding-default-fonts` skill (portable
   fonts — RFI responses get issued as PDFs and reopened in Bluebeam).
   Present the file with `present_files` when done. If file-creation
   tools are unavailable in this environment, say so explicitly and
   fall back to path (b).

b. **No file requested** (the default): do NOT load the docx skill and
   do NOT create any file. Render the draft as a clean HTML artifact
   styled for readability (or markdown if the response is plain prose
   with no layout needs). The artifact is a review surface, not a
   deliverable: the user approves or finalizes it at the Step 4 gate,
   and can request a docx export afterward if approved.

Never do both in the same pass. If ambiguous, treat it as (b) and note
once that a Word version is available on request — do not ask a
clarifying question just for output format.

In both formats the response must contain: RFI ID and project header,
the restated question, the formal determination, and a numbered
citations section referencing the exact Hermes-returned spec clauses
and codebook sections.

### Step 4 — Human-in-the-loop (HITL) write-back gate

**Hard rule: `commit_approved_rfi` may only ever carry a human-approved
final response. Never commit a Claude-generated draft on Claude's own
judgment — a draft becomes committable only when the user explicitly
approves it through this gate or hands back their own finalized version
(see return path).**

Present the full draft response in the conversation first, so the user
can read it. Then you MUST call the `AskUserQuestion` tool to get the
approval decision. Do NOT ask for approval as a plain-text message —
the tool call is the gate, and the workflow does not proceed until the
user answers it.

Call `AskUserQuestion` with exactly one question:

- header: "RFI Approval"
- question: "Approve this RFI response for logging to the EPLUS
  knowledge base?"
- options:
  1. label: "Approve & commit"
     description: "Log this response as-is so future RFIs can
     reference it."
  2. label: "Revise draft"
     description: "I'll give feedback; revise and re-present the
     draft, then ask again."
  3. label: "Finalizing outside chat"
     description: "I'll edit and issue the final version myself.
     Don't log anything now."

Act on the selection:

- **Approve & commit** → call `commit_approved_rfi(...)` with the
  markdown draft (the source of truth from Step 3), the RFI ID, the
  project ID, and metadata (minimum: CSI section, subject, date).
  Confirm the commit succeeded and echo the RFI ID.
- **Revise draft** → collect the feedback and revise. If the requested
  change requires new technical substance (a different determination,
  new clauses, changed scope), return to Step 2 and re-query Hermes —
  never patch the technical content from memory. Re-present the
  revised draft and repeat this gate (call AskUserQuestion again).
  Never commit without a fresh "Approve & commit" selection on the
  latest draft.
- **Finalizing outside chat** → commit NOTHING. Remind the user once
  that the knowledge base does not have this RFI yet: an unlogged RFI
  is invisible to future RFI lookups, so they should return with the
  final issued response so it can be logged (see "Logging a finalized
  RFI response" below).
- **Free-text ("Other") answer** → treat as NOT approval unless it
  unambiguously says to commit. When in doubt, re-present the gate.

If the user simply goes quiet after receiving the draft, commit
nothing.

**Degraded-mode gate variant:** when any part of the response is marked
PENDING VERIFICATION (see degraded mode below), do NOT offer a commit
option. Call `AskUserQuestion` with only:

- label: "Retry lookup" — description: "Try the spec database again
  now."
- label: "Keep draft as-is" — description: "I'll finish this manually
  — don't log anything."

Never include an approve/commit option while any determination is
marked PENDING VERIFICATION.

**Fallback:** if the `AskUserQuestion` tool is unavailable in this
environment, state that, ask for approval in prose, and require the
literal word "Approve" before committing. Silence or anything
ambiguous is not approval.

## Logging a finalized RFI response (return path)

Users routinely take the draft, edit it in Word/email, issue it, and
come back later — often in a brand-new chat — just to log the final
version. When a user provides a finalized/issued RFI response (pasted
text or attached document) and asks to log, commit, or save it:

1. Skip Steps 1–3 — do not re-query Hermes or rewrite their content.
   The user's final wording is authoritative; commit it **verbatim**
   (converted to clean markdown if it arrives as a document).
2. Gather the required identifiers if missing: RFI ID, project ID, and
   metadata (CSI section, subject, date). Ask rather than guess.
3. Confirm via `AskUserQuestion` — one question:
   - header: "Confirm commit"
   - question: "Commit RFI <rfi_id> — <subject> (project <project_id>)
     to the knowledge base?"
   - options:
     1. label: "Commit" — description: "Log this final response to
        the EPLUS knowledge base now."
     2. label: "Cancel" — description: "Wrong file or details — do
        not log."
   The user supplying the final document *is* the human approval; this
   confirmation exists only to catch wrong-file mistakes. On "Commit",
   call `commit_approved_rfi(...)`. On "Cancel" or ambiguous free-text,
   commit nothing and ask what to correct.
4. Report the commit result so the user knows the RFI is now in the
   knowledge base.

## Failure protocol

If the `eplus-rfi-engine` connector is missing or a tool call errors,
tell the user in plain language what failed and that no spec lookup
was performed — never silently skip the query or fabricate spec/code
citations. Include the verbatim error in a clearly-labeled technical
details section for troubleshooting. Never substitute pre-training
knowledge for a failed Hermes query.

## Degraded mode (Hermes down, stubbed, or returning empty context)

When Hermes is unavailable or returns no real content, still deliver a
consistent artifact instead of improvising:

1. Tell the user in plain language that the spec database couldn't be
   reached, so citations are pending verification. Put the raw error
   or stub payload in a clearly-labeled technical details section —
   not in the main message.
2. Produce a **PENDING VERIFICATION** response shell with the same
   structure as a normal response:
   - Restated question and parsed attributes (Step 1 output)
   - The determination section marked
     `[PENDING VERIFICATION — spec database unavailable]`
   - Placeholder citation lines naming what must be verified (e.g.,
     "Spec section 26 05 00 — clause TBD") — never invented clause or
     code numbers
   - The Hermes queries you attempted, listed in the technical details
     section, so the run can be replayed when the backend is restored
3. **Never call `commit_approved_rfi` with a PENDING VERIFICATION
   shell** — degraded-mode output must not enter the knowledge base.
   Use the degraded-mode gate variant from Step 4 (no commit option).