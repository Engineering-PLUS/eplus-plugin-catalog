---
name: rfi
description: Use this skill whenever a task involves RFIs (Requests for Information), submittals, submittal review, RFI response drafting, spec clause lookups, CSI division/section questions, logging or committing a finalized/issued RFI response to the knowledge base, or the eplus-rfi-engine MCP tools (query_hermes_rfi, commit_approved_rfi, list_sources, read_source, grep_corpus). Encodes the EPLUS RFI workflow — settle the memory question up front, deconstruct the request, query Hermes, draft the response to the house format, then gate the knowledge-base write-back behind an explicit AskUserQuestion approval — plus the return path for logging a final RFI that was edited and issued outside the chat. Always load it before calling any eplus-rfi-engine tool.
argument-hint: <RFI text, attached document reference, or instructions — e.g. "review this request and draft a response">
---

# EPLUS RFI & Submittal workflow (eplus-rfi-engine MCP)

Rules for processing RFIs and submittals through the `eplus-rfi-engine`
MCP server. Depending on delivery, its tools appear as
`mcp__eplus-rfi-engine__<tool>` (managed/desktop connector) or
`mcp__plugin_eplus-rfis-submittals_eplus-rfi-engine__<tool>` (this
plugin). Same server, same rules.

When invoked as a slash command, process the following request through
the workflow below:

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
and building codes.

