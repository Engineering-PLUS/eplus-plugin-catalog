# eplus-rfis-submittals

Skill that teaches Claude the EPLUS RFI & Submittal
Processing workflow. The backend is the **Hermes Knowledge Engine** — a
dedicated Azure VM running a FastMCP server over HTTP/SSE with native
file access to 82,000+ pages of extracted AEC technical documents (Core &
Shell specs, TFO documentation, product submittals, historical RFIs, and
TIA/NEC codebooks) indexed via Graphify (Graph-RAG).

Unlike `eplus-autocad` (whose server is a **local** stdio process that
cannot run inside the Cowork VM), Hermes is a **remote** SSE server —
safe to bundle. This plugin ships an `.mcp.json` at the plugin root that
connects directly over SSE with a Bearer auth header; no local process
is launched, so it works in Claude Code, Cowork, and managed fleets
alike. For Claude Desktop (which does not read plugin `.mcp.json`), use
the `npx supergateway` snippet below in `claude_desktop_config.json`.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/rfi/SKILL.md`](skills/rfi/SKILL.md) | Doctrine: memory decision → deconstruct → query Hermes → draft → HITL write-back gate, plus the return path for logging final RFI responses issued outside the chat |
| Skill     | [`skills/pdf-stamping/SKILL.md`](skills/pdf-stamping/SKILL.md) | Apply the firm's Bluebeam review stamps and the ENGINEERING PLUS COMMENTS box to a submittal, as live annotations (Cowork only) |
| MCP       | [`.mcp.json`](.mcp.json) | Bundled remote SSE connection to the Hermes VM with Bearer auth |

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
the red comment box the same width 5 pt beneath it, red Helvetica 6pt text.

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

## MCP tools (server name: `eplus-rfi-engine`)

1. `query_hermes_rfi(query: str, project_id: str = "default", csi_section: Optional[str] = None) -> str`
   — dispatches a search query to the Hermes Graph-RAG engine and returns
   a synthesized context report.
2. `commit_approved_rfi(rfi_id: str, markdown_content: str, metadata: dict, project_id: str = "default") -> dict`
   — writes back human-approved final RFI responses to the VM database
   and triggers an incremental background update to the knowledge graph.
   Gated behind explicit user approval by the skill.
3. `list_sources(category=None, project=None, pattern=None, spec_version=None, max_results=100) -> ...`
   — browses the corpus file listing (categories: codebooks,
   specifications, rfis_historical, submittals, rfis_approved); returns
   paths usable with `read_source`.
4. `read_source(src, offset=0, max_chars=20000) -> ...`
   — returns the verbatim text of one corpus document, with paging and
   the file's spec `version`, for pulling exact clauses and verifying
   excerpts before citing.
5. `grep_corpus(pattern, category=None, project=None, spec_version=None, max_hits=20) -> ...`
   — exact keyword/phrase/regex search across the raw corpus with
   context lines, for locating a part number, spec clause, or RFI
   number across all projects.

## Claude Code / Cowork configuration

Bundled in [`.mcp.json`](.mcp.json) — native remote SSE, no local
process (replace `<AZURE_VM_PUBLIC_IP>` with the Hermes VM's public IP):

```json
{
  "mcpServers": {
    "eplus-rfi-engine": {
      "type": "sse",
      "url": "http://<AZURE_VM_PUBLIC_IP>:8650/sse",
      "headers": {
        "Authorization": "Bearer af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"
      }
    }
  }
}
```

## Claude Desktop configuration

Claude Desktop doesn't load plugin `.mcp.json`; for local testing there,
add the supergateway proxy to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eplus-rfi-engine": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://<AZURE_VM_PUBLIC_IP>:8650/sse",
        "--header",
        "Authorization: Bearer af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"
      ]
    }
  }
}
```

> **Security note:** the bearer token above is a shared static credential
> sent over plain HTTP. Rotate it if it leaks, and prefer fronting the VM
> with HTTPS (or an Azure Application Gateway/TLS terminator) before
> wide deployment.

## Tool naming

The bundled server is named `eplus-rfi-engine`, so tools appear as
`mcp__plugin_eplus-rfis-submittals_eplus-rfi-engine__<tool>` when loaded
from this plugin, or `mcp__eplus-rfi-engine__<tool>` from a
desktop/managed connection. The skill tolerates both.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install eplus-rfis-submittals@eplus-claude-plugins
```

Verify: the skills list shows `rfi` and `pdf-stamping`, and with the
`eplus-rfi-engine` connection active, asking Claude to "review this RFI and
draft a response" settles the memory question, then queries Hermes instead of
answering from memory.

For stamping, in a Cowork session with `pymupdf` installed:

```bash
python skills/pdf-stamping/scripts/inspect_stamp.py "skills/pdf-stamping/stamps/No Exception.pdf"
```

should report `class: review stamp`, `artwork lives in: ANNOTATIONS`, and a
215 x 108 pt ink bbox.
