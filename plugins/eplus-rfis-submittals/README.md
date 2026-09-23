# eplus-rfis-submittals

Teaches Claude the EPLUS RFI & Submittal processing workflow: settle the
memory question, deconstruct the request, delegate the spec lookup to a
research subagent, draft the response to the house format, and gate the
knowledge-base write-back behind the user's explicit sign-off. The knowledge
base holds 82,000+ pages of extracted AEC technical documents (Core & Shell
specs, program-specific documentation, product submittals, historical RFIs,
and TIA/NEC codebooks) and is reached through the `rfi-knowledge-hub`
connector, which the desktop bootstrap config delivers as a **managed
connector** — this plugin ships no server definition and no credential.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/rfi/SKILL.md`](skills/rfi/SKILL.md) | Doctrine: memory decision → deconstruct → delegate research → draft → HITL write-back gate, plus the return path for logging final RFI responses issued outside the chat |
| Reference | [`skills/rfi/reference/tools.md`](skills/rfi/reference/tools.md) | Exact signatures and parameter rules for the five connector tools |
| Skill     | [`skills/contract-document-review/SKILL.md`](skills/contract-document-review/SKILL.md) | Folder-based review of RFIs and submittals against the project's own drawings, bulletins and specs: one round of questions, governing-sheet register, delegation by building, citation cross-check, packaging (Cowork only) |
| Skill     | [`skills/pdf-stamping/SKILL.md`](skills/pdf-stamping/SKILL.md) | Apply the firm's Bluebeam review stamps and the ENGINEERING PLUS COMMENTS box to a submittal, as live annotations (Cowork only) |
| Agent     | [`agents/rfi-researcher.md`](agents/rfi-researcher.md) | Sonnet research subagent: runs every spec-database lookup in its own isolated context under a hard budget and returns a compact evidence brief |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | Sign-off gate on `commit_approved_rfi` and an export-log echo of the researcher's brief; single PowerShell commands, each with an `EPLUS_NO_*` escape hatch |
| Scripts   | [`scripts/gate-commit.ps1`](scripts/gate-commit.ps1), [`scripts/show-researcher-final.ps1`](scripts/show-researcher-final.ps1) | The two hook bodies (Windows host, PowerShell 5.1, ASCII, always exit 0) |

## Research delegation

The main conversation never calls the four read tools itself. Step 2 of the
`rfi` skill composes a 200–300 token input (RFI id, project, CSI section, the
question in one sentence, extracted nouns, any named authority, spec version,
mode) and hands it to `rfi-researcher`, which runs on Sonnet in an isolated
context. The agent works under a hard budget — at most 3 discovery queries,
4 direct corpus reads, 10 local file operations — and returns a brief of at
most 400 words with fixed headings: `Status` (grounded | keyword-miss |
degraded), `Findings`, `Verbatim clauses` (each confirmed with `read_source`
and cited by path, version, and offset), `Queries run`, `Next step`. Only the
brief enters the main thread; the multi-thousand-token reports stay in the
subagent. The agent never drafts, never proposes a disposition, and cannot
call `commit_approved_rfi` (it is in its `disallowedTools`).

One RFI = one agent. Batches run one agent per RFI, at most three at a time,
with drafting and approval sequential in the main thread. If the spawn fails,
the skill stops and tells the user rather than researching inline.

## Sign-off hook

The marketplace promises nothing is saved without the user's sign-off. The
skill enforces that with an `AskUserQuestion` gate; `hooks/hooks.json` adds a
runtime enforcement: a `PreToolUse` hook on `commit_approved_rfi` (both tool
name forms) returns `permissionDecision: "ask"`, so the harness itself
prompts before any write to the knowledge base, whatever the model decided.
Disable with `EPLUS_NO_RFI_COMMIT_GATE=1`. Since the desktop app release of
2026-09-11 organization-plugin hooks also run in Chat-tab sessions, so the
gate holds wherever the connector is reachable; on older builds the skill's
`AskUserQuestion` gate was the only enforcement in Chat. Not yet confirmed
from a Chat export.

The second hook, `SubagentStop` scoped to `^eplus-rfis-submittals:rfi-researcher$`,
appends the researcher's full brief (with a 220-character excerpt header) to
`<session project dir>/<session_id>/subagent-final-messages.log`, the
directory the session exporter zips. On Cowork the brief travels in the
researcher's `SubagentHandback` call and its last plain message is only a
stub such as "Report delivered.", so the hook takes the message of the last
`SubagentHandback` call from the subagent's own transcript and falls back to
`last_assistant_message` only when none is found; the entry header says which
(`source=handback` or `source=last_message`). Disable with
`EPLUS_NO_RFI_SUBAGENT_ECHO=1`. There is no `SessionStart` hook and no
per-message banner: the fleet is Windows-only, each hook is one
`powershell -File` call costing up to a second, so only the two that matter
are wired.

### Hook wiring notes

The prose that used to sit in a top-level `description` field of
`hooks/hooks.json` lives here: the plugins reference documents no such field,
so it is kept out of the file the app parses.

- **Two single-PowerShell hooks** (the EPLUS fleet is Windows-only and the app
  runs hooks on the Windows host, in Cowork and, since the desktop release of
  2026-09-11, in Chat-tab sessions too; no sh half, no SessionStart).
  (1) `PreToolUse` on `commit_approved_rfi` under both tool-name forms
  (managed connector `mcp__rfi-knowledge-hub__*` and bundled
  `mcp__plugin_eplus-rfis-submittals_rfi-knowledge-hub__*`):
  `scripts/gate-commit.ps1` returns `permissionDecision: "ask"` so the harness
  itself prompts before any write to the EPLUS knowledge base; the marketplace
  promise that nothing is saved without sign-off is enforced by the runtime,
  not only by the skill's `AskUserQuestion` gate. Disable with
  `EPLUS_NO_RFI_COMMIT_GATE=1`. (2) `SubagentStop` scoped to
  `^eplus-rfis-submittals:rfi-researcher$` (plugin agents report the
  plugin-scoped `agent_type`, so the matcher is anchored):
  `scripts/show-researcher-final.ps1` appends the researcher's full evidence
  brief, with a 220-character excerpt header, to
  `<session project dir>/<session_id>/subagent-final-messages.log`, the
  directory the session exporter zips. No `displayContent` banner: that needs
  a `MessageDisplay` drain firing on every message, which this plugin does not
  wire. Disable with `EPLUS_NO_RFI_SUBAGENT_ECHO=1`.
- **Form.** `gate-commit.ps1` reads stdin with `[Console]::In.ReadToEnd()`;
  `show-researcher-final.ps1` reads it as UTF-8 bytes, because the hook
  console code page on the seats (IBM437) mangles non-ASCII text in a brief,
  and appends the log as UTF-8 without a BOM. Both never
  emit `additionalContext` or `decision` on `SubagentStop`, and always exit 0
  with the decision in the JSON body. Every entry uses `"shell": "powershell"`
  with a direct `& "${CLAUDE_PLUGIN_ROOT}\scripts\<name>.ps1"` call, adopted
  2026-09-03 after a field A/B in the same export: the app's own PowerShell
  runs the script in one process (540 ms measured) instead of launching a
  second `powershell.exe` (907 ms). The single-launch form is the standard for
  this catalog.

## Reviews against a Contract Document set

When the evidence is a folder rather than the knowledge base (IFC drawing sets
per building, drawing bulletins, a shared specification set, dozens of
submittal packages), the `rfi` skill hands off to `contract-document-review`.
It carries the review rules a user otherwise has to type into the prompt
(what counts as a Contract Document, bulletin precedence, conflicts go to the
Engineer of Record, product data vs shop drawing criteria, the stamp decision
basis) and adds two controls from a 2026-09-13 field session, where a review
cited tag numbers from an equipment list a bulletin had replaced:

- **Governing-sheet register first.** Before any analysis, bulletins are found
  by title block and revision list (not file name) and every sheet is mapped
  to the document that governs it. Worker prompts cite the register.
- **Citation cross-check before packaging.** Every sheet, tag and model cited
  in a comment is checked against the governing list; nothing is stamped while
  a mismatch is open.

Findings come back from one worker per building, the main thread reconciles
them into a single `FINAL_CONTENT.md`, and every stamp and Word document is
built from that file, so revisions rebuild rather than patch. No knowledge-base
commit happens during a batch review.

## Memory

The RFI skill opens every session by asking whether anything should be saved to
memory at all — *don't save*, *ask before each save*, or *save freely* — and
holds to that answer for the session. An unanswered or ambiguous reply is
treated as *don't save*. Regardless of the answer, project-specific technical
values (mounting heights, note numbers, clause values, part numbers) are never
memorized: they differ between drawing sets on the same program, so the
governing value is read from the project's own sheet every time.

## Stamping submittals

`skills/pdf-stamping` produces an `EPLUS RESPONSE - <file>.pdf` reference copy
carrying **live** annotations — a `/Stamp` annot with the firm's artwork and a
`/FreeText` comment block — so the reviewer can adjust them in Bluebeam before
issuing. Geometry matches an issued response: the review stamp at 286 pt wide,
the comment box the same width 5 pt beneath it, Helvetica 6pt text. Comments
are house red by default; `--comment-color <hex>` sets the text and border
colour without touching the stamp. `--batch manifest.json` stamps many
submittals in one process (plan the whole batch with `--plan`, resume a
cut-off run with `--skip-existing`), writing one JSON result line per job.

Eight stamps ship with the skill in [`skills/pdf-stamping/stamps`](skills/pdf-stamping/stamps),
in two classes the script refuses to interchange:

| Class | Names | Applied to |
|---|---|---|
| Review stamp (`--stamp`) | Exceptions As Noted · No Exception · Rejected (Resubmit) · Review Required · For Record · For Information Only | one page |
| Watermark (`--watermark`) | Draft · For Reference Only | every page |

Placement is planned before anything is written (`--plan` reports ranked
candidates with the ink each would cover); if nothing sits on blank paper the
skill asks rather than covering the drawing. Requires PyMuPDF and a real
filesystem — **Cowork only**, and the stamps are controlled documents that must
not be edited in place.

## Connector tools (server name: `rfi-knowledge-hub`)

1. `query_hermes_rfi(query: str, project_id: str = "default", csi_section: Optional[str] = None) -> str`
   — dispatches a discovery search to the knowledge graph and returns a
   synthesized context report. Researcher only.
2. `list_sources(category=None, project=None, pattern=None, spec_version=None, max_results=100) -> ...`
   — browses the corpus file listing (categories: codebooks,
   specifications, rfis_historical, submittals, rfis_approved); returns
   paths usable with `read_source`. Researcher only.
3. `read_source(src, offset=0, max_chars=20000) -> ...`
   — returns the verbatim text of one corpus document, with paging and
   the file's spec `version`, for pulling exact clauses and verifying
   excerpts before citing. Researcher only.
4. `grep_corpus(pattern, category=None, project=None, spec_version=None, max_hits=20) -> ...`
   — exact keyword/phrase/regex search across the raw corpus with
   context lines, for locating a part number, spec clause, or RFI
   number across all projects. Researcher only.
5. `commit_approved_rfi(rfi_id: str, markdown_content: str, metadata: dict, project_id: str = "default") -> dict`
   — writes back a human-approved final RFI response to the knowledge base
   and triggers an incremental background update to the knowledge graph.
   Main thread only; gated by the skill's approval question and by the
   PreToolUse hook.

## Connector configuration

The `rfi-knowledge-hub` server is delivered to every seat as a **managed
connector** from the desktop bootstrap config. Nothing in this repository
configures it: the plugin no longer ships a `.mcp.json`, and no endpoint,
port, or token lives here. The only requirement on the bootstrap side is the
server name — it must be exactly `rfi-knowledge-hub`, so the tool names the
skill, the agent allowlist, and the hook matcher rely on hold.

## Tool naming

With the managed connector the tools appear as
`mcp__rfi-knowledge-hub__<tool>`. The bundled form
`mcp__plugin_eplus-rfis-submittals_rfi-knowledge-hub__<tool>` may reappear
if the plugin is ever bundled again; the skill, the agent's allowlist, and
the hook matcher tolerate both.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install eplus-rfis-submittals@eplus-claude-plugins
```

Verify: the skills list shows `rfi`, `contract-document-review` and `pdf-stamping`, the agent list shows
`eplus-rfis-submittals:rfi-researcher`, and with the `rfi-knowledge-hub`
connector active, asking Claude to "review this RFI and draft a response"
settles the memory question, then delegates the lookup to the researcher
instead of answering from memory.

For stamping, in a Cowork session with `pymupdf` installed:

```bash
python3 skills/pdf-stamping/scripts/inspect_stamp.py "skills/pdf-stamping/stamps/No Exception.pdf"
```

should report `class: review stamp`, `artwork lives in: ANNOTATIONS`, and a
215 x 108 pt ink bbox.