**The graph matcher is LITERAL — it matches query words against node
labels, with no semantic understanding.** Query quality lives or dies
on keyword choice: topic nouns that would appear in document titles
and spec language. Intent phrasing ("spec requirements", "prior RFI
precedent", "clarification on"), project names, and CSI numbers in the
query text seed the search on the wrong nodes and poison retrieval.

## Available tools

- `query_hermes_rfi(query, project_id="default", csi_section=None)` —
  dispatches a search query to the Hermes Graph-RAG engine and returns a
  synthesized context report. Read-only; call freely.
  - `query`: **topic keywords only** — equipment, materials, systems,
    and the technical subject (e.g. `"telecom ductbank fiber routing
    separation outside plant"`). Never put project names, CSI/section
    numbers, or meta-words like "spec requirements" / "RFI precedent"
    in it.
  - `project_id`: the project name goes HERE (e.g. `"STACK_NVA05D"`,
    `"Miner_Building_A"`) — it biases which documents are read. When
    set, the engine runs a second project-scoped retrieval pass; each
    entry in the response's `sources` is labeled `"pass": "general"`
    or `"pass": "project"` so you can see where coverage came from.
  - `csi_section`: the CSI section goes HERE (e.g. `"27 05 26"`).
  - The response's `additional_candidates` lists relevant documents
    that were found but NOT read this time. If the answer looks
    incomplete, draw the next query's keywords from those titles — or
    read them directly with `read_source` — instead of guessing.

**Direct corpus tools — no synthesis models involved, instant, zero
token cost on the backend.** Prefer these over `query_hermes_rfi`
whenever you already know WHAT document you need; use the graph query
when you need to DISCOVER what exists on a topic.

- `list_sources(category=None, project=None, pattern=None,
  spec_version=None, max_results=100)` — browse the corpus file
  listing. `category`: codebooks | specifications | rfis_historical |
  submittals | rfis_approved. `pattern`: case-insensitive substring on
  the path ("270526", "RFI_254", "ductbank"). Returns paths usable
  with `read_source`.
- `read_source(src, offset=0, max_chars=20000)` — the exact text of
  one document, verbatim ground truth. Use it to pull a specific spec
  part or clause, to page through a long document (`total_chars` in
  the response tells you when to page), and to VERIFY any excerpt from
  a query report before citing it in a draft.
- `grep_corpus(pattern, category=None, project=None, spec_version=None,
  max_hits=20)` — exact keyword/phrase/regex search across the raw
  corpus with context lines. The fastest way to find every mention of
  a part number, spec clause ("27 05 26-2.4"), RFI number, or device
  model across all projects.

**Spec versions:** specification files exist as the baseline issue and
an authoritative 2025-08 update. All three direct tools accept
`spec_version`: `"latest"` (the 2025-08 update where one exists —
default choice for determinations), `"baseline"` (the current issue),
`"all"` (both — use when the user asks what changed between versions).
`read_source` reports the file's `version` so citations can name it.
- `commit_approved_rfi(rfi_id, markdown_content, metadata, project_id="default")` —
  writes a human-approved final RFI response to the VM database and
  triggers an incremental background update to the knowledge graph.
  **Write-back: never call without explicit user approval through the
  Step 4 AskUserQuestion gate (or the return-path confirmation gate).**
  Required metadata minimum: CSI section, subject, and date. Never
  commit with empty metadata.

## The workflow

### Step 0 — Memory decision (once per session, before anything else)

Before the first lookup — and before writing any memory file — call
`AskUserQuestion` with exactly one question:

- header: "Memory"
- question: "Should I save anything from this session to memory?"
- options:
  1. label: "Don't save anything"
     description: "Nothing is written to memory this session. Safest while
     this workflow is still changing."
  2. label: "Ask me before each save"
     description: "I'll show you the exact note before writing it."
  3. label: "Save freely"
     description: "I'll save context as it comes up and tell you what I
     wrote."

Then hold to it for the whole session:

- **Don't save anything** → write no memory files at all, and do not raise it
  again. Do not offer a summary "just in case."
- **Ask me before each save** → show the full proposed note and get an explicit
  yes before each write.
- **Save freely** → write as you go and report what you wrote.

Ask once. If the question is skipped, dismissed, or answered ambiguously,
treat it as **Don't save anything**. If the user has already said in this
session what they want, honour that and skip the question.

**What must never go into memory, under any option:**

- **Project-specific technical values** — mounting heights, note numbers,
  clause values, dimensions, part numbers, equipment schedules. These vary
  between drawing sets on the same program, and a remembered value invites a
  future session to apply one project's number to another. The governing value
  is read from the project's own sheet or the knowledge base every time.
- Anything the knowledge base already holds. Committed RFIs are retrievable —
  memory is not a second copy of them.

**What is worth saving** (subject to the choice above): who the user is and how
they work, standing feedback on drafting and tone, project identifiers, the
governing drawing set, open items, and where in the corpus a recurring answer
lives. Reasoning that travels between projects is fine; the numbers are not.

Every memory file this skill writes ends with a provenance line — the date and
`eplus-rfis-submittals` version it was written under — so a later session can
see it predates a workflow change. Memories are advisory context, never a
citation: nothing recalled from memory may appear in a draft as a technical
claim without being re-verified against the corpus.

### Step 1 — Request deconstruction & context analysis

Parse the user's prompt or attached RFI document. Identify the key
engineering attributes:

- Project ID (default to `"default"` only if the user gives none)
- CSI division/section (e.g., `26 05 00`)
- Specific equipment/materials involved
- The core technical question being asked

**Capture the RFI identifier here, not at the commit gate.** If the user hasn't
given an RFI number and the attached document doesn't carry one, ask for it
now, while they are already supplying context — discovering at Step 4 that the
response has nowhere to be filed wastes a turn and tempts a bad guess.

**Never invent an identifier.** Do not offer a synthesized placeholder such as
`<PROJECT>-<TOPIC>-<DATE>` as an option — a made-up number in the knowledge
base is indistinguishable from a real one to every future lookup. If the number
genuinely does not exist yet, that is a reason to defer the commit, not to
manufacture a key: draft the response, and log it when the number is issued via
the return path below.

If the RFI is ambiguous or missing critical attributes, ask the user
before querying.

### Step 2 — Targeted Hermes query formulation

**Do NOT answer the RFI from general pre-training memory.** All
substantive technical claims must be grounded in Hermes-returned context.

**Pick the right retrieval path first.** If the RFI already names the
authority you need — a spec section ("27 05 26 part 2.4"), an RFI
number, a device/part number — go DIRECT: `grep_corpus` to locate it,
`read_source` to pull the exact text (`spec_version="latest"` for
determinations). That's verbatim ground truth at zero backend cost and
counts fully as grounding. Use `query_hermes_rfi` when you need to
discover what the corpus holds on a topic: precedent, related
submittals, cross-project practice.

Build the query as **4–10 topic keywords**, not a sentence. Pick the
nouns a spec writer or submittal title would use: equipment, materials,
systems, standards bodies, and the technical subject. Pass project and
CSI section through their own parameters — never inside the query text.

- Good: `query="IDF rack dedicated circuit UPS receptacle power",
  project_id="STACK_NVA06A", csi_section="26 05 00"`
- Bad: `query="NVA06 spec requirements and prior RFI precedent for
  UPS-backed circuits (CSI 26 05 00)"` — the project name, CSI number,
  and intent words match the wrong graph nodes and poison retrieval.

Then execute:

query_hermes_rfi(query=..., project_id=..., csi_section=...)

If the report leaves gaps, check its `additional_candidates` first —
those are documents the engine found but didn't read. Reading the
promising ones with `read_source` is cheaper and more precise than
another graph query. Only then run additional queries with **different
keyword angles** (synonyms, the counterpart trade's vocabulary, the
governing standard's terms — e.g. `ductbank` vs `duct bank` vs
`underground pathways`), rather than lengthening one query.

**Verify before you cite.** Before a quoted clause, number, or
determination goes into the draft, confirm it against the source with
`read_source` (the report names each excerpt's source path). The
synthesis stage is instructed to quote verbatim, but the source file is
the authority — a ten-second read beats a wrong citation in an issued
RFI.

**At most 2–3 queries per batch — review the results before querying
again.** Each report can run thousands of tokens and stays in the
conversation for every subsequent turn, so a broad exploratory batch
burns the daily token budget even when each response is fine on its
own. Read what came back, keep only the angle that's working, and let
that decide whether another query is needed at all.

**"No relevant content found in retrieved documents." is a keyword
miss, not an outage.** The database reached real documents but none
matched the topic. Retry 1–2 times with different keyword angles
before treating the lookup as failed; only enter degraded mode if
retries also come back empty or the tool itself errors.

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

**House response format — write to it from the first draft.** These
responses are not letters. They get typed into an RFI response field, or
into the red ENGINEERING PLUS COMMENTS box beneath the review stamp on a
submittal, where they render as 6pt text in a box about 286 pt wide. That
box is the real constraint on length.

- **Two to four sentences per response.** Determination first, then the
  reason, then any action required of the contractor.
- No letterhead, salutation, or closing paragraph. No restated preamble
  before the answer.
- Multiple questions get numbered responses, each self-contained.
- Where a response will be stamped onto a drawing, keep the whole comment
  block to roughly 25 lines at that width — beyond that it stops fitting
  next to the stamp.
- Citations stay in their own section beneath the responses, not woven into
  the sentences.

Writing long and cutting back wastes a review cycle. Write short first; the
user can always ask for more.

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

## Handing off to the stamp

When the response is going onto a submittal rather than into an RFI field —
the user asks to stamp the submittal, mark it reviewed, or produce an
"EPLUS RESPONSE" copy — load the `pdf-stamping` skill in this plugin and
follow it. The approved response text becomes the ENGINEERING PLUS COMMENTS
block; the disposition stamp is the user's call, never inferred from the
comments. Stamping is Cowork-only.

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

**Try the direct corpus tools before declaring degraded mode.** The
synthesis pipeline and the direct tools fail independently: when
`query_hermes_rfi` errors or returns empty synthesis, `grep_corpus` +
`read_source` usually still work, and a draft grounded in verbatim
`read_source` text is a NORMAL response with real citations — not a
PENDING VERIFICATION shell. Enter degraded mode only when the direct
tools are also unavailable or the corpus genuinely lacks the material.

When the backend is truly unreachable, still deliver a consistent
artifact instead of improvising:

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